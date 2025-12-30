from PIL import Image
from openai import OpenAI
from utils.common import pil_to_base64, parse_tags
from utils.mobile_use import MobileUse
from utils.adb_connector import AdbConnectorFactory, AdbConnector
from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import Message, ContentItem, NousFnCallPrompt
from qwen_vl_utils import smart_resize
import adbutils
import json
import time
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# 导入核心日志和异常模块
from core.logger import get_logger
from core.exceptions import (
    DeviceConnectionException,
    APICallException,
    ScreenshotException,
    ActionExecutionException
)

# 获取日志记录器
logger = get_logger(__name__)

# 从环境变量读取调试模式（默认关闭）
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

# -------------------------------
# 连接 adb 设备
# -------------------------------
def get_device(adb_config: Optional[Dict[str, Any]] = None) -> tuple:
    """
    连接 ADB 设备
    
    Args:
        adb_config: ADB连接配置，格式为 {"type": "...", "params": {...}}
                   - 为 None 时使用本地默认连接
                   - type="direct": 直连远程ADB
                   - type="ssh_tunnel": SSH隧道连接
    
    Returns:
        tuple: (device, connector) - 设备对象和连接器（用于后续清理）
    """
    try:
        # 使用连接器工厂创建连接器
        connector = AdbConnectorFactory.from_dict(adb_config)
        
        # 建立连接
        device = connector.connect()
        
        return device, connector
    except Exception as e:
        logger.error("无法连接到 ADB 设备", extra={"error": str(e), "adb_config_type": adb_config.get("type") if adb_config else "local"}, exc_info=True)
        raise DeviceConnectionException(details={"error": str(e)})


def get_device_legacy():
    """连接 ADB 设备（兼容旧版本，使用本地连接）"""
    try:
        adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        device = adb.device()
        model = device.getprop('ro.product.model')
        logger.info("成功连接到 ADB 设备", extra={"device_model": model})
        return device
    except Exception as e:
        logger.error("无法连接到 ADB 设备", extra={"error": str(e)}, exc_info=True)
        raise DeviceConnectionException(details={"error": str(e)})

# -------------------------------
# 系统消息构建
# -------------------------------
def build_system_messages(resized_width, resized_height):
    mobile_use = MobileUse(cfg={"display_width_px": resized_width, "display_height_px": resized_height})
    query_messages = [Message(role="system", content=[ContentItem(text="You are a helpful assistant.")])]
    messages = NousFnCallPrompt().preprocess_fncall_messages(
        messages=query_messages,
        functions=[mobile_use.function],
        lang=None
    )
    messages = [m.model_dump() for m in messages]
    combined_text = " ".join(item.get('text', '') for m in messages for item in m.get('content', []))
    return {"role": "system", "content": combined_text}

# -------------------------------
# 截图与调整
# -------------------------------
def capture_screenshot(device):
    """截图并调整尺寸"""
    try:
        screenshot_path = "/sdcard/screen.png"
        device.shell(f"screencap -p {screenshot_path}")
        local_screenshot = f"screenshot_{int(time.time() * 1000)}.png"
        device.sync.pull(screenshot_path, local_screenshot)

        image = Image.open(local_screenshot)
        original_size = (image.width, image.height)
        
        if DEBUG_MODE:
            logger.debug("截图成功", extra={"original_size": f"{image.width}x{image.height}"})

        MIN_PIXELS, MAX_PIXELS = 3136, 5000000
        resized_height, resized_width = smart_resize(
            image.height, image.width, 
            factor=28, 
            min_pixels=MIN_PIXELS, 
            max_pixels=MAX_PIXELS
        )
        image = image.resize((resized_width, resized_height))
        
        if image.width <= 0 or image.height <= 0:
            raise ValueError("图像尺寸无效")

        if DEBUG_MODE:
            logger.debug("图像调整完成", extra={"resized_size": f"{image.width}x{image.height}"})
        
        os.remove(local_screenshot)
        
        return image
    except Exception as e:
        logger.error("截图失败", extra={"error": str(e)}, exc_info=True)
        raise ScreenshotException(details={"error": str(e)})

# -------------------------------
# 动作执行映射
# -------------------------------
def execute_click(device, args):
    """执行点击动作"""
    x, y = args['coordinate']
    device.shell(f"input tap {x} {y}")
    logger.debug("执行点击", extra={"coordinate": [x, y]})

def execute_type(device, args):
    """执行输入动作"""
    text = args["text"]
    device.shell(f'am broadcast -a ADB_INPUT_TEXT --es msg "{text}"')
    logger.debug("执行输入", extra={"text": text})

