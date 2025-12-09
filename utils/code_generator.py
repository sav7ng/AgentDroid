"""
Auto.js 代码生成器
根据 Agent 执行的 history 生成 Auto.js 脚本
"""

from typing import Generator, List, Dict, Any
from utils.openai_client import OpenAIClient
from core.logger import get_logger
from datetime import datetime
import json

logger = get_logger(__name__)

# Auto.js 脚本生成 Prompt
GENERATE_CODE_INTERPRETER = """
你是一名 Auto.js 4.x/Pro 自动化脚本专家，请根据我提供的 JSON "操作日志"生成一个可直接运行的 Auto.js 脚本。

【要求】
1. 只能输出 Auto.js 代码，不解释、不用 Markdown。
2. 禁止 async/await/Promise，全部同步执行。
3. 动作按日志顺序逐条执行。
4. 每步必须 toastLog，并 sleep(2000)。
5. 脚本必须以 "auto" 开头。
6. 必须封装以下方法：
   * safeClick(x,y)
   * safeSwipe(x1,y1,x2,y2)
   * safeLongPress(x,y,ms)
   * safeInput(text)
   * safeKey(name)
   * safeSystemButton(name)
   * safeOpenApp(appName)
   * safeWait(sec)

【Auto.js 无障碍服务 API 参考】
- click(x, y): 点击屏幕指定坐标，返回 Promise<boolean>
- longClick(x, y): 长按屏幕指定位置，返回 Promise<boolean>
- press(x, y, duration): 按住屏幕指定位置一段时间(毫秒)，返回 Promise<boolean>
- swipe(x1, y1, x2, y2, duration): 直线滑动，duration 单位毫秒，返回 Promise<boolean>
- inputText(text, index?): 输入文本(追加)，返回 Promise<boolean>
- setText(text, index?): 设置文本(覆盖)，返回 Promise<boolean>
- back(): 模拟返回键，返回 boolean
- home(): 模拟Home键，返回 boolean
- lockScreen(): 锁屏，返回 boolean
- openNotifications(): 拉出通知栏，返回 boolean
- toggleRecents(): 模拟最近任务键，返回 boolean
- currentPackage(clearCache?): 返回当前活跃窗口包名
- currentActivity(): 返回当前Activity名称
- performGesture(points, duration, delay?): 模拟手势路径，返回 Promise<boolean>

【动作映射规则】
- action=click → click(x,y)
- action=long_press → press(x,y,ms)
- action=swipe → swipe(x1,y1,x2,y2,duration)
- action=type → inputText(text) 或 setText(text)
- action=key →
  * back → back()
  * home → home()
  * enter → sendKeyCodeHeadsethook() 或 keyCode(66)
  * menu 或不支持 → 忽略
- action=system_button → 同 key 映射
- action=open → app.launchApp(text)
- action=wait → sleep(sec*1000)
- action=terminate → 不生成代码

【输入 JSON】
日志格式如下，history 中每个元素是"字符串格式的 Python 字典"，需自行解析：
{
  "status": "success",
  "history": [
    "{'action':'click','coordinate':[100,200]}",
    "{'action':'type','text':'hello'}",
    "{'action':'terminate','status':'success'}"
  ],
  "task_id": "xxx",
  "instruction": "任务名"
}

【注意事项】
1. 由于 Auto.js 无障碍 API 大部分返回 Promise，但要求同步执行，需使用同步等待方式或忽略 Promise
2. 坐标系以屏幕左上角为原点(0,0)，向右下增加
3. 时长参数单位统一为毫秒(ms)
4. 所有操作前需确保无障碍服务已启用
5. 不要开头输出```javascript和结尾输出```内容

【最终要求】
只输出最终 Auto.js 代码，不要任何多余内容。
"""


class CodeGenerator:
    """Auto.js 代码生成器"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "gpt-4"
    ):
        """
        初始化代码生成器
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
        """
        self.client = OpenAIClient(api_key, base_url, model)
        logger.info(
            "初始化代码生成器",
            extra={"model": model, "base_url": base_url}
        )
    
    def format_history_for_prompt(
        self,
        history: List[Dict[str, Any]],
        task_id: str,
        instruction: str,
        status: str = "success"
    ) -> Dict[str, Any]:
        """
        将 history 格式化为 prompt 需要的格式
        
        Args:
            history: Agent 执行的动作列表（dict 对象）
            task_id: 任务 ID
            instruction: 用户指令
            status: 任务状态
            
        Returns:
            格式化后的 JSON 对象
        """
        # 将 dict 对象转换为字符串格式
        history_strings = [str(action) for action in history]
        
        formatted = {
            "status": status,
            "history": history_strings,
            "task_id": task_id,
            "instruction": instruction
        }
        
        logger.debug(
            "格式化 history",
            extra={
                "task_id": task_id,
                "history_count": len(history),
                "status": status
            }
        )
        
        return formatted
    
    def generate_code_stream(
        self,
        history: List[Dict[str, Any]],
        task_id: str,
        instruction: str,
        status: str = "success"
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式生成 Auto.js 代码
        
        Args:
            history: Agent 执行的动作列表
            task_id: 任务 ID
            instruction: 用户指令
            status: 任务状态
            
        Yields:
            dict: 事件对象
                - codegen_start: 开始生成
                - codegen_chunk: 代码片段
                - codegen_complete: 生成完成
                - error: 错误信息
        """
        try:
            # 格式化输入
            formatted_input = self.format_history_for_prompt(
                history, task_id, instruction, status
            )
            
            input_json = json.dumps(formatted_input, ensure_ascii=False, indent=2)
            
            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": "你是一名 Auto.js 脚本专家，擅长根据操作日志生成可执行的自动化脚本。"
                },
                {
                    "role": "user",
                    "content": f"{GENERATE_CODE_INTERPRETER}\n\n{input_json}"
                }
            ]
            
            logger.info(
                "开始生成代码",
                extra={
                    "task_id": task_id,
                    "history_length": len(history),
                    "model": self.client.model
                }
            )
            
            # yield 开始事件
            yield {
                "event_type": "codegen_start",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "history_length": len(history),
                    "instruction": instruction,
                    "status": status
                }
            }
            
            # 流式调用
            generated_code = ""
            chunk_count = 0
            
            for chunk in self.client.chat_completion_stream(messages):
                generated_code += chunk
                chunk_count += 1
                
                # yield 代码片段
                yield {
                    "event_type": "codegen_chunk",
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "chunk": chunk,
                        "chunk_index": chunk_count,
                        "accumulated_length": len(generated_code)
                    }
                }
            
            logger.info(
                "代码生成完成",
                extra={
                    "task_id": task_id,
                    "code_length": len(generated_code),
                    "chunks": chunk_count
                }
            )
            
            # yield 完成事件
            yield {
                "event_type": "codegen_complete",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "code_length": len(generated_code),
                    "chunks": chunk_count,
                    "full_code": generated_code
                }
            }
            
        except Exception as e:
            error_msg = f"代码生成失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            yield {
                "event_type": "error",
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "error_type": "code_generation",
                    "message": error_msg
                }
            }
