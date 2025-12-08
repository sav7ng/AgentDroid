# 日志系统使用文档

## 📋 概述

本项目集成了完整的日志打印模块，包含以下核心功能：

- ✅ **TraceID 追踪** - 为每个请求生成唯一的追踪ID，贯穿整个请求生命周期
- ✅ **多种格式输出** - 支持文本格式（默认）、彩色文本、JSON格式
- ✅ **统一异常处理** - 自动捕获并记录异常，返回规范的错误响应
- ✅ **请求/响应日志** - 自动记录所有 API 请求和响应信息
- ✅ **灵活配置** - 支持通过环境变量配置日志行为

---

## 🏗️ 架构设计

### 目录结构

```
AgentDroid/
├── core/                      # 核心模块
│   ├── logger.py             # 日志管理器
│   ├── trace_context.py      # TraceID 上下文管理
│   └── exceptions.py         # 自定义异常类
├── middleware/                # 中间件
│   ├── trace_middleware.py   # TraceID 中间件
│   └── exception_handler.py  # 全局异常处理器
└── ...
```

---

## 🚀 快速开始

### 1. 在代码中使用日志

```python
from core.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 基础日志
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")

# 带额外信息的日志（推荐）
logger.info(
    "用户登录成功",
    extra={
        "user_id": 12345,
        "username": "john",
        "ip": "192.168.1.1"
    }
)

# 记录异常（包含堆栈信息）
try:
    # 一些可能出错的代码
    result = risky_operation()
except Exception as e:
    logger.error("操作失败", exc_info=True)
```

### 2. 使用自定义异常

```python
from core.exceptions import (
    TaskBusyException,
    DeviceConnectionException,
    APICallException,
    ValidationException
)

# 抛出业务异常（会被全局异常处理器捕获）
if is_busy:
    raise TaskBusyException()

# 带详细信息的异常
raise APICallException(
    message="OpenAI API 调用超时",
    details={"timeout": 30, "model": "gpt-4"}
)
```

---

## 📝 日志格式

### 文本格式（默认）- 易于阅读

```
2025-12-08 18:05:48.720 | INFO     | [d98103c4] | main:245 - 任务已接受，准备后台执行 | task_id=xyz-123 | instruction=打开支付宝
2025-12-08 18:05:50.123 | INFO     | [d98103c4] | agent_core:45 - 成功连接到 ADB 设备 | device_model=Pixel 6
2025-12-08 18:05:52.456 | INFO     | [d98103c4] | agent_core:202 - 执行动作 | action=click | description=点击支付宝图标
2025-12-08 18:05:55.789 | WARNING  | [d98103c4] | agent_core:250 - API 调用速率接近限制 | current_rate=95
2025-12-08 18:06:00.100 | ERROR    | [d98103c4] | agent_core:150 - 截图失败 | error=ADB timeout
```

**格式说明：**
```
时间戳 | 级别(8字符对齐) | [TraceID前8位] | 模块:行号 - 消息 | key=value | key=value
```

### 彩色文本格式 - 更直观

设置 `LOG_FORMAT=color` 后，不同级别会显示不同颜色：
- **INFO** - 绿色
- **WARNING** - 黄色
- **ERROR** - 红色
- **CRITICAL** - 紫色
- **DEBUG** - 青色

### JSON 格式 - 用于日志分析

设置 `LOG_FORMAT=json` 后输出 JSON 格式，便于日志收集工具处理：

```json
{
  "timestamp": "2025-12-08T18:05:48.720+08:00",
  "level": "INFO",
  "trace_id": "d98103c4-82bb-401b-8107-ba5f70cf616e",
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

---

## ⚙️ 环境变量配置

在项目根目录创建 `.env` 文件或设置环境变量：

```bash
# 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# 日志格式 (text, color, json)
# text  - 纯文本格式，易读（默认）
# color - 彩色文本格式，更直观
# json  - JSON格式，便于日志分析
LOG_FORMAT=text

