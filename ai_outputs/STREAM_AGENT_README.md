# 流式 Agent 使用指南

## 📋 概述

`run_mobile_agent_stream` 是 `run_mobile_agent` 的流式输出版本,它通过 Python Generator 实时返回执行过程中的各种事件,支持:

- ✅ **实时流式输出** LLM 的思考过程
- ✅ **自动保存截图** 每一步的屏幕截图
- ✅ **记录操作日志** 完整的动作和响应记录
- ✅ **结构化事件** 易于 Web 前端集成
- ✅ **可回放执行** 保存完整执行历史

## 🚀 快速开始

### 基本使用

```python
from agent_core import run_mobile_agent_stream

# 流式运行 Agent
for event in run_mobile_agent_stream(
    instruction="打开微信",
    max_steps=10,
    api_key="your-api-key",
    base_url="your-base-url",
    model_name="gui-owl"
):
    event_type = event.get("event_type")
    
    if event_type == "llm_chunk":
        # 实时打印 LLM 的思考过程
        print(event["data"]["chunk"], end='', flush=True)
    
    elif event_type == "action_completed":
        # 动作执行完成
        print(f"✅ 动作完成: {event['data']['description']}")
    
    elif event_type == "task_completed":
        # 任务完成
        print(f"🎉 任务完成! 输出目录: {event['data']['output_dir']}")
```

### 运行测试脚本

```bash
# 基本测试
python test_stream_agent.py

# Web 集成演示
python test_stream_agent.py web
```

## 📊 事件类型

流式 Agent 会 yield 以下类型的事件:

### 1. `task_init` - 任务初始化
```json
{
  "event_type": "task_init",
  "task_id": "abc12345",
  "timestamp": "2025-12-08T18:00:00",
  "data": {
    "instruction": "打开微信",
    "max_steps": 10,
    "output_dir": "agent_outputs/task_abc12345"
  }
}
```

### 2. `device_connected` - 设备连接成功
```json
{
  "event_type": "device_connected",
  "task_id": "abc12345",
  "timestamp": "2025-12-08T18:00:01",
  "data": {
    "device_model": "Mi 11"
  }
}
```

### 3. `step_start` - 步骤开始
```json
{
  "event_type": "step_start",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:02",
  "data": {
    "total_steps": 10
  }
}
```

### 4. `screenshot` - 截图完成
```json
{
  "event_type": "screenshot",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:03",
  "data": {
    "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "screenshot_path": "agent_outputs/task_abc12345/step_1/screenshot.png",
    "width": 1080,
    "height": 2400
  }
}
```

### 5. `llm_call_start` - LLM 调用开始
```json
{
  "event_type": "llm_call_start",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:04",
  "data": {
    "model": "gui-owl"
  }
}
```

### 6. `llm_chunk` - LLM 流式输出片段
```json
{
  "event_type": "llm_chunk",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:05",
  "data": {
    "chunk": "我看到",
    "chunk_index": 1,
    "accumulated_length": 3
  }
}
```

### 7. `llm_complete` - LLM 响应完成
```json
{
  "event_type": "llm_complete",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:10",
  "data": {
    "response_length": 256,
    "chunks_received": 50,
    "response_path": "agent_outputs/task_abc12345/step_1/llm_response.txt"
  }
}
```

### 8. `action_parsed` - 动作解析完成
```json
{
  "event_type": "action_parsed",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:11",
  "data": {
    "action": {
      "action": "click",
      "coordinate": [540, 1200],
      "description": "点击微信图标"
    },
    "thinking": "我看到屏幕上有微信图标...",
    "conclusion": "需要点击微信图标来打开应用",
    "action_path": "agent_outputs/task_abc12345/step_1/action.json"
  }
}
```

### 9. `action_executing` - 动作执行中
```json
{
  "event_type": "action_executing",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:12",
  "data": {
    "action": "click",
    "description": "点击微信图标"
  }
}
```

### 10. `action_completed` - 动作执行完成
```json
{
  "event_type": "action_completed",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:13",
  "data": {
    "status": "continue",
    "action": "click",
    "description": "点击微信图标"
  }
}
```

### 11. `step_end` - 步骤结束
```json
{
  "event_type": "step_end",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:14",
  "data": {
    "step": 1,
    "start_time": "2025-12-08T18:00:02",
    "end_time": "2025-12-08T18:00:14",
    "screenshot_path": "agent_outputs/task_abc12345/step_1/screenshot.png",
    "llm_response": "完整的LLM响应文本...",
    "action": {...},
    "status": "continue",
    "error": null
  }
}
```

