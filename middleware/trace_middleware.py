"""
TraceID 中间件 - 为每个请求生成和管理 TraceID

功能：
1. 为每个请求生成唯一的 TraceID
2. 在响应头中返回 TraceID
3. 记录请求和响应信息
4. 自动注入到日志上下文中
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.trace_context import generate_trace_id, set_trace_id, get_trace_id
from core.logger import get_logger

logger = get_logger(__name__)


class TraceMiddleware(BaseHTTPMiddleware):
    """TraceID 中间件 - 为每个 HTTP 请求生成和管理 TraceID"""
    
    def __init__(self, app: ASGIApp):
        """
        初始化 TraceID 中间件
        
        Args:
            app: ASGI 应用实例
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，注入 TraceID 并记录请求/响应信息
        
        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器
            
        Returns:
            Response: HTTP 响应
        """
        # 生成或获取 TraceID（支持从请求头传入）
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        set_trace_id(trace_id)
        
        # 记录请求开始时间
        start_time = time.time()
        
        # 记录请求信息
        logger.info(
            f"请求开始: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        )
        
        # 处理请求
        try:
            response = await call_next(request)
        except Exception as e:
            # 如果出现异常，记录并重新抛出（由异常处理器处理）
            duration = time.time() - start_time
            logger.error(
                f"请求处理异常: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration": f"{duration:.3f}s",
                    "error": str(e),
                },
                exc_info=True
            )
            raise
        
        # 计算请求处理时间
        duration = time.time() - start_time
        
        # 在响应头中添加 TraceID
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-Duration"] = f"{duration:.3f}s"
        
        # 记录响应信息
        logger.info(
            f"请求完成: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": f"{duration:.3f}s",
            }
        )
        
        return response
