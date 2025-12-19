"""
Agent 工厂类

提供统一的 Agent 创建接口，支持多种 Agent 类型的注册和实例化。
"""

from typing import Dict, Any, Type
from core.logger import get_logger

logger = get_logger(__name__)


class AgentFactory:
    """
    Agent 工厂类
    
    职责：
    - 管理已注册的 Agent 类型
    - 根据配置创建 Agent 实例
    - 提供 Agent 类型查询功能
    """
    
    # 已注册的 Agent 类型映射 {agent_type: AgentClass}
    _agents: Dict[str, Type] = {}
    
    @classmethod
    def register_agent(cls, agent_type: str, agent_class: Type) -> None:
        """
        注册新的 Agent 类型
        
        Args:
            agent_type: Agent 类型标识（如 "mobile-use-agent"）
            agent_class: Agent 类
            
        Example:
            AgentFactory.register_agent("custom-agent", CustomAgent)
        """
        if agent_type in cls._agents:
            logger.warning(
                f"Agent 类型 '{agent_type}' 已存在，将被覆盖",
                extra={"agent_type": agent_type}
            )
        
        cls._agents[agent_type] = agent_class
        logger.info(
            f"成功注册 Agent 类型: {agent_type}",
            extra={"agent_type": agent_type, "agent_class": agent_class.__name__}
        )
    
    @classmethod
    def create_agent(cls, agent_type: str, config: Dict[str, Any]):
        """
        创建 Agent 实例
        
        Args:
            agent_type: Agent 类型（如 "mobile-use-agent"）
            config: Agent 配置字典，包含：
                - api_key: API 密钥
                - base_url: API 基础 URL
                - model_name: 模型名称
                - max_steps: 最大步数
                - 其他配置参数
            
        Returns:
            Agent 实例
            
        Raises:
            ValueError: 不支持的 agent_type
            
        Example:
            agent = AgentFactory.create_agent(
                "mobile-use-agent",
                {
                    "api_key": "xxx",
                    "base_url": "http://xxx",
                    "model_name": "gui-owl",
                    "max_steps": 50
                }
            )
        """
        if agent_type not in cls._agents:
            available_types = list(cls._agents.keys())
            error_msg = (
                f"不支持的 agent_type: '{agent_type}'. "
                f"可用类型: {available_types}"
            )
            logger.error(error_msg, extra={"agent_type": agent_type})
            raise ValueError(error_msg)
        
        agent_class = cls._agents[agent_type]
        
        logger.info(
            f"创建 Agent 实例: {agent_type}",
            extra={
                "agent_type": agent_type,
                "agent_class": agent_class.__name__,
                "model": config.get('model_name', 'N/A')
            }
        )
        
        try:
            # 创建 Agent 实例
            agent = agent_class(**config)
            return agent
        except Exception as e:
            error_msg = f"创建 Agent 失败: {str(e)}"
            logger.error(
                error_msg,
                extra={"agent_type": agent_type, "error": str(e)},
                exc_info=True
            )
            raise ValueError(error_msg) from e
    
    @classmethod
    def list_agents(cls) -> list:
        """
        列出所有已注册的 Agent 类型
        
        Returns:
            Agent 类型列表
        """
        return list(cls._agents.keys())
    
    @classmethod
    def is_registered(cls, agent_type: str) -> bool:
        """
        检查 Agent 类型是否已注册
        
        Args:
            agent_type: Agent 类型
            
        Returns:
            是否已注册
        """
        return agent_type in cls._agents
    
    @classmethod
    def get_agent_class(cls, agent_type: str) -> Type:
        """
        获取 Agent 类
        
        Args:
            agent_type: Agent 类型
            
        Returns:
            Agent 类
            
        Raises:
            ValueError: 不支持的 agent_type
        """
        if agent_type not in cls._agents:
            raise ValueError(f"不支持的 agent_type: '{agent_type}'")
        return cls._agents[agent_type]


# 自动注册内置的 Mobile-Use-Agent
from agents.mobile_use_agent import MobileUseAgent

AgentFactory.register_agent("mobile-use-agent", MobileUseAgent)

logger.info("Agent 工厂初始化完成", extra={"registered_agents": AgentFactory.list_agents()})