def execute_swipe(device, args):
    """执行滑动动作"""
    x1, y1 = args['coordinate']
    x2, y2 = args['coordinate2']
    duration = int(args.get('duration', 500))
    device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
    logger.debug("执行滑动", extra={"from": [x1, y1], "to": [x2, y2], "duration": duration})

def execute_key(device, args):
    """执行按键动作"""
    key = args['text'].upper()
    device.shell(f"input keyevent {key}")
    logger.debug("执行按键", extra={"key": key})

def execute_long_press(device, args):
    """执行长按动作"""
    x, y = args['coordinate']
    duration_ms = int(args['time'] * 1000)
    device.shell(f"input swipe {x} {y} {x} {y} {duration_ms}")
    logger.debug("执行长按", extra={"coordinate": [x, y], "duration_ms": duration_ms})

def execute_system_button(device, args):
    """执行系统按钮动作"""
    key_codes = {'back': 4, 'home': 3, 'menu': 82, 'enter': 66}
    button = args['button'].lower()
    if button in key_codes:
        device.shell(f"input keyevent {key_codes[button]}")
        logger.debug("执行系统按钮", extra={"button": button})
    else:
        logger.warning("未知系统按钮", extra={"button": button})

def execute_open(device, args):
    """执行打开应用动作"""
    package = args['text']
    device.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
    logger.debug("执行打开应用", extra={"package": package})

def execute_wait(device, args):
    """执行等待动作"""
    wait_time = args['time']
    time.sleep(wait_time)
    logger.debug("执行等待", extra={"time": wait_time})

ACTION_MAP = {
    'click': execute_click,
    'type': execute_type,
    'swipe': execute_swipe,
    'key': execute_key,
    'long_press': execute_long_press,
    'system_button': execute_system_button,
    'open': execute_open,
    'wait': execute_wait
}

def execute_action(device, action_content):
    """执行动作"""
    action = action_content.get('action')
    description = action_content.get('description', '')
    
    logger.info("执行动作", extra={"action": action, "description": description})
    
    if action == 'terminate':
        status = action_content.get('status', 'terminated')
        logger.info("任务终止", extra={"status": status})
        return status
    
    try:
        if action in ACTION_MAP:
            ACTION_MAP[action](device, action_content)
        else:
            logger.warning("未知动作类型", extra={"action": action})
    except Exception as e:
        error_msg = f"动作执行失败: {str(e)}"
        logger.error(error_msg, extra={"action": action, "error": str(e)}, exc_info=True)
        if DEBUG_MODE:
            logger.debug("动作详情", extra={"action_content": action_content})
        raise ActionExecutionException(action=action, message=str(e))
    
    return "continue"

