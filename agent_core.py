from PIL import Image
from openai import OpenAI
from utils.common import pil_to_base64, parse_tags
from utils.mobile_use import MobileUse
from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import Message, ContentItem, NousFnCallPrompt
from qwen_vl_utils import smart_resize
import adbutils
import json
import time
import logging
import os

# -------------------------------
# 日志配置
# -------------------------------
LOG_LEVEL = logging.WARNING
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEBUG_MODE = LOG_LEVEL == logging.DEBUG

# -------------------------------
# 连接 adb 设备
# -------------------------------
def get_device():
    try:
        adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        device = adb.device()
        logger.info(f"设备型号: {device.getprop('ro.product.model')}")
        return device
    except Exception as e:
        logger.error(f"Failed to connect to ADB device: {e}")
        return None

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
    screenshot_path = "/sdcard/screen.png"
    device.shell(f"screencap -p {screenshot_path}")
    local_screenshot = f"screenshot_{int(time.time() * 1000)}.png"
    device.sync.pull(screenshot_path, local_screenshot)

    image = Image.open(local_screenshot)
    if DEBUG_MODE:
        logger.debug(f"原始图像尺寸: {image.width}x{image.height}")

    MIN_PIXELS, MAX_PIXELS = 3136, 5000000
    resized_height, resized_width = smart_resize(image.height, image.width, factor=28, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
    image = image.resize((resized_width, resized_height))
    if image.width <= 0 or image.height <= 0:
        raise ValueError("图像尺寸无效")

    if DEBUG_MODE:
        logger.debug(f"调整后尺寸: {image.width}x{image.height}")
    
    os.remove(local_screenshot)
    
    return image

# -------------------------------
# 动作执行映射
# -------------------------------
def execute_click(device, args):
    x, y = args['coordinate']
    device.shell(f"input tap {x} {y}")

def execute_type(device, args):
    device.shell(f'am broadcast -a ADB_INPUT_TEXT --es msg "{args["text"]}"')

def execute_swipe(device, args):
    x1, y1 = args['coordinate']
    x2, y2 = args['coordinate2']
    duration = int(args.get('duration', 500))
    device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")

def execute_key(device, args):
    device.shell(f"input keyevent {args['text'].upper()}")

def execute_long_press(device, args):
    x, y = args['coordinate']
    duration_ms = int(args['time'] * 1000)
    device.shell(f"input swipe {x} {y} {x} {y} {duration_ms}")

def execute_system_button(device, args):
    key_codes = {'back': 4, 'home': 3, 'menu': 82, 'enter': 66}
    button = args['button'].lower()
    if button in key_codes:
        device.shell(f"input keyevent {key_codes[button]}")
    else:
        logger.warning(f"未知系统按钮: {button}")

def execute_open(device, args):
    device.shell(f"monkey -p {args['text']} -c android.intent.category.LAUNCHER 1")

def execute_wait(device, args):
    time.sleep(args['time'])

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
    action = action_content.get('action')
    print(f"执行动作: {action}")
    if action == 'terminate':
        return action_content.get('status', 'terminated')
    try:
        if action in ACTION_MAP:
            ACTION_MAP[action](device, action_content)
        else:
            logger.warning(f"未知动作: {action}")
    except Exception as e:
        logger.error(f"动作执行失败: {e}")
        if DEBUG_MODE:
            logger.debug(f"动作内容: {action_content}")
    return "continue"

# -------------------------------
# 主循环函数
# -------------------------------
def run_mobile_agent(instruction, max_steps=50, api_key="", base_url="", model_name="gui-owl"):
    device = get_device()
    if not device:
        return {"status": "error", "message": "No ADB device found or failed to connect."}

    bot = OpenAI(api_key=api_key, base_url=base_url)
    history = []
    final_status = "max_steps_reached"

    for step in range(max_steps):
        print(f"=== Step {step+1} ===")
        if step > 0:
            time.sleep(2)

        try:
            image = capture_screenshot(device)
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return {"status": "error", "message": f"Failed to capture screenshot: {e}"}

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

        print(f"发送API请求 - 模型: {model_name}")

        try:
            response = bot.chat.completions.create(model=model_name, messages=messages)

            if not response.choices:
                logger.warning("API未返回choices，跳过本轮")
                continue

            result_text = response.choices[0].message.content
            print(f"API响应成功 - 内容长度: {len(result_text)} 字符")

        except Exception as e:
            logger.error(f"API调用失败: {type(e).__name__} - {e}")
            return {"status": "error", "message": f"API call failed: {e}"}

        try:
            parsed_tags = parse_tags(result_text, ['tool_call'])
            tool_call_json = json.loads(parsed_tags.get('tool_call', '{}'))
            action_content = tool_call_json.get('arguments')
            if not action_content:
                logger.warning("未返回动作，停止循环")
                final_status = "no_action_returned"
                break
        except Exception as e:
            logger.error(f"解析tool_call失败: {e}")
            continue

        status = execute_action(device, action_content)
        history.append(action_content.get('description', str(action_content)))

        if status != "continue":
            print(f"任务结束，状态: {status}")
            final_status = status
            break
    
    return {"status": final_status, "history": history}

