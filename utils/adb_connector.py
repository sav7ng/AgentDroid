"""
ADB连接器模块

提供统一的ADB连接管理，支持多种连接方式：
- 本地连接（默认）
- 直连远程ADB（A厂商）
- SSH隧道连接（B厂商）
"""

import subprocess
import time
import tempfile
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import adbutils

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AdbConnectionConfig:
    """ADB连接配置"""
    type: str = "local"  # local, direct, ssh_tunnel
    params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}


class AdbConnector(ABC):
    """ADB连接器基类"""
    
    @abstractmethod
    def connect(self) -> adbutils.AdbDevice:
        """建立连接并返回ADB设备对象"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开连接并清理资源"""
        pass
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class LocalAdbConnector(AdbConnector):
    """本地ADB连接器（默认方式）"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 5037):
        self.host = host
        self.port = port
        self._device = None
    
    def connect(self) -> adbutils.AdbDevice:
        """连接本地ADB设备"""
        logger.info("使用本地ADB连接", extra={"host": self.host, "port": self.port})
        adb = adbutils.AdbClient(host=self.host, port=self.port)
        self._device = adb.device()
        model = self._device.getprop('ro.product.model')
        logger.info("成功连接到ADB设备", extra={"device_model": model})
        return self._device
    
    def disconnect(self):
        """本地连接无需特殊清理"""
        logger.debug("本地ADB连接断开")
        self._device = None


class DirectAdbConnector(AdbConnector):
    """直连远程ADB连接器（A厂商方式）"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Args:
            params: 连接参数
                - address: ADB地址，如 "192.168.1.100:5555"
                - key: ADB私钥内容（可选）
        """
        self.address = params.get("address")
        self.key = params.get("key")
        self._device = None
        self._key_file = None
        
        if not self.address:
            raise ValueError("直连模式需要提供 address 参数")
    
    def connect(self) -> adbutils.AdbDevice:
        """直连远程ADB设备"""
        logger.info("使用直连模式连接远程ADB", extra={"address": self.address})
        
        # 如果提供了key，写入临时文件
        if self.key:
            self._setup_adb_key()
        
        # 连接远程设备
        try:
            result = subprocess.run(
                ["adb", "connect", self.address],
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            logger.debug("ADB connect 输出", extra={"output": output})
            
            if "connected" not in output.lower() and "already connected" not in output.lower():
                raise ConnectionError(f"无法连接到远程ADB: {output}")
            
            # 获取设备对象
            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            self._device = adb.device(self.address)
            model = self._device.getprop('ro.product.model')
            logger.info("成功连接到远程ADB设备", extra={"address": self.address, "device_model": model})
            return self._device
            
        except subprocess.TimeoutExpired:
            raise ConnectionError(f"连接远程ADB超时: {self.address}")
        except Exception as e:
            raise ConnectionError(f"连接远程ADB失败: {str(e)}")
    
    def _setup_adb_key(self):
        """设置ADB密钥"""
        if not self.key:
            return
        
        # 创建临时密钥文件
        self._key_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_adbkey')
        self._key_file.write(self.key)
        self._key_file.close()
        
        # 设置环境变量指向密钥
        os.environ['ADB_VENDOR_KEYS'] = self._key_file.name
        logger.debug("已设置ADB密钥", extra={"key_file": self._key_file.name})
    
    def disconnect(self):
        """断开远程ADB连接"""
        try:
            if self.address:
                subprocess.run(
                    ["adb", "disconnect", self.address],
                    capture_output=True,
                    timeout=10
                )
                logger.info("已断开远程ADB连接", extra={"address": self.address})
        except Exception as e:
            logger.warning("断开ADB连接时出错", extra={"error": str(e)})
        
        # 清理临时密钥文件
        if self._key_file and os.path.exists(self._key_file.name):
            try:
                os.unlink(self._key_file.name)
                logger.debug("已清理临时ADB密钥文件")
            except Exception as e:
                logger.warning("清理ADB密钥文件失败", extra={"error": str(e)})
        
        self._device = None


class SshTunnelAdbConnector(AdbConnector):
    """SSH隧道ADB连接器（B厂商方式）"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        Args:
            params: 连接参数
                - ssh_command: 完整的SSH命令（如 "ssh -oHostKeyAlgorithms=+ssh-rsa user@host -p port -L local:remote:port -Nf"）
                - ssh_password: SSH密码
                - adb_address: ADB连接地址（如 "127.0.0.1:8011"）
        """
        self.ssh_command = params.get("ssh_command")
        self.ssh_password = params.get("ssh_password")
        self.adb_address = params.get("adb_address", "127.0.0.1:5555")
        self._device = None
        self._ssh_process = None
        
        if not self.ssh_command:
            raise ValueError("SSH隧道模式需要提供 ssh_command 参数")
        if not self.adb_address:
            raise ValueError("SSH隧道模式需要提供 adb_address 参数")
    
    def connect(self) -> adbutils.AdbDevice:
        """通过SSH隧道连接ADB设备"""
        logger.info("使用SSH隧道模式连接ADB", extra={"adb_address": self.adb_address})
        
        # 建立SSH隧道
        self._establish_ssh_tunnel()
        
        # 等待隧道建立
        time.sleep(2)
        
        # 连接ADB
        try:
            result = subprocess.run(
                ["adb", "connect", self.adb_address],
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            logger.debug("ADB connect 输出", extra={"output": output})
            
            if "connected" not in output.lower() and "already connected" not in output.lower():
                raise ConnectionError(f"无法连接到ADB (通过SSH隧道): {output}")
            
            # 获取设备对象
            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            self._device = adb.device(self.adb_address)
            model = self._device.getprop('ro.product.model')
            logger.info("成功通过SSH隧道连接到ADB设备", 
                       extra={"adb_address": self.adb_address, "device_model": model})
            return self._device
            
        except subprocess.TimeoutExpired:
            self._cleanup_ssh_tunnel()
            raise ConnectionError(f"连接ADB超时 (通过SSH隧道): {self.adb_address}")
        except Exception as e:
            self._cleanup_ssh_tunnel()
            raise ConnectionError(f"连接ADB失败 (通过SSH隧道): {str(e)}")
    
    def _establish_ssh_tunnel(self):
        """建立SSH隧道"""
        logger.info("正在建立SSH隧道...")
        
        try:
            # 使用 sshpass 处理密码（如果提供了密码）
            if self.ssh_password:
                # 检查是否安装了 sshpass
                sshpass_check = subprocess.run(
                    ["where", "sshpass"] if os.name == 'nt' else ["which", "sshpass"],
                    capture_output=True
                )
                
                if sshpass_check.returncode == 0:
                    # 使用 sshpass
                    full_command = f'sshpass -p "{self.ssh_password}" {self.ssh_command}'
                else:
                    # Windows 或没有 sshpass，使用 expect 脚本或 plink
                    logger.warning("未找到 sshpass，尝试使用替代方案")
                    full_command = self._build_ssh_command_with_password()
            else:
                full_command = self.ssh_command
            
            logger.debug("执行SSH命令", extra={"command": full_command.replace(self.ssh_password or "", "***")})
            
            # 执行SSH命令（后台运行）
            if os.name == 'nt':
                # Windows 使用 start 命令
                self._ssh_process = subprocess.Popen(
                    full_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE
                )
            else:
                # Linux/Mac
                self._ssh_process = subprocess.Popen(
                    full_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    preexec_fn=os.setpgrp
                )
            
            # 如果命令包含 -Nf（后台运行），等待进程启动
            if "-Nf" in self.ssh_command or "-fN" in self.ssh_command:
                time.sleep(3)
                logger.info("SSH隧道已在后台建立")
            else:
                # 检查进程是否正常启动
                time.sleep(1)
                if self._ssh_process.poll() is not None:
                    stdout, stderr = self._ssh_process.communicate()
                    raise ConnectionError(f"SSH隧道建立失败: {stderr.decode()}")
                logger.info("SSH隧道已建立")
                
        except Exception as e:
            logger.error("建立SSH隧道失败", extra={"error": str(e)})
            raise ConnectionError(f"建立SSH隧道失败: {str(e)}")
    
    def _build_ssh_command_with_password(self) -> str:
        """构建带密码的SSH命令（Windows兼容）"""
        # 尝试使用 plink (PuTTY)
        plink_check = subprocess.run(
            ["where", "plink"] if os.name == 'nt' else ["which", "plink"],
            capture_output=True
        )
        
        if plink_check.returncode == 0:
            # 将 ssh 命令转换为 plink 格式
            # 解析原始 ssh 命令
            cmd = self.ssh_command
            
            # 提取参数
            host_match = re.search(r'(\S+@\S+)', cmd)
            port_match = re.search(r'-p\s+(\d+)', cmd)
            forward_match = re.search(r'-L\s+(\S+)', cmd)
            
            if host_match:
                host = host_match.group(1)
                port = port_match.group(1) if port_match else "22"
                forward = forward_match.group(1) if forward_match else ""
                
                plink_cmd = f'plink -ssh -pw "{self.ssh_password}" -P {port}'
                if forward:
                    plink_cmd += f' -L {forward}'
                plink_cmd += f' -N {host}'
                return plink_cmd
        
        # 回退：直接使用原命令（可能需要手动输入密码）
        logger.warning("无法自动处理SSH密码，请确保SSH密钥已配置或手动输入密码")
        return self.ssh_command
    
    def _cleanup_ssh_tunnel(self):
        """清理SSH隧道"""
        if self._ssh_process:
            try:
                self._ssh_process.terminate()
                self._ssh_process.wait(timeout=5)
                logger.debug("SSH隧道进程已终止")
            except Exception as e:
                logger.warning("终止SSH隧道进程失败", extra={"error": str(e)})
                try:
                    self._ssh_process.kill()
                except:
                    pass
            self._ssh_process = None
        
        # 尝试杀死后台SSH进程（针对 -Nf 模式）
        if "-Nf" in self.ssh_command or "-fN" in self.ssh_command:
            self._kill_background_ssh()
    
    def _kill_background_ssh(self):
        """杀死后台SSH进程"""
        try:
            # 从 adb_address 提取本地端口
            local_port = self.adb_address.split(":")[-1]
            
            if os.name == 'nt':
                # Windows: 查找并杀死占用端口的进程
                result = subprocess.run(
                    f'netstat -ano | findstr ":{local_port}"',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.strip().split('\n'):
                    if 'LISTENING' in line or 'ESTABLISHED' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                            logger.debug(f"已终止SSH进程 PID: {pid}")
            else:
                # Linux/Mac: 使用 pkill 或 fuser
                subprocess.run(
                    f'fuser -k {local_port}/tcp 2>/dev/null || true',
                    shell=True,
                    capture_output=True
                )
                logger.debug(f"已清理端口 {local_port} 上的进程")
        except Exception as e:
            logger.warning("清理后台SSH进程失败", extra={"error": str(e)})
    
    def disconnect(self):
        """断开SSH隧道和ADB连接"""
        try:
            if self.adb_address:
                subprocess.run(
                    ["adb", "disconnect", self.adb_address],
                    capture_output=True,
                    timeout=10
                )
                logger.info("已断开ADB连接", extra={"address": self.adb_address})
        except Exception as e:
            logger.warning("断开ADB连接时出错", extra={"error": str(e)})
        
        # 清理SSH隧道
        self._cleanup_ssh_tunnel()
        self._device = None
        logger.info("SSH隧道已关闭")


class AdbConnectorFactory:
    """ADB连接器工厂"""
    
    @staticmethod
    def create(config: Optional[AdbConnectionConfig] = None) -> AdbConnector:
        """
        根据配置创建合适的ADB连接器
        
        Args:
            config: ADB连接配置，为None时使用本地连接
            
        Returns:
            AdbConnector 实例
        """
        if config is None:
            logger.info("使用默认本地ADB连接器")
            return LocalAdbConnector()
        
        conn_type = config.type.lower()
        params = config.params or {}
        
        if conn_type == "local":
            return LocalAdbConnector(
                host=params.get("host", "127.0.0.1"),
                port=params.get("port", 5037)
            )
        elif conn_type == "direct":
            return DirectAdbConnector(params)
        elif conn_type == "ssh_tunnel":
            return SshTunnelAdbConnector(params)
        else:
            raise ValueError(f"不支持的ADB连接类型: {conn_type}")
    
    @staticmethod
    def from_dict(config_dict: Optional[Dict[str, Any]] = None) -> AdbConnector:
        """
        从字典创建ADB连接器
        
        Args:
            config_dict: 配置字典，格式为 {"type": "...", "params": {...}}
            
        Returns:
            AdbConnector 实例
        """
        if config_dict is None:
            return AdbConnectorFactory.create(None)
        
        config = AdbConnectionConfig(
            type=config_dict.get("type", "local"),
            params=config_dict.get("params", {})
        )
        return AdbConnectorFactory.create(config)
