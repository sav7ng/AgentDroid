"""
日志系统测试脚本
用于验证日志功能是否正常工作
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logger import get_logger
from core.trace_context import set_trace_id, get_trace_id, generate_trace_id
from core.exceptions import (
    TaskBusyException,
    DeviceConnectionException,
    APICallException
)

def test_basic_logging():
    """测试基础日志功能"""
    print("=" * 60)
    print("测试 1: 基础日志功能")
    print("=" * 60)
    
    logger = get_logger(__name__)
    
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")
    
    print("✅ 基础日志测试通过\n")


def test_structured_logging():
    """测试结构化日志"""
    print("=" * 60)
    print("测试 2: 结构化日志（带 extra 字段）")
    print("=" * 60)
    
    logger = get_logger(__name__)
    
    logger.info(
        "用户登录成功",
        extra={
            "user_id": 12345,
            "username": "test_user",
            "ip": "192.168.1.1"
        }
    )
    
    logger.warning(
        "API 调用速率接近限制",
        extra={
            "current_rate": 95,
            "limit": 100,
            "endpoint": "/run-agent"
        }
    )
    
    print("✅ 结构化日志测试通过\n")


def test_trace_context():
    """测试 TraceID 上下文"""
    print("=" * 60)
    print("测试 3: TraceID 上下文管理")
    print("=" * 60)
    
    logger = get_logger(__name__)
    
    # 生成并设置 TraceID
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    
    print(f"生成的 TraceID: {trace_id}")
    
    # 验证 TraceID 已设置
    current_trace_id = get_trace_id()
    assert current_trace_id == trace_id, "TraceID 不匹配"
    
    # 记录带 TraceID 的日志
    logger.info("这条日志应该包含 TraceID", extra={"test": "trace_context"})
    
    print("✅ TraceID 上下文测试通过\n")


def test_exception_logging():
    """测试异常日志"""
    print("=" * 60)
    print("测试 4: 异常日志记录")
    print("=" * 60)
    
    logger = get_logger(__name__)
    
    # 测试带堆栈的异常日志
    try:
        # 模拟一个异常
        result = 1 / 0
    except Exception as e:
        logger.error(
            "捕获到除零错误",
            extra={"operation": "division"},
            exc_info=True
        )
    
    print("✅ 异常日志测试通过\n")


def test_custom_exceptions():
    """测试自定义异常"""
    print("=" * 60)
    print("测试 5: 自定义异常类")
    print("=" * 60)
    
    # 测试 TaskBusyException
    try:
        raise TaskBusyException()
    except TaskBusyException as e:
        print(f"TaskBusyException: {e.message}")
        print(f"错误码: {e.code}")
        print(f"状态码: {e.status_code}")
        assert e.code == "TASK_BUSY"
        assert e.status_code == 429
    
    # 测试 APICallException
    try:
        raise APICallException(
            message="OpenAI API timeout",
            details={"timeout": 30, "model": "gpt-4"}
        )
    except APICallException as e:
        print(f"\nAPICallException: {e.message}")
        print(f"详情: {e.details}")
        assert e.code == "API_CALL_ERROR"
        assert e.status_code == 502
    
    print("\n✅ 自定义异常测试通过\n")


def test_different_log_levels():
    """测试不同日志级别"""
    print("=" * 60)
    print("测试 6: 不同日志级别")
    print("=" * 60)
    
    logger = get_logger(__name__)
    
    logger.debug("调试信息 - 详细的内部状态")
    logger.info("信息日志 - 关键业务节点")
    logger.warning("警告日志 - 需要注意但不影响主流程")
    logger.error("错误日志 - 影响功能的错误")
    logger.critical("严重错误 - 可能导致系统崩溃")
    
    print("✅ 日志级别测试通过\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试日志系统")
    print("=" * 60 + "\n")
    
    try:
        test_basic_logging()
        test_structured_logging()
        test_trace_context()
        test_exception_logging()
        test_custom_exceptions()
        test_different_log_levels()
        
        print("=" * 60)
        print("✅ 所有测试通过！日志系统运行正常")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
