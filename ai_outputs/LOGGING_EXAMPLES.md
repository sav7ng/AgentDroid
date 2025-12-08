# 日志系统快速使用示例

## 基本用法

### 1. 导入并使用日志

```python
from core.logger import get_logger

logger = get_logger(__name__)

# 基础日志
logger.info("任务开始执行")
logger.warning("检测到潜在问题")
logger.error("执行失败")

# 带额外信息的日志（推荐）
logger.info("任务完成", extra={
    "task_id": "abc-123",
    "duration": 5.2,
    "status": "success"
})
```

### 2. 使用自定义异常

```python
from core.exceptions import TaskBusyException, APICallException

# 抛出异常（会被全局异常处理器捕获）
if is_task_running:
    raise TaskBusyException()

# 带详细信息
raise APICallException(
    message="API timeout",
    details={"timeout": 30, "endpoint": "/v1/chat"}
)
```

### 3. TraceID 自动追踪

所有 HTTP 请求会自动生成 TraceID，在响应头中返回：

```bash
# 响应头
X-Trace-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
X-Request-Duration: 0.123s
```

### 4. 手动设置 TraceID（后台任务）

```python
from core.trace_context import set_trace_id

# 在后台任务中设置 TraceID
task_id = str(uuid.uuid4())
set_trace_id(task_id)

# 后续日志都会包含这个 trace_id
logger.info("后台任务开始", extra={"task_id": task_id})
```

## 日志输出示例

### JSON 格式日志

```json
{
  "timestamp": "2025-12-08T17:56:18.375+08:00",
  "level": "INFO",
  "trace_id": "578c751d-2d1f-4f1f-b141-447e7a135d3f",
  "module": "main",
  "function": "run_agent_async_endpoint",
  "line": 245,
  "message": "任务已接受，准备后台执行",
  "extra": {
    "task_id": "xyz-123",
    "instruction": "打开支付宝"
  }
}
```

### 异常日志（包含堆栈）

```json
{
  "timestamp": "2025-12-08T17:56:18.404+08:00",
  "level": "ERROR",
  "trace_id": "578c751d-2d1f-4f1f-b141-447e7a135d3f",
  "module": "agent_core",
  "function": "capture_screenshot",
  "line": 95,
  "message": "截图失败",
  "extra": {"error": "ADB device not found"},
  "exception": "Traceback (most recent call last):\n  File..."
}
```

## 环境变量配置

创建 `.env` 文件：

```bash
# 日志级别
LOG_LEVEL=INFO

# 日志文件（可选）
LOG_FILE_PATH=./logs/agent.log

# 调试模式
DEBUG_MODE=false
```

## 常用查询

```bash
# 查询特定 trace_id 的日志
cat logs/agent.log | jq 'select(.trace_id == "your-trace-id")'

# 查询错误日志
cat logs/agent.log | jq 'select(.level == "ERROR")'

# 查询特定时间段
cat logs/agent.log | jq 'select(.timestamp >= "2025-12-08T17:00:00")'
```

完整文档请参考 [LOGGING_README.md](LOGGING_README.md)
