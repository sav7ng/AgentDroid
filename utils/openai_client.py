"""
通用 OpenAI 客户端模块
提供可配置的 OpenAI API 调用方法（同步和流式）
"""

from openai import OpenAI
from core.logger import get_logger
from typing import Optional, Generator, Dict, Any

logger = get_logger(__name__)


class OpenAIClient:
    """可配置的 OpenAI 客户端"""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        """
        初始化 OpenAI 客户端
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        
        logger.info(
            "初始化 OpenAI 客户端",
            extra={"model": model, "base_url": base_url}
        )
        
    def chat_completion(self, messages: list, **kwargs) -> str:
        """
        同步调用聊天完成接口
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数传递给 API
            
        Returns:
            str: 模型响应内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            
            content = response.choices[0].message.content
            
            logger.debug(
                "同步调用完成",
                extra={
                    "model": self.model,
                    "response_length": len(content)
                }
            )
            
            return content
            
        except Exception as e:
            logger.error(
                "同步调用失败",
                extra={"model": self.model, "error": str(e)},
                exc_info=True
            )
            raise
    
    def chat_completion_stream(
        self, 
        messages: list, 
        **kwargs
    ) -> Generator[str, None, None]:
        """
        流式调用聊天完成接口
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数传递给 API
            
        Yields:
            str: 模型响应内容片段
        """
        try:
            logger.debug(
                "开始流式调用",
                extra={"model": self.model, "messages_count": len(messages)}
            )
            
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )
            
            total_chunks = 0
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        total_chunks += 1
                        yield delta.content
            
            logger.debug(
                "流式调用完成",
                extra={"model": self.model, "total_chunks": total_chunks}
            )
            
        except Exception as e:
            logger.error(
                "流式调用失败",
                extra={"model": self.model, "error": str(e)},
                exc_info=True
            )
            raise
