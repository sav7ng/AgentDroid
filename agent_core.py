from PIL import Image
from openai import OpenAI
from utils.common import pil_to_base64, parse_tags
from utils.mobile_use import MobileUse
from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import Message, ContentItem, NousFnCallPrompt
from qwen_vl_utils import smart_resize
import adbutils
import json
import time
import os

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
def get_device():
    """连接 ADB 设备"""
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
def run_mobile_agent(instruction, max_steps=50, api_key="", base_url="", model_name="gui-owl"):
    """运行移动设备 Agent 主循环"""
    logger.info(
        "开始运行 Mobile Agent",
        extra={
            "instruction": instruction,
            "max_steps": max_steps,
            "model_name": model_name
        }
    )
    
    # 连接设备
    device = get_device()

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
            history.append(action_content.get('description', str(action_content)))

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
    
    logger.info(
        "Mobile Agent 运行结束",
        extra={
            "final_status": final_status,
            "total_history": len(history)
        }
    )
    
    return {"status": final_status, "history": history}
