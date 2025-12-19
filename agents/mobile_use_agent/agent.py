"""
Mobile-Use-Agent 实现

包装现有的 agent_core.py 功能，提供统一的 Agent 接口。
"""

from typing import Dict, Optional, Any, Generator
import asyncio
from agent_core import run_mobile_agent, run_mobile_agent_stream


class MobileUseAgent:
    """
    Mobile-Use-Agent 统一接口（包装现有实现）
    
    特性：
    - 支持多种 LLM 提供商（通过 base_url 切换）
    - 保持与 agent_core.py 的兼容性
    - 提供统一的配置管理
    """
    
    AGENT_TYPE = "mobile-use-agent"
    
    def __init__(self, 
                 api_key: str,
                 base_url: str,
                 model_name: str = "gui-owl",
                 max_steps: int = 50,
                 output_dir: str = "agent_outputs",
                 **kwargs):
        """
        初始化 Mobile-Use-Agent
        
        Args:
            api_key: LLM API 密钥
            base_url: LLM API 基础 URL
            model_name: 模型名称
            max_steps: 最大执行步数
            output_dir: 输出目录
            **kwargs: 其他配置参数
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.max_steps = max_steps
        self.output_dir = output_dir
        self.config = kwargs
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取 Agent 信息"""
        return {
            "type": self.AGENT_TYPE,
            "model": self.model_name,
            "base_url": self.base_url,
            "max_steps": self.max_steps
        }
    
    async def run(self, instruction: str, **kwargs) -> Dict[str, Any]:
        """
        同步执行任务（包装 run_mobile_agent）
        
        Args:
            instruction: 用户指令
            **kwargs: 覆盖配置参数
            
        Returns:
            执行结果字典，包含：
            - status: 执行状态
            - history: 执行历史
            - agent_type: Agent 类型标识
        """
        max_steps = kwargs.get('max_steps', self.max_steps)
        
        # 在线程池中执行同步函数
        result = await asyncio.to_thread(
            run_mobile_agent,
            instruction=instruction,
            max_steps=max_steps,
            api_key=self.api_key,
            base_url=self.base_url,
            model_name=self.model_name
        )
        
        # 添加 agent_type 标识
        result['agent_type'] = self.AGENT_TYPE
        return result
    
    def run_stream(self, instruction: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        流式执行任务（包装 run_mobile_agent_stream）
        
        Args:
            instruction: 用户指令
            **kwargs: 覆盖配置参数
            
        Yields:
            事件字典，包含：
            - event_type: 事件类型
            - data: 事件数据
            - agent_type: Agent 类型标识
        """
        max_steps = kwargs.get('max_steps', self.max_steps)
        output_dir = kwargs.get('output_dir', self.output_dir)
        task_id = kwargs.get('task_id')
        
        # 直接调用现有的流式函数（生成器）
        for event in run_mobile_agent_stream(
            instruction=instruction,
            max_steps=max_steps,
            api_key=self.api_key,
            base_url=self.base_url,
            model_name=self.model_name,
            output_dir=output_dir,
            task_id=task_id
        ):
            # 添加 agent_type 标识
            event['agent_type'] = self.AGENT_TYPE
            yield event
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'MobileUseAgent':
        """
        从配置字典创建实例
        
        Args:
            config: 配置字典
            
        Returns:
            MobileUseAgent 实例
        """
        return cls(
            api_key=config['api_key'],
            base_url=config['base_url'],
            model_name=config.get('model_name', 'gui-owl'),
            max_steps=config.get('max_steps', 50),
            output_dir=config.get('output_dir', 'agent_outputs'),
            **config.get('extra', {})
        )
    
    def __repr__(self) -> str:
        return (
            f"MobileUseAgent(model={self.model_name}, "
            f"max_steps={self.max_steps}, "
            f"base_url={self.base_url})"
        )
