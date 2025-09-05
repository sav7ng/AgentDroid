import base64
import io
import os
import json
import copy
import time
import logging
from PIL import Image
from typing import Dict, List, Tuple, Optional, Any
from agents import new_json_action as json_action
from agents.coordinate_resize import convert_point_format
from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import (
    NousFnCallPrompt,
    Message,
    ContentItem,
)

# 配置日志
logger = logging.getLogger(__name__)

# 初始化提示处理器
nousprompt = NousFnCallPrompt()

def pil_to_base64_url(image: Image.Image, format: str = "JPEG") -> str:
    """
    将PIL图像转换为Base64 URL - 优化版本
    
    Args:
        image: PIL图像对象
        format: 图像格式（如"JPEG", "PNG"）
    
    Returns:
        Base64 URL字符串
    """
    try:
        # 验证图像
        if not isinstance(image, Image.Image):
            raise ValueError("输入必须是PIL图像对象")
        
        # 将图像保存到字节流
        buffered = io.BytesIO()
        
        # 优化图像质量和大小
        if format.upper() == "JPEG":
            image.save(buffered, format=format, quality=85, optimize=True)
        else:
            image.save(buffered, format=format, optimize=True)
        
        # 将字节流编码为Base64
        image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # 构建Base64 URL
        mime_type = f"image/{format.lower()}"
        base64_url = f"data:{mime_type};base64,{image_base64}"
        
        logger.debug(f"图像转换为Base64成功，大小: {len(image_base64)} 字符")
        return base64_url
        
    except Exception as e:
        logger.error(f"图像转换为Base64失败: {e}")
        raise

def message_translate(messages: List[Dict], to_format: str = 'dashscope') -> List[Dict]:
    """
    消息格式转换 - 优化版本，支持更多格式
    
    Args:
        messages: 消息列表
        to_format: 目标格式 ('dashscope', 'openai', 'qwen', 'claude')
    
    Returns:
        转换后的消息列表
    """
    if to_format == 'dashscope':
        return messages
    
    messages = copy.deepcopy(messages)
    
    try:
        if to_format == 'openai':
            return _convert_to_openai_format(messages)
        elif to_format == 'qwen':
            return _convert_to_qwen_format(messages)
        elif to_format == 'claude':
            return _convert_to_claude_format(messages)
        else:
            logger.warning(f"不支持的格式: {to_format}，返回原始格式")
            return messages
            
    except Exception as e:
        logger.error(f"消息格式转换失败: {e}")
        return messages

def _convert_to_openai_format(messages: List[Dict]) -> List[Dict]:
    """转换为OpenAI格式"""
    for msg in messages:
        if isinstance(msg['content'], str):
            msg['content'] = [{"type": "text", "text": msg['content']}]
        else:
            new_contents = []
            for content in msg['content']:
                if isinstance(content, str):
                    new_contents.append({"type": "text", "text": content})
                elif 'text' in content:
                    new_contents.append({"type": "text", "text": content['text']})
                elif 'image' in content:
                    new_contents.append({"type": "image_url", "image_url": {"url": content['image']}})
                else:
                    logger.warning(f"未知内容类型: {content}")
            msg['content'] = new_contents
    return messages

def _convert_to_qwen_format(messages: List[Dict]) -> List[Dict]:
    """转换为Qwen格式"""
    for msg in messages:
        if isinstance(msg['content'], str):
            msg['content'] = [{"type": "text", "text": msg['content']}]
        else:
            new_contents = []
            for content in msg['content']:
                if isinstance(content, str):
                    new_contents.append({"type": "text", "text": content})
                elif 'text' in content:
                    new_contents.append({"type": "text", "text": content['text']})
                elif 'image' in content:
                    new_contents.append({"type": "image", "image": content['image']})
                else:
                    logger.warning(f"未知内容类型: {content}")
            msg['content'] = new_contents
    return messages

