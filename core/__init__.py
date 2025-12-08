"""
Core module - 核心基础设施模块
包含日志、上下文、异常等核心功能
"""

from .logger import get_logger, LoggerManager
from .trace_context import get_trace_id, set_trace_id, generate_trace_id
from .exceptions import (
    BaseBusinessException,
    TaskNotFoundException,
    TaskBusyException,
    DeviceConnectionException,
    APICallException
)

__all__ = [
    'get_logger',
    'LoggerManager',
    'get_trace_id',
    'set_trace_id',
    'generate_trace_id',
    'BaseBusinessException',
    'TaskNotFoundException',
    'TaskBusyException',
    'DeviceConnectionException',
    'APICallException'
]