# -------------------------------
# 主循环函数
# -------------------------------
def run_mobile_agent(
    instruction, 
    max_steps=50, 
    api_key="", 
    base_url="", 
    model_name="gui-owl",
    adb_config: Optional[Dict[str, Any]] = None
):
    """
    运行移动设备 Agent 主循环
    
    Args:
        instruction: 用户指令
        max_steps: 最大步数
        api_key: API密钥
        base_url: API基础URL
        model_name: 模型名称
        adb_config: ADB连接配置（可选）
    """
    logger.info(
        "开始运行 Mobile Agent",
        extra={
            "instruction": instruction,
            "max_steps": max_steps,
            "model_name": model_name,
            "adb_config_type": adb_config.get("type") if adb_config else "local"
        }
    )
    
    # 连接设备
    device, connector = get_device(adb_config)

    bot = OpenAI(api_key=api_key, base_url=base_url)
    history = []
    final_status = "max_steps_reached"

    for step in range(max_steps):
        logger.info(f"执行步骤 {step + 1}/{max_steps}")
        
        if step > 0:
            time.sleep(2)

        # 截图
        try:
            image = capture_screenshot(device)
        except ScreenshotException as e:
            return {"status": "error", "message": str(e)}

        # 构建消息
        system_message = build_system_messages(image.width, image.height)
        final_system_message = {"role": "system", "content": system_message['content']}

        history_text = "\n".join([f"Step {i+1}: {h}" for i, h in enumerate(history)])
        user_prompt = (
            f"用户指令: {instruction}\n"
            f"任务进度:\n{history_text}\n"
            "请在 <thinking> 标签中说明推理步骤，"
            "在 <tool_call> 标签中输出动作，"
            "在 <conclusion> 标签中总结动作。"
        )

        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{pil_to_base64(image)}"}}
            ]
        }

        messages = [final_system_message, user_message]

        # 调用 API
        logger.info("调用 LLM API", extra={"model": model_name, "step": step + 1})

        try:
            response = bot.chat.completions.create(model=model_name, messages=messages)

            if not response.choices:
                logger.warning("API 未返回 choices，跳过本轮")
                continue

            result_text = response.choices[0].message.content
            logger.info(
                "API 响应成功",
                extra={"step": step + 1, "response_length": len(result_text)}
            )

        except Exception as e:
            error_msg = f"API 调用失败: {type(e).__name__} - {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise APICallException(message=str(e), details={"step": step + 1})

        # 解析响应
        try:
            parsed_tags = parse_tags(result_text, ['tool_call'])
            tool_call_json = json.loads(parsed_tags.get('tool_call', '{}'))
            action_content = tool_call_json.get('arguments')
            
            if not action_content:
                logger.warning("未返回动作，停止循环", extra={"step": step + 1})
                final_status = "no_action_returned"
                break
        except Exception as e:
            logger.error(
                "解析 tool_call 失败",
                extra={"step": step + 1, "error": str(e)},
                exc_info=True
            )
            continue

        # 执行动作
        try:
            status = execute_action(device, action_content)
            # 保存完整的动作对象到 history（而非仅描述文本）
            history.append(action_content)

            if status != "continue":
                logger.info("任务完成", extra={"status": status, "total_steps": step + 1})
                final_status = status
                break
        except ActionExecutionException as e:
            # 动作执行失败，但继续下一步
            logger.warning("动作执行失败，继续下一步", extra={"error": str(e)})
            continue
    
    if final_status == "max_steps_reached":
        logger.warning(f"达到最大步数限制 ({max_steps})，任务未完成")
    
    # 清理连接
    try:
        if connector:
            connector.disconnect()
            logger.info("ADB 连接已清理")
    except Exception as e:
        logger.warning("清理 ADB 连接时出错", extra={"error": str(e)})
    
    logger.info(
        "Mobile Agent 运行结束",
        extra={
            "final_status": final_status,
            "total_history": len(history)
        }
    )
    
    return {"status": final_status, "history": history}