def _convert_to_claude_format(messages: List[Dict]) -> List[Dict]:
    """转换为Claude格式"""
    # Claude格式类似OpenAI，但有一些细微差别
    return _convert_to_openai_format(messages)

def generate_user_prompt_optimized(
    instruction: str, 
    history: List[str], 
    add_info: str = '', 
    add_thought: bool = True,
    think_tag_begin: str = '<thinking>',
    think_tag_end: str = '</thinking>',
    enable_reflection: bool = False
) -> str:
    """
    生成优化的用户提示 - 融合单图和多图场景
    
    Args:
        instruction: 用户指令
        history: 历史记录
        add_info: 附加信息
        add_thought: 是否添加思考标签
        think_tag_begin: 思考开始标签
        think_tag_end: 思考结束标签
        enable_reflection: 是否启用反思模式
    
    Returns:
        生成的用户提示
    """
    user_prompt = f'用户查询: {instruction}'

    if add_thought:
        if history:
            user_prompt += f'\n任务进度（你已在当前设备上执行了以下操作）: {history}.\n'
        
        if add_info:
            user_prompt += f'\n以下提示可以帮助你完成用户任务: {add_info}.'
        
        if enable_reflection and history:
            user_prompt += f'''
在回答之前，你必须：
1. 分析上一个动作（{history[-1]}）是否合适。
2. 验证其效果是否符合预期。当你发现动作执行不正确时，需要尝试纠正或尝试其他方法，而不是终止。
3. 为下一个动作提供逐步推理。

请按以下结构在{think_tag_begin}{think_tag_end}标签中填写内容：
{think_tag_begin}
[动作分析]
(1) 正确性评估: ...
(2) 结果一致性: ...
(3) 当前截图观察: ...
(4) 下一步规划: 后续动作的逐步推理...
(5) 动作: 以祈使句形式表达下一步。

{think_tag_end}
最后提供<tool_call></tool_call> XML标签。'''
        else:
            user_prompt += f'\n在回答之前，请在{think_tag_begin}{think_tag_end}标签中逐步解释你的推理，并将它们插入到<tool_call></tool_call> XML标签之前。'
        
        user_prompt += '\n回答后，在<conclusion></conclusion>标签中总结你的动作，并将它们插入到<tool_call></tool_call> XML标签之后。'
    
    return user_prompt

def build_system_messages_optimized(
    instruction: str, 
    resized_width: int, 
    resized_height: int, 
    add_info: str = '', 
    history: str = '', 
    infer_mode: str = 'optimized_infer',
    add_thought: bool = True
) -> Tuple[Dict, Dict]:
    """
    构建优化的系统消息
    
    Args:
        instruction: 指令
        resized_width: 调整后宽度
        resized_height: 调整后高度
        add_info: 附加信息
        history: 历史记录
        infer_mode: 推理模式
        add_thought: 是否添加思考
    
    Returns:
        系统提示部分和用户提示部分的元组
    """
    try:
        # 导入移动使用功能
        from agents.function_call_mobile_answer import AndroidWorldMobileUse
        
        mobile_use = AndroidWorldMobileUse(
            cfg={"display_width_px": resized_width, "display_height_px": resized_height}
        )
        
        think_tag_begin = '<thinking>'
        think_tag_end = '</thinking>'
        
        user_prompt = generate_user_prompt_optimized(
            instruction, history, add_info, 
            add_thought=add_thought, 
            think_tag_begin=think_tag_begin, 
            think_tag_end=think_tag_end
        )

        query_messages = [
            Message(
                role="system", 
                content=[ContentItem(text="你是一个有用的助手。")]
            ),
            Message(
                role="user",
                content=[ContentItem(text=user_prompt)],
            )
        ]

        messages = nousprompt.preprocess_fncall_messages(
            messages=query_messages,
            functions=[mobile_use.function],
            lang=None,
        )
        messages = [m.model_dump() for m in messages]

        # 设置内容类型
        for msg in messages:
            for content in msg['content']:
                content['type'] = 'text'

        system_prompt_part = {'role': 'system', 'content': []}
        system_prompt_part['content'].append({
            'text': messages[0]['content'][0]['text'] + messages[0]['content'][1]['text']
        })

        user_prompt_part = {'role': 'user', 'content': []}
        user_prompt_part['content'].append({'text': messages[1]['content'][0]['text']})

        return system_prompt_part, user_prompt_part
        
    except Exception as e:
        logger.error(f"构建系统消息失败: {e}")
        # 返回简化版本
        return (
            {'role': 'system', 'content': [{'text': '你是一个有用的助手。'}]},
            {'role': 'user', 'content': [{'text': user_prompt}]}
        )