# 日志文件路径（可选，不设置则只输出到控制台）
LOG_FILE_PATH=./logs/app.log

# 单个日志文件最大大小（字节）
LOG_MAX_BYTES=10485760  # 10MB

# 保留的日志文件数量
LOG_BACKUP_COUNT=5

# 是否启用控制台输出
LOG_ENABLE_CONSOLE=true

# 调试模式（启用更详细的日志）
DEBUG_MODE=false
```

### 示例配置文件

```bash
# .env - 开发环境（彩色输出）
LOG_LEVEL=INFO
LOG_FORMAT=color
LOG_ENABLE_CONSOLE=true
DEBUG_MODE=false
```

```bash
# .env - 生产环境（JSON格式+文件输出）
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=./logs/agent.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=10
LOG_ENABLE_CONSOLE=true
```

---

## 🔍 TraceID 使用

### 自动追踪

所有通过 FastAPI 接收的 HTTP 请求会自动生成 TraceID，并在响应头中返回：

```bash
# 请求
curl -X POST http://localhost:9777/run-agent-async \
  -H "Content-Type: application/json" \
  -d '{"instruction": "打开支付宝", "api_key": "xxx", ...}'

# 响应头
HTTP/1.1 200 OK
X-Trace-ID: d98103c4-82bb-401b-8107-ba5f70cf616e
X-Request-Duration: 0.123s
```

### 客户端传递 TraceID

客户端可以在请求头中传递自定义的 TraceID：

```bash
curl -X POST http://localhost:9777/run-agent-async \
  -H "Content-Type: application/json" \
  -H "X-Trace-ID: my-custom-trace-id" \
  -d '{"instruction": "打开支付宝", ...}'
```

### 后台任务追踪

异步任务使用 `task_id` 作为 `trace_id`，确保整个任务生命周期可追踪：

```python
# 后台任务自动设置 TraceID
task_id = str(uuid.uuid4())
set_trace_id(task_id)  # 使用 task_id 作为 trace_id

# 所有后续日志都会包含这个 trace_id
logger.info("开始执行任务", extra={"task_id": task_id})
```

---

## 🎯 统一异常处理

### 异常响应格式

所有异常都会返回统一的 JSON 格式：

```json
{
  "code": "TASK_BUSY",
  "message": "已有任务在执行，请等待上一个任务完成",
  "trace_id": "d98103c4-82bb-401b-8107-ba5f70cf616e",
  "timestamp": "2025-12-08T18:05:48.720+08:00",
  "details": {
    "additional_info": "..."
  }
}
```

### 预定义异常类型

| 异常类 | HTTP 状态码 | 错误码 | 说明 |
|--------|-------------|--------|------|
| `TaskBusyException` | 429 | `TASK_BUSY` | 任务繁忙 |
| `DeviceConnectionException` | 503 | `DEVICE_CONNECTION_ERROR` | 设备连接失败 |
| `APICallException` | 502 | `API_CALL_ERROR` | API 调用失败 |
| `ScreenshotException` | 500 | `SCREENSHOT_ERROR` | 截图失败 |
| `ActionExecutionException` | 500 | `ACTION_EXECUTION_ERROR` | 动作执行失败 |
| `ValidationException` | 400 | `VALIDATION_ERROR` | 参数验证失败 |

---

## 📊 日志查询示例

### 文本格式日志查询

```bash
# 查询特定 trace_id 的日志（前8位）
cat logs/agent.log | grep "\[d98103c4\]"

# 查询错误日志
cat logs/agent.log | grep "ERROR"

# 查询特定模块的日志
cat logs/agent.log | grep "agent_core"

# 查询包含特定关键词的日志
cat logs/agent.log | grep "任务完成"
```

### JSON 格式日志查询（使用 jq）

```bash
# 查询特定 trace_id 的所有日志
cat logs/agent.log | jq 'select(.trace_id == "d98103c4-82bb-401b-8107-ba5f70cf616e")'

