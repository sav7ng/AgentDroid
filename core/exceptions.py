"""
自定义异常模块 - 定义业务异常类

功能：
1. 统一的异常基类
2. 预定义的业务异常类型
3. 统一的错误码体系
"""

from typing import Optional, Dict, Any


class BaseBusinessException(Exception):
    """
    业务异常基类
    
    Attributes:
        code: 错误码
        message: 错误消息
        details: 额外的错误详情
        status_code: HTTP 状态码
    """
    
    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        """
        初始化业务异常
        
        Args:
            message: 错误消息
            code: 错误码
            details: 额外的错误详情
            status_code: HTTP 状态码
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将异常转换为字典格式
        
        Returns:
            Dict[str, Any]: 异常信息字典
        """
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class TaskNotFoundException(BaseBusinessException):
    """任务未找到异常"""
    
    def __init__(self, task_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"任务未找到: {task_id}"
        super().__init__(
            message=message,
            code="TASK_NOT_FOUND",
            details=details or {"task_id": task_id},
            status_code=404
        )


class TaskBusyException(BaseBusinessException):
    """任务繁忙异常 - 已有任务在执行"""
    
    def __init__(self, message: str = "已有任务在执行，请等待上一个任务完成", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="TASK_BUSY",
            details=details,
            status_code=429
        )


class DeviceConnectionException(BaseBusinessException):
    """设备连接异常"""
    
    def __init__(self, message: str = "无法连接到 ADB 设备", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DEVICE_CONNECTION_ERROR",
            details=details,
            status_code=503
        )


class APICallException(BaseBusinessException):
    """API 调用异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"API 调用失败: {message}",
            code="API_CALL_ERROR",
            details=details,
            status_code=502
        )


class ScreenshotException(BaseBusinessException):
    """截图异常"""
    
    def __init__(self, message: str = "截图失败", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="SCREENSHOT_ERROR",
            details=details,
            status_code=500
        )


class ActionExecutionException(BaseBusinessException):
    """动作执行异常"""
    
    def __init__(self, action: str, message: str, details: Optional[Dict[str, Any]] = None):
        full_message = f"动作执行失败 [{action}]: {message}"
        super().__init__(
            message=full_message,
            code="ACTION_EXECUTION_ERROR",
            details=details or {"action": action},
            status_code=500
        )


class ValidationException(BaseBusinessException):
    """参数验证异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=400
        )
