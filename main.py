from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional
import uvicorn
import asyncio
import httpx
import uuid
import logging
import threading
from agent_core import run_mobile_agent
from agent_core_v4 import run_mobile_agent_v4, run_mobile_agent_v4_async
from datetime import datetime, timezone

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        # 设置任务执行状态
        is_task_running = True
        logger.info(f"开始执行任务 {task_id}")
        
        # 在线程池中执行同步的agent函数
        result = await asyncio.to_thread(
            run_mobile_agent,
            instruction=instruction,
            max_steps=max_steps,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name
        )
        
        # 添加任务ID到结果中
        result["task_id"] = task_id
        
        logger.info(f"任务 {task_id} 执行完成，状态: {result.get('status')}")
        
        # 如果提供了回调URL，则进行POST回调
        if callback_url:
            await send_callback(callback_url, result)
            
    except Exception as e:
        logger.error(f"任务 {task_id} 执行失败: {e}")
        error_result = {
            "task_id": task_id,
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

async def execute_agent_v4_with_callback(
    task_id: str,
    instruction: str,
    max_steps: int,
    api_key: str,
    base_url: str,
    model_name: str,
    output_path: str,
    callback_url: Optional[str] = None
):
    """在后台执行agent v4任务并进行回调"""
    global is_task_running
    
    try:
        # 设置任务执行状态
        is_task_running = True
        logger.info(f"开始执行V4任务 {task_id}")
        
        # 使用已有的异步V4函数
        result = await run_mobile_agent_v4_async(
            instruction=instruction,
            max_steps=max_steps,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            output_path=output_path
        )
        
        # 添加任务ID到结果中
        result["task_id"] = task_id
        
        logger.info(f"V4任务 {task_id} 执行完成，状态: {result.get('status')}")
        
        # 如果提供了回调URL，则进行POST回调
        if callback_url:
            await send_callback(callback_url, result)
            
    except Exception as e:
        logger.error(f"V4任务 {task_id} 执行失败: {e}")
        error_result = {
            "task_id": task_id,
            "status": "error",
            "error": str(e)
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

    logger.info(f"[Callback] Initiating callback for Task ID: {task_id} to URL: {callback_url}")
    logger.info(f"[Callback] Payload preview - Status: {result.get('status')}, Size: {len(str(result))} chars")

    last_error_message = None

    for attempt in range(1, max_attempts + 1):
        try:
            start_time = time.time()

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Content-Type": "application/json", "User-Agent": "Mobile-Agent-API/1.0"},
                follow_redirects=True
            ) as client:
                logger.info(f"[Callback] Attempt {attempt}/{max_attempts}: Sending POST request to {callback_url}")

                response = await client.post(callback_url, json=result)

                elapsed_time = time.time() - start_time
                logger.info(f"[Callback] Attempt {attempt}: Request completed in {elapsed_time:.2f} seconds")
                logger.info(f"[Callback] Attempt {attempt}: Response Status Code: {response.status_code}")
                logger.info(f"[Callback] Attempt {attempt}: Response Headers: {dict(response.headers)}")

                # Log response body (truncate if large)
                try:
                    response_text = response.text
                    if len(response_text) > 500:
                        logger.info(f"[Callback] Attempt {attempt}: Response Body (truncated): {response_text[:500]}...")
                    else:
                        logger.info(f"[Callback] Attempt {attempt}: Response Body: {response_text}")
                except Exception as content_error:
                    logger.warning(f"[Callback] Attempt {attempt}: Could not read response body: {content_error}")

                # Success on any 2xx response
                if 200 <= response.status_code < 300:
                    logger.info(f"[Callback] Success on attempt {attempt} - Task ID: {task_id}, URL: {callback_url}")
                    logger.info(f"[Callback] Finished processing callback for Task ID: {task_id}")
                    return

                # Non-success status code: prepare to retry if attempts remain
                last_error_message = f"Non-success status code: {response.status_code}"
                logger.warning(f"[Callback] Attempt {attempt} failed: {last_error_message}")

        except httpx.TimeoutException as timeout_error:
            last_error_message = f"Timeout: {timeout_error}"
            logger.error(f"[Callback] Attempt {attempt} failed with timeout - Task ID: {task_id}, URL: {callback_url}, Error: {timeout_error}")
        except httpx.ConnectError as connect_error:
            last_error_message = f"Connection failed: {connect_error}"
            logger.error(f"[Callback] Attempt {attempt} failed to connect - Task ID: {task_id}, URL: {callback_url}, Error: {connect_error}")
        except httpx.HTTPStatusError as http_error:
            last_error_message = f"HTTP error: {http_error}"
            status_code = getattr(getattr(http_error, 'response', None), 'status_code', 'unknown')
            logger.error(f"[Callback] Attempt {attempt} HTTP error - Task ID: {task_id}, URL: {callback_url}, Status Code: {status_code}, Error: {http_error}")
        except Exception as e:
            last_error_message = f"Unexpected error: {type(e).__name__}: {e}"
            logger.error(f"[Callback] Attempt {attempt} failed - Task ID: {task_id}, URL: {callback_url}, Exception Type: {type(e).__name__}, Error: {e}")
            import traceback
            logger.debug(f"[Callback] Exception traceback on attempt {attempt}:\n{traceback.format_exc()}")

        # If not returned yet, we will retry if we have remaining attempts
        if attempt < max_attempts:
            # Exponential backoff with jitter
            backoff = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            jitter = random.uniform(0, 0.5)
            delay = backoff + jitter
            logger.info(f"[Callback] Scheduling retry {attempt + 1} in {delay:.2f} seconds")
            await asyncio.sleep(delay)
        else:
            logger.error(f"[Callback] All {max_attempts} attempts failed for Task ID: {task_id}. Last error: {last_error_message}")
            logger.info(f"[Callback] Finished processing callback for Task ID: {task_id}")
            return

app = FastAPI(
    title="Mobile Agent API",
    description="An API to control a mobile agent to perform tasks based on user instructions.",
    version="1.0.0",
)

class AgentRequest(BaseModel):
    instruction: str
    max_steps: int = 50
    api_key: str
    base_url: str
    model_name: str = "gui-owl"
    callback_url: Optional[str] = None

class AgentV4Request(BaseModel):
    instruction: str
    max_steps: int = 50
    api_key: str
    base_url: str
    model_name: str = "gui-owl"
    output_path: str = "./agent_outputs"
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
    try:
        result = run_mobile_agent(
            instruction=request.instruction,
            max_steps=request.max_steps,
            api_key=request.api_key,
            base_url=request.base_url,
            model_name=request.model_name
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result
    except Exception as e:
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

    logger.info(f"[Callback-Test] Received callback. Total stored: {len(CALLBACK_LOGS)}")
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
    logger.info("[Callback-Test] Cleared callback logs")
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
    
    # 检查是否已有任务在执行
    if is_task_running:
        return {
            "status": "busy",
            "message": "已有任务在执行，请等待上一个任务执行完成后再请求",
        }
    
    # 指令关键词校验：若不包含"买/下单/购买"等关键词，则直接返回未实现
    keywords = ["买", "下单", "购买"]
    instruction_text = (request.instruction or "").strip()
    if not any(keyword in instruction_text for keyword in keywords):
        return {
            "status": "not_supported",
            "message": "未实现对应功能任务：指令未包含购买/下单相关关键词",
        }

    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
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

@app.post("/run-agent-v4")
async def run_agent_v4_endpoint(request: AgentV4Request):
    """
    Run the mobile agent v4 with the given instruction using the optimized mobile_agent_v4 engine.

    - **instruction**: The user's instruction for the agent.
    - **max_steps**: The maximum number of steps the agent can take.
    - **api_key**: The API key for the OpenAI model.
    - **base_url**: The base URL for the OpenAI API.
    - **model_name**: The name of the model to use.
    - **output_path**: The output path for saving agent execution logs and screenshots.
    """
    try:
        result = run_mobile_agent_v4(
            instruction=request.instruction,
            max_steps=request.max_steps,
            api_key=request.api_key,
            base_url=request.base_url,
            model_name=request.model_name,
            output_path=request.output_path
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-agent-v4-async")
async def run_agent_v4_async_endpoint(request: AgentV4Request, background_tasks: BackgroundTasks):
    """
    Run the mobile agent v4 asynchronously with the given instruction. Returns immediately with task_id.
    If callback_url is provided, results will be POST to that URL when complete.

    - **instruction**: The user's instruction for the agent.
    - **max_steps**: The maximum number of steps the agent can take.
    - **api_key**: The API key for the OpenAI model.
    - **base_url**: The base URL for the OpenAI API.
    - **model_name**: The name of the model to use.
    - **output_path**: The output path for saving agent execution logs and screenshots.
    - **callback_url**: Optional URL to POST results when task completes.
    """
    global is_task_running
    
    # 检查是否已有任务在执行
    if is_task_running:
        return {
            "status": "busy",
            "message": "已有任务在执行，请等待上一个任务执行完成后再请求",
        }
    
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 添加后台任务
    background_tasks.add_task(
        execute_agent_v4_with_callback,
        task_id=task_id,
        instruction=request.instruction,
        max_steps=request.max_steps,
        api_key=request.api_key,
        base_url=request.base_url,
        model_name=request.model_name,
        output_path=request.output_path,
        callback_url=request.callback_url
    )
    
    # 立即返回任务ID
    return {
        "task_id": task_id,
        "status": "accepted",
        "message": "V4任务已接受，正在后台执行",
        "callback_url": request.callback_url
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9777)