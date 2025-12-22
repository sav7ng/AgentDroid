"""
PhoneAgent 适配器类

包装 phone_agent.PhoneAgent，实现与 MobileUseAgent 统一的接口。
"""

from typing import Dict, Any, Generator, Optional, Callable
import asyncio
import uuid
import sys
from pathlib import Path
from datetime import datetime

# 将 agents 目录添加到 Python 路径，以便导入 phone_agent
agents_dir = Path(__file__).parent.parent
if str(agents_dir) not in sys.path:
    sys.path.insert(0, str(agents_dir))

from phone_agent.agent import PhoneAgent, AgentConfig, StepResult
from phone_agent.model import ModelConfig


class PhoneAgentWrapper:
    """
    PhoneAgent 适配器，实现统一的 Agent 接口
    
    特性：
    - 支持 ADB 和 HDC (HarmonyOS) 设备
    - 提供与 MobileUseAgent 兼容的接口
    - 支持流式输出（通过包装 step() 方法）
    """
    
    AGENT_TYPE = "phone-agent"
    
    def __init__(self, 
                 api_key: str,
                 base_url: str,
                 model_name: str = "autoglm-phone",
                 max_steps: int = 50,
                 device_id: Optional[str] = None,
                 lang: str = "cn",
                 verbose: bool = True,
                 confirmation_callback: Optional[Callable[[str], bool]] = None,
                 takeover_callback: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        初始化 PhoneAgent 包装器
        
        Args:
            api_key: LLM API 密钥
            base_url: LLM API 基础 URL
            model_name: 模型名称
            max_steps: 最大执行步数
            device_id: 设备 ID（可选，用于多设备场景）
            lang: 语言（cn 或 en）
            verbose: 是否输出详细日志
            confirmation_callback: 敏感操作确认回调
            takeover_callback: 接管请求回调
            **kwargs: 其他配置参数
        """
        
        # 创建 PhoneAgent 配置
        model_config = ModelConfig(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name
        )
        
        agent_config = AgentConfig(
            max_steps=max_steps,
            device_id=device_id,
            lang=lang,
            verbose=verbose
        )
        
        # 创建 PhoneAgent 实例
        self.phone_agent = PhoneAgent(
            model_config=model_config,
            agent_config=agent_config,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback
        )
        
        # 保存配置用于 get_agent_info
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.max_steps = max_steps
        self.device_id = device_id
        self.lang = lang
        self.output_dir = kwargs.get('output_dir', 'agent_outputs')
    
    async def run(self, instruction: str, **kwargs) -> Dict[str, Any]:
        """
        同步执行任务（适配 MobileUseAgent 接口）
        
        Args:
            instruction: 用户指令
            **kwargs: 覆盖配置参数
            
        Returns:
            执行结果字典，包含：
            - status: 执行状态（success | error）
            - message: 最终消息
            - history: 执行历史
            - agent_type: Agent 类型标识
        """
        try:
            # 在线程池中运行 PhoneAgent（避免阻塞事件循环）
            message = await asyncio.to_thread(
                self.phone_agent.run,
                instruction
            )
            
            return {
                "status": "success",
                "message": message,
                "history": self._convert_context_to_history(),
                "step_count": self.phone_agent.step_count,
                "agent_type": self.AGENT_TYPE
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "history": [],
                "step_count": 0,
                "agent_type": self.AGENT_TYPE
            }
    
    def run_stream(self, instruction: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式执行任务（模拟流式输出）
        
        PhoneAgent 本身不支持流式，这里通过包装 step() 方法模拟流式输出。
        
        Args:
            instruction: 用户指令
            **kwargs: 覆盖配置参数
            
        Yields:
            事件字典，包含：
            - event_type: 事件类型
            - task_id: 任务 ID
            - step: 步骤编号
            - timestamp: 时间戳
            - agent_type: Agent 类型标识
            - data: 事件数据
        """
        task_id = kwargs.get('task_id') or str(uuid.uuid4())[:8]
        
        # 1. 任务初始化事件
        yield {
            "event_type": "task_init",
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "agent_type": self.AGENT_TYPE,
            "data": {
                "instruction": instruction,
                "max_steps": self.max_steps,
                "device_id": self.device_id,
                "lang": self.lang
            }
        }
        
        # 2. 重置 Agent 状态
        self.phone_agent.reset()
        
        # 3. 执行首步
        try:
            result = self.phone_agent.step(instruction)
            
            yield {
                "event_type": "step_completed",
                "task_id": task_id,
                "step": 1,
                "timestamp": datetime.now().isoformat(),
                "agent_type": self.AGENT_TYPE,
                "data": {
                    "action": result.action,
                    "thinking": result.thinking,
                    "success": result.success,
                    "finished": result.finished,
                    "message": result.message
                }
            }
            
            if result.finished:
                yield {
                    "event_type": "task_completed",
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": self.AGENT_TYPE,
                    "data": {
                        "status": "success" if result.success else "error",
                        "message": result.message or "Task completed",
                        "total_steps": 1,
                        "history": self._convert_context_to_history()
                    }
                }
                return
            
            # 4. 继续执行后续步骤
            step = 2
            while step <= self.max_steps:
                result = self.phone_agent.step()
                
                yield {
                    "event_type": "step_completed",
                    "task_id": task_id,
                    "step": step,
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": self.AGENT_TYPE,
                    "data": {
                        "action": result.action,
                        "thinking": result.thinking,
                        "success": result.success,
                        "finished": result.finished,
                        "message": result.message
                    }
                }
                
                if result.finished:
                    break
                
                step += 1
            
            # 5. 任务完成事件
            final_status = "success" if result.success else "error"
            if step > self.max_steps and not result.finished:
                final_status = "max_steps_reached"
            
            yield {
                "event_type": "task_completed",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "agent_type": self.AGENT_TYPE,
                "data": {
                    "status": final_status,
                    "message": result.message or "Task completed",
                    "total_steps": step,
                    "history": self._convert_context_to_history()
                }
            }
            
        except Exception as e:
            yield {
                "event_type": "error",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "agent_type": self.AGENT_TYPE,
                "data": {
                    "error_type": "execution",
                    "message": str(e)
                }
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """
        获取 Agent 信息
        
        Returns:
            Agent 信息字典
        """
        return {
            "type": self.AGENT_TYPE,
            "model": self.model_name,
            "base_url": self.base_url,
            "max_steps": self.max_steps,
            "device_id": self.device_id,
            "lang": self.lang
        }
    
    def _convert_context_to_history(self) -> list:
        """
        将 PhoneAgent 的 context 转换为 history 格式
        
        Returns:
            简化的历史记录列表
        """
        # PhoneAgent 的 context 是消息列表
        # 转换为简化的 history 格式
        history = []
        for msg in self.phone_agent.context:
            role = msg.get("role")
            content = msg.get("content")
            
            # 处理不同类型的 content
            if isinstance(content, str):
                history.append({
                    "role": role,
                    "content": content
                })
            elif isinstance(content, list):
                # 提取文本内容（忽略图片）
                text_parts = [
                    item.get("text", "") 
                    for item in content 
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                if text_parts:
                    history.append({
                        "role": role,
                        "content": " ".join(text_parts)
                    })
        
        return history
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'PhoneAgentWrapper':
        """
        从配置字典创建实例
        
        Args:
            config: 配置字典
            
        Returns:
            PhoneAgentWrapper 实例
        """
        return cls(
            api_key=config['api_key'],
            base_url=config['base_url'],
            model_name=config.get('model_name', 'gpt-4-vision-preview'),
            max_steps=config.get('max_steps', 50),
            device_id=config.get('device_id'),
            lang=config.get('lang', 'cn'),
            verbose=config.get('verbose', True),
            confirmation_callback=config.get('confirmation_callback'),
            takeover_callback=config.get('takeover_callback'),
            **config.get('extra', {})
        )
    
    def __repr__(self) -> str:
        return (
            f"PhoneAgentWrapper(model={self.model_name}, "
            f"max_steps={self.max_steps}, "
            f"device_id={self.device_id}, "
            f"lang={self.lang})"
        )
