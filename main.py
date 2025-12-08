from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional
import uvicorn
import asyncio
import httpx
import uuid
import threading
from agent_core import run_mobile_agent
from datetime import datetime, timezone

# 导入核心日志和异常处理模块
from core.logger import get_logger
from core.trace_context import set_trace_id, generate_trace_id
from core.exceptions import TaskBusyException, DeviceConnectionException, APICallException
from middleware.trace_middleware import TraceMiddleware
from middleware.exception_handler import setup_exception_handlers

# 获取日志记录器
logger = get_logger(__name__)

# 简单的内存回调存储（仅用于测试与调试，生产请使用持久化存储）
CALLBACK_LOGS = []  # list[dict]

# 任务执行锁，确保同时只有一个任务执行
task_execution_lock = threading.Lock()
is_task_running = False

# 后台任务处理函数
async def execute_agent_with_callback(
    task_id: str,
    instruction: str,
    max_steps: int,
    api_key: str,
    base_url: str,
    model_name: str,
    callback_url: Optional[str] = None
):
    """在后台执行agent任务并进行回调"""
    global is_task_running
    
    try:
        # 为后台任务设置 TraceID（使用 task_id 作为 trace_id）
        set_trace_id(task_id)
        
        # 设置任务执行状态
        is_task_running = True
        logger.info("开始执行任务", extra={"task_id": task_id, "instruction": instruction})
        
        # 在线程池中执行同步的agent函数
        result = await asyncio.to_thread(
            run_mobile_agent,
            instruction=instruction,
            max_steps=max_steps,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name
        )
        
        # 添加任务ID和原始指令到结果中
        result["task_id"] = task_id
        result["instruction"] = instruction
        
        logger.info(
            "任务执行完成",
            extra={
                "task_id": task_id,
                "status": result.get('status'),
                "history_length": len(result.get('history', []))
            }
        )
        
        # 如果提供了回调URL，则进行POST回调
        if callback_url:
            await send_callback(callback_url, result)
            
    except Exception as e:
        logger.error(
            "任务执行失败",
            extra={"task_id": task_id, "error": str(e)},
            exc_info=True
        )
        error_result = {
            "task_id": task_id,
            "instruction": instruction,
            "status": "error",
            "message": str(e),
            "history": []
        }
        
        # 即使出错也要回调
        if callback_url:
            await send_callback(callback_url, error_result)
    finally:
        # 无论成功还是失败，都要释放任务执行状态
        is_task_running = False

