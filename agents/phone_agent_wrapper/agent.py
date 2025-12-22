"""
PhoneAgent 适配器类

包装 phone_agent.PhoneAgent，实现与 MobileUseAgent 统一的接口。
"""

from typing import Dict, Any, Generator, Optional, Callable
import asyncio
import uuid
import sys
import traceback
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
                 enable_takeover: bool = True,
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
            enable_takeover: 是否启用 Take_over 动作（False 则遇到 Take_over 时直接终止任务）
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
            verbose=verbose,
            enable_takeover=enable_takeover
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
        
        # 用于记录每个步骤的动作历史
        self.actions_history = []
    
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
            - history: 执行历史（动作列表）
            - agent_type: Agent 类型标识
        """
        # 重置动作历史
        self.actions_history = []
        
        try:
            # 重置 Agent 状态
            self.phone_agent.reset()
            
            # 执行首步
            result = await asyncio.to_thread(
                self.phone_agent.step,
                instruction
            )
            
            # 记录动作
            if result.action:
                self.actions_history.append(result.action)
            
            # 如果任务完成，直接返回
            if result.finished:
                return {
                    "status": "success" if result.success else "error",
                    "message": result.message or "Task completed",
                    "history": self.actions_history,
                    "agent_type": self.AGENT_TYPE
                }
            
            # 继续执行后续步骤
            step_count = 2
            while step_count <= self.max_steps:
                result = await asyncio.to_thread(
                    self.phone_agent.step
                )
                
                # 记录动作
                if result.action:
                    self.actions_history.append(result.action)
                
                if result.finished:
                    return {
                        "status": "success" if result.success else "error",
                        "message": result.message or "Task completed",
                        "history": self.actions_history,
                        "agent_type": self.AGENT_TYPE
                    }
                
                step_count += 1
            
            # 达到最大步数
            return {
                "status": "error",
                "message": f"达到最大步数限制 ({self.max_steps})，任务可能未完成",
                "history": self.actions_history,
                "agent_type": self.AGENT_TYPE
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "history": self.actions_history,
                "agent_type": self.AGENT_TYPE
            }
    
    def stream_run(self, instruction: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式执行任务（适配 MobileUseAgent 接口）
        
        Args:
            instruction: 用户指令
            **kwargs: 覆盖配置参数
            
        Yields:
            执行事件流，包括：
            - task_init: 任务初始化
            - step_completed: 步骤完成
            - task_completed: 任务完成
            - task_error: 任务错误
        """
        task_id = kwargs.get('task_id') or str(uuid.uuid4())[:8]
        
        # 重置动作历史
        self.actions_history = []
        
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
            
            # 记录动作
            if result.action:
                self.actions_history.append(result.action)
            
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
                        "message": result.message,
                        "history": self.actions_history
                    }
                }
                return
                
        except Exception as e:
            yield {
                "event_type": "task_error",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "agent_type": self.AGENT_TYPE,
                "data": {
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            }
            return
            
        # 4. 继续执行后续步骤
        step_count = 2
        while step_count <= self.max_steps:
            try:
                result = self.phone_agent.step()
                
                # 记录动作
                if result.action:
                    self.actions_history.append(result.action)
                
                yield {
                    "event_type": "step_completed",
                    "task_id": task_id,
                    "step": step_count,
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
                            "message": result.message,
                            "history": self.actions_history
                        }
                    }
                    return
                    
            except Exception as e:
                yield {
                    "event_type": "task_error",
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": self.AGENT_TYPE,
                    "data": {
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                }
                return
                
            step_count += 1
            
        # 5. 达到最大步数仍未完成
        yield {
            "event_type": "task_completed",
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "agent_type": self.AGENT_TYPE,
            "data": {
                "message": f"达到最大步数限制 ({self.max_steps})，任务可能未完成",
                "history": self.actions_history
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
            "max_steps": self.max_steps,
            "device_id": self.device_id,
            "lang": self.lang,
            "output_dir": self.output_dir
        }
    
    def _extract_history(self, messages: list) -> list:
        """
        从完整消息历史中提取用户友好的历史记录
        
        Args:
            messages: 完整的消息历史
            
        Returns:
            用户友好的历史记录列表
        """
        history = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            # 只保留用户和助手的消息
            if role not in ["user", "assistant"]:
                continue
                
            # 处理文本内容
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
            enable_takeover=config.get('enable_takeover', True),
            **config.get('extra', {})
        )
    
    def __repr__(self) -> str:
        return (
            f"PhoneAgentWrapper(model={self.model_name}, "
            f"max_steps={self.max_steps}, "
            f"device_id={self.device_id}, "
            f"lang={self.lang})"
        )
