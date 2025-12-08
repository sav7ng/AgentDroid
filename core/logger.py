"""
日志管理器模块 - 提供统一的日志记录功能

功能：
1. 支持 JSON 格式日志输出
2. 自动注入 TraceID
3. 支持控制台和文件输出
4. 日志轮转功能
5. 提供便捷的日志接口
"""

import logging
import sys
import json
from datetime import datetime
from typing import Optional, Any, Dict
from logging.handlers import RotatingFileHandler
import os

from .trace_context import get_trace_id


class TextFormatter(logging.Formatter):
    """文本格式化器 - 将日志输出为易读的文本格式"""
    
    # 日志级别对应的颜色代码（ANSI）
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def __init__(self, use_color: bool = True):
        """
        初始化文本格式化器
        
        Args:
            use_color: 是否使用颜色输出
        """
        super().__init__()
        self.use_color = use_color
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为文本"""
        
        # 时间戳
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # 日志级别（8个字符对齐）
        level = record.levelname.ljust(8)
        if self.use_color:
            level = f"{self.COLORS.get(record.levelname, '')}{level}{self.RESET}"
        
        # TraceID（取前8位，如果没有则显示 --------）
        trace_id = get_trace_id()
        trace_id_short = trace_id[:8] if trace_id else "--------"
        
        # 模块和行号
        location = f"{record.name}:{record.lineno}"
        
        # 消息
        message = record.getMessage()
        
        # 构建基本日志行
        log_line = f"{timestamp} | {level} | [{trace_id_short}] | {location} - {message}"
        
        # 添加额外信息
        if hasattr(record, 'extra_data') and record.extra_data:
            extra_parts = [f"{k}={v}" for k, v in record.extra_data.items()]
            log_line += " | " + " | ".join(extra_parts)
        
        # 添加异常信息
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)
        
        # 添加堆栈信息
        if record.stack_info:
            log_line += "\n" + self.formatStack(record.stack_info)
        
        return log_line


class JSONFormatter(logging.Formatter):
    """JSON 格式化器 - 将日志输出为 JSON 格式"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON"""
        
        # 基础日志字段
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).astimezone().isoformat(),
            "level": record.levelname,
            "trace_id": get_trace_id(),
            "module": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        
        # 添加额外的上下文信息
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data["extra"] = record.extra_data
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加堆栈信息
        if record.stack_info:
            log_data["stack_info"] = self.formatStack(record.stack_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ContextAdapter(logging.LoggerAdapter):
    """日志适配器 - 用于添加额外的上下文信息"""
    
    def process(self, msg, kwargs):
        """处理日志消息，添加额外信息"""
        # 从 kwargs 中提取 extra 参数
        extra = kwargs.get('extra', {})
        
        # 将 extra 作为自定义属性添加到 LogRecord
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['extra_data'] = extra.copy() if extra else None
        
        return msg, kwargs


class LoggerManager:
    """日志管理器 - 单例模式，管理全局日志配置"""
    
    _instance: Optional['LoggerManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志管理器"""
        if self._initialized:
            return
        
        # 从环境变量读取配置
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_format = os.getenv('LOG_FORMAT', 'text').lower()  # text, json, color
        self.log_file_path = os.getenv('LOG_FILE_PATH', None)
        self.log_max_bytes = int(os.getenv('LOG_MAX_BYTES', 10 * 1024 * 1024))  # 默认 10MB
        self.log_backup_count = int(os.getenv('LOG_BACKUP_COUNT', 5))  # 默认保留 5 个文件
        self.enable_console = os.getenv('LOG_ENABLE_CONSOLE', 'true').lower() == 'true'
        
        # 配置根日志记录器
        self._configure_root_logger()
        
        self._initialized = True
    
    def _configure_root_logger(self):
        """配置根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有的处理器
        root_logger.handlers.clear()
        
        # 根据配置选择格式化器
        if self.log_format == 'json':
            # JSON 格式（用于日志收集和分析）
            console_formatter = JSONFormatter()
            file_formatter = JSONFormatter()
        elif self.log_format == 'color':
            # 彩色文本格式（用于控制台）
            console_formatter = TextFormatter(use_color=True)
            file_formatter = TextFormatter(use_color=False)  # 文件不使用颜色
        else:  # 'text' 或其他
            # 纯文本格式（默认）
            console_formatter = TextFormatter(use_color=False)
            file_formatter = TextFormatter(use_color=False)
        
        # 添加控制台处理器
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # 添加文件处理器（如果配置了文件路径）
        if self.log_file_path:
            # 确保日志目录存在
            log_dir = os.path.dirname(self.log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                self.log_file_path,
                maxBytes=self.log_max_bytes,
                backupCount=self.log_backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> ContextAdapter:
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称，通常使用 __name__
            
        Returns:
            ContextAdapter: 日志适配器实例
        """
        logger = logging.getLogger(name)
        return ContextAdapter(logger, {})
    
    def set_level(self, level: str):
        """
        动态设置日志级别
        
        Args:
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        level = level.upper()
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            handler.setLevel(level)
        self.log_level = level


# 全局日志管理器实例
_logger_manager = LoggerManager()


def get_logger(name: str = None) -> ContextAdapter:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称，如果为 None 则使用调用者的模块名
        
    Returns:
        ContextAdapter: 日志适配器实例
        
    Example:
        >>> from core.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条日志")
        >>> logger.info("带额外信息的日志", extra={"user_id": 123, "action": "login"})
        >>> logger.error("发生错误", exc_info=True)
    """
    if name is None:
        # 获取调用者的模块名
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'root')
    
    return _logger_manager.get_logger(name)


def set_log_level(level: str):
    """
    设置全局日志级别的便捷函数
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Example:
        >>> from core.logger import set_log_level
        >>> set_log_level('DEBUG')
    """
    _logger_manager.set_level(level)