### 12. `task_completed` - 任务完成
```json
{
  "event_type": "task_completed",
  "task_id": "abc12345",
  "timestamp": "2025-12-08T18:05:00",
  "data": {
    "status": "success",
    "total_steps": 5,
    "history": ["步骤1描述", "步骤2描述", ...],
    "output_dir": "agent_outputs/task_abc12345",
    "metadata_path": "agent_outputs/task_abc12345/metadata.json",
    "log_path": "agent_outputs/task_abc12345/execution_log.json"
  }
}
```

### 13. `error` - 错误事件
```json
{
  "event_type": "error",
  "task_id": "abc12345",
  "step": 1,
  "timestamp": "2025-12-08T18:00:15",
  "data": {
    "error_type": "api_call",
    "message": "API 调用失败: Connection timeout",
    "details": {...},
    "continue": false
  }
}
```

## 📁 输出文件结构

执行后会在 `agent_outputs` 目录下生成以下结构:

```
agent_outputs/
└── task_abc12345/                  # 任务目录
    ├── metadata.json               # 任务元信息
    ├── execution_log.json          # 完整执行日志
    ├── step_1/                     # 第1步
    │   ├── screenshot.png          # 截图
    │   ├── llm_response.txt        # LLM完整响应
    │   └── action.json             # 动作详情
    ├── step_2/                     # 第2步
    │   ├── screenshot.png
    │   ├── llm_response.txt
    │   └── action.json
    └── ...
```

### metadata.json 示例
```json
{
  "task_id": "abc12345",
  "instruction": "打开微信",
  "max_steps": 10,
  "model_name": "gui-owl",
  "start_time": "2025-12-08T18:00:00",
  "end_time": "2025-12-08T18:05:00",
  "final_status": "success",
  "total_steps": 5,
  "steps": [...]
}
```

### action.json 示例
```json
{
  "thinking": "我看到屏幕上有微信图标,位于坐标(540, 1200)附近",
  "action": {
    "action": "click",
    "coordinate": [540, 1200],
    "description": "点击微信图标"
  },
  "conclusion": "成功点击微信图标,应该能打开微信应用"
}
```

## 🌐 Web 集成示例

### FastAPI + WebSocket

```python
from fastapi import FastAPI, WebSocket
from agent_core import run_mobile_agent_stream
import json

app = FastAPI()

@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    await websocket.accept()
    
    # 接收前端指令
    data = await websocket.receive_json()
    instruction = data.get("instruction")
    
    # 流式执行并推送事件
    for event in run_mobile_agent_stream(
        instruction=instruction,
        max_steps=10,
        api_key=api_key,
        base_url=base_url,
        model_name="gui-owl"
    ):
        # 发送事件到前端
        await websocket.send_json(event)
    
    await websocket.close()
```

### Server-Sent Events (SSE)

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agent_core import run_mobile_agent_stream
import json

app = FastAPI()

@app.get("/api/agent/stream")
async def stream_agent(instruction: str):
    def event_generator():
        for event in run_mobile_agent_stream(
            instruction=instruction,
            max_steps=10,
            api_key=api_key,
            base_url=base_url,
            model_name="gui-owl"
        ):
            # SSE 格式
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### 前端示例 (JavaScript)

```javascript
// WebSocket 方式
const ws = new WebSocket('ws://localhost:8000/ws/agent');

ws.onopen = () => {
  ws.send(JSON.stringify({
    instruction: "打开微信"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event_type) {
    case 'screenshot':
      // 显示截图
      document.getElementById('screenshot').src = 
        'data:image/png;base64,' + data.data.screenshot_base64;
      break;
      
    case 'llm_chunk':
      // 实时显示 LLM 思考
      document.getElementById('thinking').innerText += data.data.chunk;
      break;
      
    case 'action_parsed':
      // 显示动作信息
      console.log('Action:', data.data.action);
      break;
      
    case 'task_completed':
      // 任务完成
      alert('任务完成!');
      break;
  }
};

// SSE 方式
const eventSource = new EventSource(
  '/api/agent/stream?instruction=' + encodeURIComponent('打开微信')
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // 处理事件...
};
```