# 查询错误级别的日志
cat logs/agent.log | jq 'select(.level == "ERROR")'

# 查询特定模块的日志
cat logs/agent.log | jq 'select(.module == "agent_core")'

# 按时间范围查询
cat logs/agent.log | jq 'select(.timestamp >= "2025-12-08T17:00:00")'

# 统计错误数量
cat logs/agent.log | jq 'select(.level == "ERROR")' | wc -l
```

---

## 💡 最佳实践

### 1. 使用结构化日志

❌ **不推荐**：
```python
logger.info(f"用户 {user_id} 登录成功，IP: {ip}")
```

✅ **推荐**：
```python
logger.info(
    "用户登录成功",
    extra={"user_id": user_id, "ip": ip}
)
```

### 2. 合理使用日志级别

- `DEBUG`: 详细的调试信息（生产环境应关闭）
- `INFO`: 关键业务流程节点
- `WARNING`: 警告信息，不影响主流程
- `ERROR`: 错误信息，影响功能但不崩溃
- `CRITICAL`: 严重错误，可能导致系统崩溃

### 3. 记录异常时包含堆栈

```python
try:
    risky_operation()
except Exception as e:
    logger.error("操作失败", exc_info=True)  # 包含完整堆栈
```

### 4. 避免记录敏感信息

❌ 不要记录：密码、API 密钥、个人隐私数据

```python
# 错误示例
logger.info(f"API Key: {api_key}")

# 正确示例
logger.info("API 认证成功", extra={"key_prefix": api_key[:8]})
```

### 5. 选择合适的日志格式

- **开发环境**: 使用 `color` 格式，便于快速查看
- **生产环境**: 使用 `json` 格式，便于日志收集和分析
- **日志文件**: 使用 `text` 或 `json` 格式

---

## 🧪 测试验证

### 启动服务

```bash
python main.py
```

### 查看日志输出（文本格式）

```
2025-12-08 18:05:48.720 | INFO     | [--------] | main:320 - 启动 Mobile Agent API 服务 | host=0.0.0.0 | port=9777
```

### 查看日志输出（彩色格式）

```bash
LOG_FORMAT=color python main.py
```

### 发送测试请求

```bash
# 异步任务
curl -X POST http://localhost:9777/run-agent-async \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "打开支付宝",
    "max_steps": 10,
    "api_key": "your-api-key",
    "base_url": "https://api.openai.com/v1",
    "model_name": "gui-owl",
    "callback_url": "http://localhost:9777/callback-test"
  }'
```

### 验证 TraceID

检查响应头是否包含 `X-Trace-ID`：

```bash
curl -i http://localhost:9777/run-agent-async ...
```

---

## 🔧 故障排查

### 日志文件未生成

- 检查 `LOG_FILE_PATH` 是否设置
- 确认目录权限
- 查看控制台是否有权限错误

### TraceID 未出现在日志中

- 确认使用了 `TraceMiddleware`
- 检查是否在异步上下文中正确设置 TraceID
- 后台任务需要手动设置：`set_trace_id(task_id)`

### 日志级别不生效

- 检查环境变量 `LOG_LEVEL` 是否正确设置
- 确认 `.env` 文件在正确位置
- 使用 `set_log_level()` 动态修改

### 日志格式不符合预期

- 检查 `LOG_FORMAT` 环境变量（text/color/json）
- 清除终端缓存，重启服务
- 确认支持 ANSI 颜色的终端（Windows 10+ CMD, PowerShell, Git Bash 等）

---

## 📚 参考资料

- [Python logging 文档](https://docs.python.org/3/library/logging.html)
- [FastAPI 中间件](https://fastapi.tiangolo.com/tutorial/middleware/)
- [contextvars 文档](https://docs.python.org/3/library/contextvars.html)

---

## 🆘 支持

如有问题或建议，请提交 Issue 或联系开发团队。
