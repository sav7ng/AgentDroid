"""
TraceID 上下文管理模块 - 使用 contextvars 管理请求追踪ID

功能：
1. 生成唯一的 TraceID (UUID)
2. 在异步上下文中存储和获取 TraceID
3. 线程安全、协程安全
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# 创建上下文变量存储 TraceID
_trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


def generate_trace_id() -> str:
    """
    生成唯一的 TraceID
    
    Returns:
        str: UUID 格式的 TraceID
        
    Example:
        >>> trace_id = generate_trace_id()
        >>> print(trace_id)
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    return str(uuid.uuid4())


def set_trace_id(trace_id: str) -> None:
    """
    设置当前上下文的 TraceID
    
    Args:
        trace_id: 要设置的 TraceID
        
    Example:
        >>> set_trace_id('my-custom-trace-id')
    """
    _trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """
    获取当前上下文的 TraceID
    
    Returns:
        Optional[str]: 当前的 TraceID，如果未设置则返回 None
        
    Example:
        >>> trace_id = get_trace_id()
        >>> if trace_id:
        ...     print(f"当前 TraceID: {trace_id}")
    """
    return _trace_id_var.get()


def clear_trace_id() -> None:
    """
    清除当前上下文的 TraceID
    
    Example:
        >>> clear_trace_id()
    """
    _trace_id_var.set(None)


def get_or_generate_trace_id() -> str:
    """
    获取当前 TraceID，如果不存在则生成新的
    
    Returns:
        str: TraceID
        
    Example:
        >>> trace_id = get_or_generate_trace_id()
    """
    trace_id = get_trace_id()
    if trace_id is None:
        trace_id = generate_trace_id()
        set_trace_id(trace_id)
    return trace_id