async def send_callback(callback_url: str, result: dict):
    """Sends a POST callback to the specified URL with retry mechanism and exponential backoff."""
    import time
    import random

    task_id = result.get("task_id", "unknown")

    # Retry configuration (local to function to avoid global constants churn)
    max_attempts = 5
    base_delay_seconds = 1.0
    max_delay_seconds = 30.0

    logger.info(
        "Initiating callback",
        extra={
            "task_id": task_id,
            "callback_url": callback_url,
            "status": result.get('status'),
            "payload_size": len(str(result))
        }
    )

    last_error_message = None

    for attempt in range(1, max_attempts + 1):
        try:
            start_time = time.time()

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Content-Type": "application/json", "User-Agent": "Mobile-Agent-API/1.0"},
                follow_redirects=True
            ) as client:
                logger.info(
                    "Sending callback request",
                    extra={"attempt": f"{attempt}/{max_attempts}", "url": callback_url}
                )

                response = await client.post(callback_url, json=result)

                elapsed_time = time.time() - start_time
                
                # Log response details
                response_text = response.text[:500] if len(response.text) > 500 else response.text
                logger.info(
                    "Callback response received",
                    extra={
                        "attempt": attempt,
                        "status_code": response.status_code,
                        "elapsed_time": f"{elapsed_time:.2f}s",
                        "response_body": response_text
                    }
                )

                # Success on any 2xx response
                if 200 <= response.status_code < 300:
                    logger.info(
                        "Callback succeeded",
                        extra={"attempt": attempt, "task_id": task_id}
                    )
                    return

                # Non-success status code: prepare to retry if attempts remain
                last_error_message = f"Non-success status code: {response.status_code}"
                logger.warning(
                    "Callback attempt failed",
                    extra={"attempt": attempt, "error": last_error_message}
                )

        except httpx.TimeoutException as timeout_error:
            last_error_message = f"Timeout: {timeout_error}"
            logger.error(
                "Callback timeout",
                extra={"attempt": attempt, "task_id": task_id, "error": str(timeout_error)}
            )
        except httpx.ConnectError as connect_error:
            last_error_message = f"Connection failed: {connect_error}"
            logger.error(
                "Callback connection failed",
                extra={"attempt": attempt, "task_id": task_id, "error": str(connect_error)}
            )
        except httpx.HTTPStatusError as http_error:
            last_error_message = f"HTTP error: {http_error}"
            status_code = getattr(getattr(http_error, 'response', None), 'status_code', 'unknown')
            logger.error(
                "Callback HTTP error",
                extra={
                    "attempt": attempt,
                    "task_id": task_id,
                    "status_code": status_code,
                    "error": str(http_error)
                }
            )
        except Exception as e:
            last_error_message = f"Unexpected error: {type(e).__name__}: {e}"
            logger.error(
                "Callback unexpected error",
                extra={
                    "attempt": attempt,
                    "task_id": task_id,
                    "exception_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )

        # If not returned yet, we will retry if we have remaining attempts
        if attempt < max_attempts:
            # Exponential backoff with jitter
            backoff = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            jitter = random.uniform(0, 0.5)
            delay = backoff + jitter
            logger.info(
                "Scheduling callback retry",
                extra={"next_attempt": attempt + 1, "delay": f"{delay:.2f}s"}
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                "All callback attempts failed",
                extra={
                    "task_id": task_id,
                    "max_attempts": max_attempts,
                    "last_error": last_error_message
                }
            )
            return

app = FastAPI(
    title="Mobile Agent API",
    description="An API to control a mobile agent to perform tasks based on user instructions.",
    version="1.0.0",
)

# 添加 TraceID 中间件
app.add_middleware(TraceMiddleware)

# 配置全局异常处理器
setup_exception_handlers(app)

class AgentRequest(BaseModel):
    instruction: str
    max_steps: int = 50
    api_key: str
    base_url: str
    model_name: str = "gui-owl"
    callback_url: Optional[str] = None

@app.post("/run-agent")
async def run_agent_endpoint(request: AgentRequest):
    """
    Run the mobile agent with the given instruction.

    - **instruction**: The user's instruction for the agent.
    - **max_steps**: The maximum number of steps the agent can take.
    - **api_key**: The API key for the OpenAI model.
    - **base_url**: The base URL for the OpenAI API.
    - **model_name**: The name of the model to use.
    """
    logger.info(
        "接收到同步任务请求",
        extra={"instruction": request.instruction, "max_steps": request.max_steps}
    )
    
    try:
        result = run_mobile_agent(
            instruction=request.instruction,
            max_steps=request.max_steps,
            api_key=request.api_key,
            base_url=request.base_url,
            model_name=request.model_name
        )
        
        if result.get("status") == "error":
            logger.error("任务执行返回错误", extra={"message": result.get("message")})
            raise HTTPException(status_code=500, detail=result.get("message"))

        logger.info("任务执行成功", extra={"status": result.get("status")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("任务执行异常", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==============================
# Callback 测试与查看接口（仅调试）
# ==============================

@app.post("/callback-test")
async def callback_test_receiver(request: Request):
    """测试用回调接收端点：记录并返回接收结果。"""
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": await request.body()}

    record = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "headers": dict(request.headers),
        "payload": payload,
    }
    CALLBACK_LOGS.append(record)
    # 控制内存占用，仅保留最近100条
    if len(CALLBACK_LOGS) > 100:
        del CALLBACK_LOGS[:-100]

    logger.info("收到回调测试请求", extra={"total_stored": len(CALLBACK_LOGS)})
    return {"status": "ok", "stored": len(CALLBACK_LOGS)}

@app.get("/callback-test")
async def callback_test_list(limit: int = 20):
    """获取最近的回调记录。"""
    limit = max(1, min(100, limit))
    return {
        "count": min(limit, len(CALLBACK_LOGS)),
        "total": len(CALLBACK_LOGS),
        "items": CALLBACK_LOGS[-limit:],
    }

@app.delete("/callback-test")
async def callback_test_clear():
    """清空回调记录。"""
    cleared = len(CALLBACK_LOGS)
    CALLBACK_LOGS.clear()
    logger.info("清空回调测试日志", extra={"cleared_count": cleared})
    return {"status": "cleared", "cleared": cleared}

@app.post("/run-agent-async")
async def run_agent_async_endpoint(request: AgentRequest, background_tasks: BackgroundTasks):
    """
    Run the mobile agent asynchronously with the given instruction. Returns immediately with task_id.
    If callback_url is provided, results will be POST to that URL when complete.

    - **instruction**: The user's instruction for the agent.
    - **max_steps**: The maximum number of steps the agent can take.
    - **api_key**: The API key for the OpenAI model.
    - **base_url**: The base URL for the OpenAI API.
    - **model_name**: The name of the model to use.
    - **callback_url**: Optional URL to POST results when task completes.
    """
    global is_task_running
    
    logger.info(
        "接收到异步任务请求",
        extra={
            "instruction": request.instruction,
            "max_steps": request.max_steps,
            "callback_url": request.callback_url
        }
    )
    
    # 检查是否已有任务在执行
    if is_task_running:
        logger.warning("任务繁忙，已有任务在执行")
        raise TaskBusyException()
    
    # 指令关键词校验：若不包含等关键词，则直接返回未实现
    # keywords = ["burger king", "汉堡王", "grab", "alipay", "支付宝", "微信", "wechat", "滴滴", "小美", "Alipay", "Hi Agent", "Hi Agent", "代理", "特工", "Hi", "Hello", "hi", "hello", "你好"]
    # instruction_text = (request.instruction or "").strip()
    # if not any(keyword in instruction_text for keyword in keywords):
    #     return {
    #         "status": "not_supported",
    #         "message": "未实现对应功能任务：指令未包含相关关键词",
    #     }

    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    logger.info("任务已接受，准备后台执行", extra={"task_id": task_id})
    
    # 添加后台任务
    background_tasks.add_task(
        execute_agent_with_callback,
        task_id=task_id,
        instruction=request.instruction,
        max_steps=request.max_steps,
        api_key=request.api_key,
        base_url=request.base_url,
        model_name=request.model_name,
        callback_url=request.callback_url
    )
    
    # 立即返回任务ID
    return {
        "task_id": task_id,
        "status": "accepted",
        "message": "任务已接受，正在后台执行",
        "callback_url": request.callback_url
    }

if __name__ == "__main__":
    logger.info("启动 Mobile Agent API 服务", extra={"host": "0.0.0.0", "port": 9777})
    uvicorn.run(app, host="0.0.0.0", port=9777)