def convert_mobile_agent_action_to_json_action(
    dummy_action: Dict,
    img_ele: Any,
    src_format: str = 'abs_origin',
    tgt_format: str = 'abs_resized'
) -> Tuple[json_action.JSONAction, Dict]:
    """
    将移动智能体动作转换为JSON动作对象 - 优化版本
    
    Args:
        dummy_action: 虚拟动作字典
        img_ele: 图像元素
        src_format: 源格式
        tgt_format: 目标格式
    
    Returns:
        转换后的JSONAction对象和翻译后的动作
    """
    # 动作类型映射
    action_type_mapping = {
        "click": json_action.CLICK,
        "terminate": json_action.STATUS,
        "answer": json_action.ANSWER,
        "long_press": json_action.LONG_PRESS,
        "type": json_action.INPUT_TEXT,
        "swipe": json_action.SWIPE,
        "wait": json_action.WAIT,
        "system_button": "system_button",
        "open": json_action.OPEN_APP,
        "open_app": json_action.OPEN_APP,
    }

    # 初始化参数
    params = {
        'x': None, 'y': None,
        'text': None,
        'direction': None,
        'goal_status': None,
        'app_name': None
    }

    try:
        # 解析动作参数
        arguments = dummy_action.get('arguments', {})
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        
        action_type_org = arguments.get('action', '')
        action_type = action_type_mapping.get(action_type_org, action_type_org)

        dummy_action_translated = copy.deepcopy({
            'name': 'mobile_use', 
            'arguments': arguments
        })

        # 根据动作类型处理参数
        if action_type == json_action.INPUT_TEXT:
            params['text'] = arguments.get('text', '')

        elif action_type == json_action.SWIPE:
            start_x, start_y = arguments.get('coordinate', [0, 0])
            end_x, end_y = arguments.get('coordinate2', [0, 0])
            
            # 转换坐标格式
            start_x, start_y = convert_point_format(
                [start_x, start_y], img_ele, 
                src_format=src_format, tgt_format=tgt_format
            )
            end_x, end_y = convert_point_format(
                [end_x, end_y], img_ele, 
                src_format=src_format, tgt_format=tgt_format
            )

            dummy_action_translated['arguments']['coordinate'] = [start_x, start_y]
            dummy_action_translated['arguments']['coordinate2'] = [end_x, end_y]
            params['direction'] = [start_x, start_y, end_x, end_y]

        elif action_type in [json_action.CLICK, json_action.LONG_PRESS]:
            x, y = arguments.get('coordinate', [0, 0])
            x, y = convert_point_format(
                [x, y], img_ele, 
                src_format=src_format, tgt_format=tgt_format
            )
            dummy_action_translated['arguments']['coordinate'] = [x, y]
            params['x'], params['y'] = x, y

        elif action_type == json_action.OPEN_APP:
            params['app_name'] = arguments.get('text', '')

        elif action_type == json_action.ANSWER:
            params['text'] = arguments.get('text', '')

        elif action_type == json_action.STATUS:
            params['goal_status'] = "task_complete"

        elif action_type == 'system_button':
            button = arguments.get('button', '').lower()
            if button == 'back':
                action_type = json_action.NAVIGATE_BACK
            elif button == 'home':
                action_type = json_action.NAVIGATE_HOME
            elif button == 'enter':
                action_type = json_action.KEYBOARD_ENTER
            else:
                logger.warning(f"未知按钮: {button}")
                action_type = json_action.KEYBOARD_ENTER

        # 创建JSONAction对象
        json_action_obj = json_action.JSONAction(
            action_type=action_type,
            **{k: v for k, v in params.items() if v is not None}
        )

        return json_action_obj, dummy_action_translated

    except Exception as e:
        logger.error(f"动作转换失败: {e}")
        # 返回默认等待动作
        return (
            json_action.JSONAction(
                action_type=json_action.WAIT,
                text="1"
            ),
            {'name': 'mobile_use', 'arguments': {'action': 'wait', 'time': 1}}
        )