## 🔧 参数说明

### run_mobile_agent_stream 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `instruction` | str | ✅ | - | 用户指令 |
| `max_steps` | int | ❌ | 50 | 最大执行步数 |
| `api_key` | str | ✅ | "" | OpenAI API 密钥 |
| `base_url` | str | ✅ | "" | API 基础 URL |
| `model_name` | str | ❌ | "gui-owl" | 模型名称 |
| `output_dir` | str | ❌ | "agent_outputs" | 输出目录 |
| `task_id` | str | ❌ | None | 任务ID (自动生成) |

## 📝 最佳实践

### 1. 处理长时间运行

```python
import asyncio

async def run_agent_async(instruction):
    """异步运行 Agent"""
    loop = asyncio.get_event_loop()
    
    for event in run_mobile_agent_stream(
        instruction=instruction,
        max_steps=50,
        api_key=api_key,
        base_url=base_url,
        model_name="gui-owl"
    ):
        # 处理事件
        await process_event(event)
        
        # 允许其他任务执行
        await asyncio.sleep(0)
```

### 2. 错误处理

```python
try:
    for event in run_mobile_agent_stream(...):
        if event.get("event_type") == "error":
            error_type = event["data"]["error_type"]
            
            if error_type == "device_connection":
                # 设备连接失败,终止任务
                break
            elif error_type == "action_execution":
                # 动作执行失败,可以继续
                if event["data"].get("continue"):
                    continue
                else:
                    break
        
        # 处理其他事件...
        
except KeyboardInterrupt:
    print("用户中断任务")
except Exception as e:
    print(f"发生异常: {e}")
```

### 3. 截图优化

对于 Web 应用,可以选择性传输截图:

```python
for event in run_mobile_agent_stream(...):
    if event.get("event_type") == "screenshot":
        # 只传输截图路径,不传输 base64
        event_to_send = event.copy()
        event_to_send["data"] = {
            "screenshot_path": event["data"]["screenshot_path"],
            "width": event["data"]["width"],
            "height": event["data"]["height"]
        }
        # 前端通过路径请求截图
        await websocket.send_json(event_to_send)
    else:
        await websocket.send_json(event)
```

## 🆚 与原版的区别

| 特性 | `run_mobile_agent` | `run_mobile_agent_stream` |
|------|-------------------|---------------------------|
| 输出方式 | 最后返回结果 | 流式 yield 事件 |
| LLM 调用 | 非流式 | 流式 |
| 截图保存 | ❌ | ✅ 每步保存 |
| 操作记录 | ❌ | ✅ JSON 文件 |
| 实时反馈 | ❌ | ✅ 实时事件 |
| Web 集成 | 困难 | 简单 |
| 回放功能 | ❌ | ✅ 完整日志 |

## 📚 更多资源

- 测试脚本: `test_stream_agent.py`
- 核心代码: `agent_core.py` 中的 `run_mobile_agent_stream` 函数
- 日志系统: `core/logger.py`
- 异常处理: `core/exceptions.py`

## ❓ 常见问题

### Q: 如何停止正在运行的任务?

A: 使用 `Ctrl+C` 中断,或在 Web 应用中关闭连接。

### Q: 截图文件太大怎么办?

A: 可以在保存截图前进行压缩,或使用较低的图像质量:

```python
# 在 capture_screenshot 函数中
image.save(screenshot_path, quality=85, optimize=True)
```

### Q: 如何自定义输出目录?

A: 使用 `output_dir` 参数:

```python
for event in run_mobile_agent_stream(
    instruction="...",
    output_dir="/path/to/custom/output"
):
    ...
```

### Q: 如何回放已保存的任务?

A: 读取 `execution_log.json` 和对应的截图文件:

```python
import json
from pathlib import Path

task_dir = Path("agent_outputs/task_abc12345")
log_file = task_dir / "execution_log.json"

with open(log_file, 'r', encoding='utf-8') as f:
    execution_log = json.load(f)

for step_data in execution_log:
    screenshot_path = step_data["screenshot_path"]
    action = step_data["action"]
    # 回放逻辑...
```

## 🎉 总结

流式 Agent 提供了强大的实时反馈能力,非常适合:

- 🌐 Web 应用集成
- 📊 实时监控和调试
- 📝 详细的执行日志
- 🔄 任务回放和分析

开始使用: `python test_stream_agent.py`
