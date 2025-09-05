from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import asyncio
from agent_core import run_mobile_agent
from agent_core_v4 import run_mobile_agent_v4, run_mobile_agent_v4_async

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

class AgentV4Request(BaseModel):
    instruction: str
    max_steps: int = 50
    api_key: str
    base_url: str
    model_name: str = "gui-owl"
    output_path: str = "./agent_outputs"

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
async def run_agent_async_endpoint(request: AgentRequest):
    """
    Run the mobile agent asynchronously with the given instruction.

    - **instruction**: The user's instruction for the agent.
    - **max_steps**: The maximum number of steps the agent can take.
    - **api_key**: The API key for the OpenAI model.
    - **base_url**: The base URL for the OpenAI API.
    - **model_name**: The name of the model to use.
    """
    try:
        # Run the synchronous function in a thread pool to make it async
        result = await asyncio.to_thread(
            run_mobile_agent,
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
async def run_agent_v4_async_endpoint(request: AgentV4Request):
    """
    Run the mobile agent v4 asynchronously with the given instruction using the optimized mobile_agent_v4 engine.

    - **instruction**: The user's instruction for the agent.
    - **max_steps**: The maximum number of steps the agent can take.
    - **api_key**: The API key for the OpenAI model.
    - **base_url**: The base URL for the OpenAI API.
    - **model_name**: The name of the model to use.
    - **output_path**: The output path for saving agent execution logs and screenshots.
    """
    try:
        result = await run_mobile_agent_v4_async(
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

