from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uvicorn
import asyncio
import httpx
import uuid
import logging
from agent_core import run_mobile_agent
from agent_core_v4 import run_mobile_agent_v4, run_mobile_agent_v4_async

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    try:
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
    try:
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

async def send_callback(callback_url: str, result: dict):
    """Sends a POST callback to the specified URL."""
    task_id = result.get("task_id", "unknown")

    logger.info(f"[Callback] Initiating callback for Task ID: {task_id} to URL: {callback_url}")
    logger.info(f"[Callback] Payload preview - Status: {result.get('status')}, Size: {len(str(result))} chars")

    try:
        import time
        start_time = time.time()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Content-Type": "application/json", "User-Agent": "Mobile-Agent-API/1.0"}
        ) as client:
            logger.info(f"[Callback] Sending POST request to {callback_url}")

            response = await client.post(callback_url, json=result)

            elapsed_time = time.time() - start_time

            logger.info(f"[Callback] Request completed in {elapsed_time:.2f} seconds")
            logger.info(f"[Callback] Response Status Code: {response.status_code}")
            logger.info(f"[Callback] Response Headers: {dict(response.headers)}")

            try:
                response_text = response.text
                if len(response_text) > 500:
                    logger.info(f"[Callback] Response Body (truncated): {response_text[:500]}...")
                else:
                    logger.info(f"[Callback] Response Body: {response_text}")
            except Exception as content_error:
                logger.warning(f"[Callback] Could not read response body: {content_error}")

            if 200 <= response.status_code < 300:
                logger.info(f"[Callback] Success - Task ID: {task_id}, URL: {callback_url}, Status Code: {response.status_code}")
            else:
                logger.warning(f"[Callback] Non-success status code - Task ID: {task_id}, URL: {callback_url}, Status Code: {response.status_code}")

    except httpx.TimeoutException as timeout_error:
        logger.error(f"[Callback] Timeout - Task ID: {task_id}, URL: {callback_url}, Error: {timeout_error}")
    except httpx.ConnectError as connect_error:
        logger.error(f"[Callback] Connection failed - Task ID: {task_id}, URL: {callback_url}, Error: {connect_error}")
    except httpx.HTTPStatusError as http_error:
        logger.error(f"[Callback] HTTP error - Task ID: {task_id}, URL: {callback_url}, Status Code: {http_error.response.status_code}, Error: {http_error}")
    except Exception as e:
        logger.error(f"[Callback] Failed to send - Task ID: {task_id}, URL: {callback_url}, Exception Type: {type(e).__name__}, Error: {e}")
        import traceback
        logger.debug(f"[Callback] Exception traceback:\n{traceback.format_exc()}")

    logger.info(f"[Callback] Finished processing callback for Task ID: {task_id}")

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

@app.post("/run-agent/")
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

@app.post("/run-agent-async/")
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

@app.post("/run-agent-v4/")
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

@app.post("/run-agent-v4-async/")
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
    uvicorn.run(app, host="0.0.0.0", port=8000)

