"""
全局异常处理器 - 统一处理应用中的异常

功能：
1. 捕获并处理自定义业务异常
2. 捕获并处理 HTTP 异常
3. 捕获并处理未预期的异常
4. 返回统一格式的错误响应
5. 自动记录异常日志
"""

from datetime import datetime
from typing import Union
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.exceptions import BaseBusinessException
from core.trace_context import get_trace_id
from core.logger import get_logger

logger = get_logger(__name__)


class ExceptionResponse:
    """统一的异常响应格式"""
    
    @staticmethod
    def create(
        code: str,
        message: str,
        status_code: int = 500,
        details: dict = None,
        trace_id: str = None
    ) -> dict:
        """
        创建统一的错误响应
        
        Args:
            code: 错误码
            message: 错误消息
            status_code: HTTP 状态码
            details: 额外的错误详情
            trace_id: 追踪ID
            
        Returns:
            dict: 错误响应字典
        """
        response = {
            "code": code,
            "message": message,
            "trace_id": trace_id or get_trace_id(),
            "timestamp": datetime.now().astimezone().isoformat(),
        }
        
        if details:
            response["details"] = details
        
        return response


async def business_exception_handler(request: Request, exc: BaseBusinessException) -> JSONResponse:
    """
    处理业务异常
    
    Args:
        request: FastAPI 请求对象
        exc: 业务异常实例
        
    Returns:
        JSONResponse: JSON 格式的错误响应
    """
    # 记录业务异常日志
    logger.warning(
        f"业务异常: {exc.message}",
        extra={
            "exception_type": exc.__class__.__name__,
            "code": exc.code,
            "details": exc.details,
            "path": request.url.path,
        }
    )
    
    # 返回统一格式的错误响应
    response_data = ExceptionResponse.create(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_data
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    处理 HTTP 异常
    
    Args:
        request: FastAPI 请求对象
        exc: HTTP 异常实例
        
    Returns:
        JSONResponse: JSON 格式的错误响应
    """
    # 记录 HTTP 异常日志
    logger.warning(
        f"HTTP 异常: {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
        }
    )
    
    # 返回统一格式的错误响应
    response_data = ExceptionResponse.create(
        code="HTTP_ERROR",
        message=str(exc.detail),
        status_code=exc.status_code
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_data
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    处理请求参数验证异常
    
    Args:
        request: FastAPI 请求对象
        exc: 请求验证异常实例
        
    Returns:
        JSONResponse: JSON 格式的错误响应
    """
    # 提取验证错误信息
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    # 记录验证异常日志
    logger.warning(
        "请求参数验证失败",
        extra={
            "path": request.url.path,
            "errors": errors,
        }
    )
    
    # 返回统一格式的错误响应
    response_data = ExceptionResponse.create(
        code="VALIDATION_ERROR",
        message="请求参数验证失败",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": errors}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_data
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    处理未预期的通用异常
    
    Args:
        request: FastAPI 请求对象
        exc: 异常实例
        
    Returns:
        JSONResponse: JSON 格式的错误响应
    """
    # 记录未预期的异常日志（包含堆栈信息）
    logger.error(
        f"未预期的异常: {str(exc)}",
        extra={
            "exception_type": exc.__class__.__name__,
            "path": request.url.path,
        },
        exc_info=True
    )
    
    # 返回统一格式的错误响应（不暴露内部错误详情）
    response_data = ExceptionResponse.create(
        code="INTERNAL_SERVER_ERROR",
        message="服务器内部错误，请稍后重试",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={"error_type": exc.__class__.__name__}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_data
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    为 FastAPI 应用配置全局异常处理器
    
    Args:
        app: FastAPI 应用实例
        
    Example:
        >>> from fastapi import FastAPI
        >>> from middleware.exception_handler import setup_exception_handlers
        >>> 
        >>> app = FastAPI()
        >>> setup_exception_handlers(app)
    """
    # 注册业务异常处理器
    app.add_exception_handler(BaseBusinessException, business_exception_handler)
    
    # 注册 HTTP 异常处理器
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # 注册请求验证异常处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # 注册通用异常处理器（捕获所有未处理的异常）
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("全局异常处理器已配置")