def capture_and_process_screenshot(device, output_dir: str = "", step_idx: int = 0) -> Tuple[Image.Image, str]:
    """
    捕获和处理截图 - 优化版本
    
    Args:
        device: 设备对象
        output_dir: 输出目录
        step_idx: 步骤索引
    
    Returns:
        处理后的图像和文件路径的元组
    """
    try:
        # 捕获截图
        screenshot_path = "/sdcard/screen.png"
        device.shell(f"screencap -p {screenshot_path}")
        
        # 生成本地文件名
        local_screenshot = f"screenshot_{int(time.time() * 1000)}_{step_idx}.png"
        if output_dir:
            local_screenshot = os.path.join(output_dir, local_screenshot)
        
        # 拉取截图
        device.sync.pull(screenshot_path, local_screenshot)
        
        # 打开和处理图像
        image = Image.open(local_screenshot)
        
        # 验证图像
        if image.width <= 0 or image.height <= 0:
            raise ValueError("图像尺寸无效")
        
        logger.debug(f"截图捕获成功: {image.width}x{image.height}")
        
        # 如果不需要保存，删除临时文件
        if not output_dir:
            try:
                os.remove(local_screenshot)
                local_screenshot = ""
            except:
                pass
        
        return image, local_screenshot
        
    except Exception as e:
        logger.error(f"截图捕获失败: {e}")
        # 返回空白图像
        blank_image = Image.new('RGB', (1080, 2340), color='white')
        return blank_image, ""

def execute_action_with_retry(
    device, 
    action_content: Dict, 
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Tuple[bool, str]:
    """
    带重试机制的动作执行 - 新增功能
    
    Args:
        device: 设备对象
        action_content: 动作内容
        max_retries: 最大重试次数
        retry_delay: 重试延迟
    
    Returns:
        (成功标志, 错误信息)的元组
    """
    from agent_core import execute_action  # 导入原有的执行函数
    
    for attempt in range(max_retries + 1):
        try:
            result = execute_action(device, action_content)
            if result != "continue":
                return True, ""
            return True, ""
            
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"动作执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {error_msg}")
            
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            else:
                return False, error_msg
    
    return False, "达到最大重试次数"