# -------------------------------
# 流式输出主循环函数
# -------------------------------
def run_mobile_agent_stream(
    instruction, 
    max_steps=50, 
    api_key="", 
    base_url="", 
    model_name="gui-owl",
    output_dir="agent_outputs",
    task_id=None,
    adb_config: Optional[Dict[str, Any]] = None
):
    """
    运行移动设备 Agent 主循环 (流式输出版本)
    
    Args:
        instruction: 用户指令
        max_steps: 最大步数
        api_key: API密钥
        base_url: API基础URL
        model_name: 模型名称
        output_dir: 输出目录
        task_id: 任务ID (可选,如果不提供则自动生成)
        adb_config: ADB连接配置（可选）
    
    Yields:
        dict: 事件对象,包含以下类型:
            - step_start: 步骤开始
            - screenshot: 截图数据
            - llm_chunk: LLM流式输出片段
            - llm_complete: LLM响应完成
            - action_parsed: 动作解析完成
            - action_executing: 动作执行中
            - action_completed: 动作执行完成
            - step_end: 步骤结束
            - task_completed: 任务完成
            - error: 错误信息
    """
    
    # 生成任务ID
    if task_id is None:
        task_id = str(uuid.uuid4())[:8]
    
    # 创建任务输出目录
    task_dir = Path(output_dir) / f"task_{task_id}"
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # 记录任务元信息
    metadata = {
        "task_id": task_id,
        "instruction": instruction,
        "max_steps": max_steps,
        "model_name": model_name,
        "start_time": datetime.now().isoformat(),
        "steps": [],
        "adb_config_type": adb_config.get("type") if adb_config else "local"
    }
    
    logger.info(
        "开始运行 Mobile Agent (流式模式)",
        extra={
            "task_id": task_id,
            "instruction": instruction,
            "max_steps": max_steps,
            "model_name": model_name,
            "output_dir": str(task_dir),
            "adb_config_type": adb_config.get("type") if adb_config else "local"
        }
    )
    
    # yield 任务初始化事件
    yield {
        "event_type": "task_init",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "instruction": instruction,
            "max_steps": max_steps,
            "output_dir": str(task_dir)
        }
    }
    
    connector = None
    try:
        # 连接设备
        device, connector = get_device(adb_config)
        
        yield {
            "event_type": "device_connected",
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "device_model": device.getprop('ro.product.model')
            }
        }
        
    except DeviceConnectionException as e:
        error_event = {
            "event_type": "error",
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "error_type": "device_connection",
                "message": str(e),
                "details": e.details
            }
        }
        yield error_event
        return

    bot = OpenAI(api_key=api_key, base_url=base_url)
    history = []
    final_status = "max_steps_reached"
    execution_log = []

    for step in range(max_steps):
        step_num = step + 1
        step_start_time = datetime.now()
        
        # 创建步骤目录
        step_dir = task_dir / f"step_{step_num}"
        step_dir.mkdir(exist_ok=True)
        
        step_data = {
            "step": step_num,
            "start_time": step_start_time.isoformat(),
            "screenshot_path": None,
            "llm_response": None,
            "action": None,
            "status": None,
            "error": None
        }
        
        logger.info(f"执行步骤 {step_num}/{max_steps}")
        
        # yield 步骤开始事件
        yield {
            "event_type": "step_start",
            "task_id": task_id,
            "step": step_num,
            "timestamp": step_start_time.isoformat(),
            "data": {
                "total_steps": max_steps
            }
        }
        
        if step > 0:
            time.sleep(2)

        # 截图
        try:
            image = capture_screenshot(device)
            
            # 保存截图
            screenshot_path = step_dir / "screenshot.png"
            image.save(screenshot_path)
            step_data["screenshot_path"] = str(screenshot_path)
            
            # 转换为base64
            screenshot_base64 = pil_to_base64(image)
            
            # yield 截图事件（不包含 base64 数据，避免 SSE 解析错误）
            yield {
                "event_type": "screenshot",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "screenshot_path": str(screenshot_path),
                    "width": image.width,
                    "height": image.height
                }
            }
            
        except ScreenshotException as e:
            error_event = {
                "event_type": "error",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "error_type": "screenshot",
                    "message": str(e),
                    "details": e.details
                }
            }
            step_data["error"] = str(e)
            step_data["status"] = "error"
            yield error_event
            break

        # 构建消息
        system_message = build_system_messages(image.width, image.height)
        final_system_message = {"role": "system", "content": system_message['content']}

        history_text = "\n".join([f"Step {i+1}: {h}" for i, h in enumerate(history)])
        user_prompt = (
            f"用户指令: {instruction}\n"
            f"任务进度:\n{history_text}\n"
            "请在 <thinking> 标签中说明推理步骤，"
            "在 <tool_call> 标签中输出动作，"
            "在 <conclusion> 标签中总结动作。"
        )

        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
            ]
        }

        messages = [final_system_message, user_message]

        # 流式调用 LLM API
        logger.info("调用 LLM API (流式模式)", extra={"model": model_name, "step": step_num})
        
        yield {
            "event_type": "llm_call_start",
            "task_id": task_id,
            "step": step_num,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "model": model_name
            }
        }

        try:
            # 流式调用
            stream = bot.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True
            )
            
            result_text = ""
            chunk_count = 0
            
            # 逐块处理流式响应
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        chunk_text = delta.content
                        result_text += chunk_text
                        chunk_count += 1
                        
                        # yield LLM 流式片段事件
                        yield {
                            "event_type": "llm_chunk",
                            "task_id": task_id,
                            "step": step_num,
                            "timestamp": datetime.now().isoformat(),
                            "data": {
                                "chunk": chunk_text,
                                "chunk_index": chunk_count,
                                "accumulated_length": len(result_text)
                            }
                        }
            
            # 保存完整LLM响应
            llm_response_path = step_dir / "llm_response.txt"
            with open(llm_response_path, 'w', encoding='utf-8') as f:
                f.write(result_text)
            step_data["llm_response"] = result_text
            
            logger.info(
                "LLM API 响应完成",
                extra={"step": step_num, "response_length": len(result_text), "chunks": chunk_count}
            )
            
            # yield LLM 完成事件
            yield {
                "event_type": "llm_complete",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "response_length": len(result_text),
                    "chunks_received": chunk_count,
                    "response_path": str(llm_response_path)
                }
            }

        except Exception as e:
            error_msg = f"API 调用失败: {type(e).__name__} - {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            error_event = {
                "event_type": "error",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "error_type": "api_call",
                    "message": error_msg,
                    "details": {"step": step_num}
                }
            }
            step_data["error"] = error_msg
            step_data["status"] = "error"
            yield error_event
            break

        # 解析响应
        try:
            parsed_tags = parse_tags(result_text, ['thinking', 'tool_call', 'conclusion'])
            thinking_text = parsed_tags.get('thinking', '')
            conclusion_text = parsed_tags.get('conclusion', '')
            tool_call_json = json.loads(parsed_tags.get('tool_call', '{}'))
            action_content = tool_call_json.get('arguments')
            
            if not action_content:
                logger.warning("未返回动作，停止循环", extra={"step": step_num})
                final_status = "no_action_returned"
                step_data["status"] = "no_action"
                
                yield {
                    "event_type": "no_action",
                    "task_id": task_id,
                    "step": step_num,
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "message": "LLM未返回有效动作"
                    }
                }
                break
            
            # 保存动作信息
            action_path = step_dir / "action.json"
            with open(action_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "thinking": thinking_text,
                    "action": action_content,
                    "conclusion": conclusion_text
                }, f, ensure_ascii=False, indent=2)
            step_data["action"] = action_content
            
            # yield 动作解析完成事件
            yield {
                "event_type": "action_parsed",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "action": action_content,
                    "thinking": thinking_text,
                    "conclusion": conclusion_text,
                    "action_path": str(action_path)
                }
            }
            
        except Exception as e:
            logger.error(
                "解析 tool_call 失败",
                extra={"step": step_num, "error": str(e)},
                exc_info=True
            )
            
            error_event = {
                "event_type": "error",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "error_type": "parse_action",
                    "message": str(e),
                    "details": {"step": step_num}
                }
            }
            step_data["error"] = str(e)
            step_data["status"] = "parse_error"
            yield error_event
            continue

        # 执行动作
        try:
            # yield 动作执行中事件
            yield {
                "event_type": "action_executing",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "action": action_content.get('action'),
                    "description": action_content.get('description', '')
                }
            }
            
            status = execute_action(device, action_content)
            # 保存完整的动作对象到 history（而非仅描述文本）
            history.append(action_content)
            step_data["status"] = status
            
            # yield 动作执行完成事件
            yield {
                "event_type": "action_completed",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "status": status,
                    "action": action_content.get('action'),
                    "description": action_content.get('description', '')
                }
            }

            if status != "continue":
                logger.info("任务完成", extra={"status": status, "total_steps": step_num})
                final_status = status
                
                # yield 步骤结束事件
                step_data["end_time"] = datetime.now().isoformat()
                execution_log.append(step_data)
                
                yield {
                    "event_type": "step_end",
                    "task_id": task_id,
                    "step": step_num,
                    "timestamp": datetime.now().isoformat(),
                    "data": step_data
                }
                break
                
        except ActionExecutionException as e:
            # 动作执行失败，但继续下一步
            logger.warning("动作执行失败，继续下一步", extra={"error": str(e)})
            step_data["error"] = str(e)
            step_data["status"] = "action_error"
            
            yield {
                "event_type": "error",
                "task_id": task_id,
                "step": step_num,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "error_type": "action_execution",
                    "message": str(e),
                    "continue": True
                }
            }
        
        # yield 步骤结束事件
        step_data["end_time"] = datetime.now().isoformat()
        execution_log.append(step_data)
        
        yield {
            "event_type": "step_end",
            "task_id": task_id,
            "step": step_num,
            "timestamp": datetime.now().isoformat(),
            "data": step_data
        }
    
    if final_status == "max_steps_reached":
        logger.warning(f"达到最大步数限制 ({max_steps})，任务未完成")
    
    # 更新元信息
    metadata["end_time"] = datetime.now().isoformat()
    metadata["final_status"] = final_status
    metadata["total_steps"] = len(execution_log)
    metadata["steps"] = execution_log
    
    # 保存元信息
    metadata_path = task_dir / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # 保存完整执行日志
    log_path = task_dir / "execution_log.json"
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(execution_log, f, ensure_ascii=False, indent=2)
    
    # 清理连接
    try:
        if connector:
            connector.disconnect()
            logger.info("ADB 连接已清理 (流式模式)")
    except Exception as e:
        logger.warning("清理 ADB 连接时出错 (流式模式)", extra={"error": str(e)})
    
    logger.info(
        "Mobile Agent 运行结束 (流式模式)",
        extra={
            "task_id": task_id,
            "final_status": final_status,
            "total_steps": len(execution_log),
            "output_dir": str(task_dir)
        }
    )
    
    # yield 任务完成事件
    yield {
        "event_type": "task_completed",
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "status": final_status,
            "total_steps": len(execution_log),
            "history": history,
            "output_dir": str(task_dir),
            "metadata_path": str(metadata_path),
            "log_path": str(log_path)
        }
    }