def validate_action_format(action_str: str) -> Tuple[bool, Dict, str]:
    """
    验证动作格式 - 新增功能
    
    Args:
        action_str: 动作字符串
    
    Returns:
        (有效标志, 解析后的动作, 错误信息)的元组
    """
    try:
        # 尝试解析JSON
        action_dict = json.loads(action_str)
        
        # 检查必需字段
        if 'action' not in action_dict:
            return False, {}, "缺少'action'字段"
        
        action_type = action_dict['action']
        
        # 验证动作类型
        valid_actions = {
            'click', 'long_press', 'type', 'swipe', 'system_button',
            'open_app', 'answer', 'wait', 'terminate', 'done'
        }
        
        if action_type not in valid_actions:
            return False, {}, f"无效的动作类型: {action_type}"
        
        # 验证特定动作的参数
        validation_errors = []
        
        if action_type in ['click', 'long_press']:
            if 'coordinate' not in action_dict:
                validation_errors.append("缺少'coordinate'字段")
            elif not isinstance(action_dict['coordinate'], list) or len(action_dict['coordinate']) != 2:
                validation_errors.append("'coordinate'必须是包含两个元素的列表")
        
        elif action_type == 'swipe':
            if 'coordinate' not in action_dict or 'coordinate2' not in action_dict:
                validation_errors.append("滑动动作缺少'coordinate'或'coordinate2'字段")
        
        elif action_type in ['type', 'open_app', 'answer']:
            if 'text' not in action_dict:
                validation_errors.append("缺少'text'字段")
        
        elif action_type == 'system_button':
            if 'button' not in action_dict:
                validation_errors.append("缺少'button'字段")
        
        if validation_errors:
            return False, {}, "; ".join(validation_errors)
        
        return True, action_dict, ""
        
    except json.JSONDecodeError as e:
        return False, {}, f"JSON解析错误: {e}"
    except Exception as e:
        return False, {}, f"验证错误: {e}"

def optimize_image_for_llm(image: Image.Image, max_size: Tuple[int, int] = (1024, 1024)) -> Image.Image:
    """
    为LLM优化图像 - 新增功能
    
    Args:
        image: 原始图像
        max_size: 最大尺寸 (宽度, 高度)
    
    Returns:
        优化后的图像
    """
    try:
        # 如果图像已经足够小，直接返回
        if image.width <= max_size[0] and image.height <= max_size[1]:
            return image
        
        # 计算缩放比例
        ratio = min(max_size[0] / image.width, max_size[1] / image.height)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        
        # 使用高质量重采样
        optimized_image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        logger.debug(f"图像优化: {image.size} -> {optimized_image.size}")
        return optimized_image
        
    except Exception as e:
        logger.error(f"图像优化失败: {e}")
        return image

def create_action_summary(action_dict: Dict, outcome: str, error_desc: str = "") -> str:
    """
    创建动作摘要 - 新增功能
    
    Args:
        action_dict: 动作字典
        outcome: 结果 ("A", "B", "C")
        error_desc: 错误描述
    
    Returns:
        动作摘要字符串
    """
    action_type = action_dict.get('action', '未知')
    
    # 基础描述
    descriptions = {
        'click': f"点击坐标 {action_dict.get('coordinate', [])}",
        'long_press': f"长按坐标 {action_dict.get('coordinate', [])}",
        'type': f"输入文本: {action_dict.get('text', '')}",
        'swipe': f"从 {action_dict.get('coordinate', [])} 滑动到 {action_dict.get('coordinate2', [])}",
        'system_button': f"按下系统按钮: {action_dict.get('button', '')}",
        'open_app': f"打开应用: {action_dict.get('text', '')}",
        'answer': f"回答: {action_dict.get('text', '')}",
        'wait': f"等待 {action_dict.get('time', 1)} 秒",
        'terminate': "终止任务",
        'done': "完成任务"
    }
    
    base_desc = descriptions.get(action_type, f"执行 {action_type} 动作")
    
    # 添加结果
    outcome_desc = {
        'A': "成功",
        'B': "失败(错误页面)",
        'C': "失败(无变化)"
    }
    
    result_desc = outcome_desc.get(outcome, "未知结果")
    
    summary = f"{base_desc} - {result_desc}"
    
    if error_desc and error_desc != "None":
        summary += f" ({error_desc})"
    
    return summary

# 导出的主要函数列表
__all__ = [
    'pil_to_base64_url',
    'message_translate', 
    'generate_user_prompt_optimized',
    'build_system_messages_optimized',
    'convert_mobile_agent_action_to_json_action',
    'capture_and_process_screenshot',
    'execute_action_with_retry',
    'validate_action_format',
    'optimize_image_for_llm',
    'create_action_summary'
]
