from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import re
import logging

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class InfoPool:
    """优化版信息池 - 跟踪所有智能体间的信息交换"""
    
    # 用户输入和累积知识
    instruction: str = ""
    task_name: str = ""
    additional_knowledge_manager: str = ""
    additional_knowledge_executor: str = ""
    add_info_token: str = "[add_info]"
    
    # UI元素信息
    ui_elements_list_before: str = ""
    ui_elements_list_after: str = ""
    action_pool: list = field(default_factory=list)

    # 工作记忆
    summary_history: list = field(default_factory=list)  # 动作描述列表
    action_history: list = field(default_factory=list)   # 动作列表
    action_outcomes: list = field(default_factory=list)  # 动作结果列表
    error_descriptions: list = field(default_factory=list)  # 错误描述列表

    # 当前状态
    last_summary: str = ""
    last_action: str = ""
    last_action_thought: str = ""
    important_notes: str = ""
    
    # 错误处理
    error_flag_plan: bool = False
    error_description_plan: str = ""
    err_to_manager_thresh: int = 2

    # 规划相关
    plan: str = ""
    completed_plan: str = ""
    progress_status: str = ""
    progress_status_history: list = field(default_factory=list)
    finish_thought: str = ""
    current_subgoal: str = ""

    # 屏幕尺寸
    width: int = 1092
    height: int = 2408

    # 未来任务
    future_tasks: list = field(default_factory=list)
    
    # 性能统计
    execution_time: float = 0.0
    retry_count: int = 0

class BaseAgent(ABC):
    """基础智能体抽象类 - 优化版本"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.execution_count = 0
        self.success_count = 0
    
    @abstractmethod
    def get_prompt(self, info_pool: InfoPool) -> str:
        """获取提示词"""
        pass
    
    @abstractmethod
    def parse_response(self, response: str) -> dict:
        """解析响应"""
        pass
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count

# 应用列表 - 优化版本
ALL_APPS = [
    "simple calendar pro: 日历应用",
    "settings: Android系统设置应用，用于管理蓝牙、Wi-Fi和亮度等设备设置",
    "markor: 笔记应用，用于创建、编辑、删除和管理笔记和文件夹",
    "broccoli: 食谱管理应用",
    "pro expense: 支出跟踪应用",
    "simple sms messenger: 短信应用，用于发送、回复和重发短信",
    "opentracks: 运动跟踪应用，用于记录和分析活动",
    "tasks: 任务管理应用，用于跟踪任务、截止日期和优先级",
    "clock: 具有秒表和计时器功能的应用",
    "joplin: 笔记应用",
    "retro music: 音乐播放器应用",
    "simple gallery pro: 图片查看应用",
    "camera: 拍照和录像应用",
    "chrome: 网页浏览器应用",
    "contacts: 联系人管理应用",
    "osmand: 地图和导航应用，支持添加位置标记、收藏夹和保存轨迹",
    "vlc: 媒体播放器应用，用于播放媒体文件",
    "audio recorder: 录音应用，用于录制和保存音频片段",
    "files: 文件管理器应用，用于Android文件系统，可删除和移动文件",
    "simple draw pro: 绘图应用，用于创建和保存绘画",
]

class Manager(BaseAgent):
    """管理器智能体 - 优化版本，负责高级规划和策略调整"""

    def __init__(self):
        super().__init__("Manager")

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "你是一个能够代表用户操作Android手机的智能体。你的目标是跟踪进度并制定高级计划来实现用户的请求。\n\n"
        prompt += "### 用户请求 ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        # 任务特定注意事项
        task_specific_note = self._get_task_specific_note(info_pool.instruction)

        if info_pool.plan == "":
            # 首次规划
            prompt += "---\n"
            prompt += "制定一个高级计划来实现用户的请求。如果请求复杂，将其分解为子目标。截图显示了手机的初始状态。\n"
            prompt += "重要提示：对于明确需要答案的请求，始终在计划的最后一步添加'执行`answer`动作'！请使用open_app打开应用而不是应用抽屉。\n\n"
            
            if task_specific_note:
                prompt += f"{task_specific_note}\n\n"
            
            prompt += "### 指导原则 ###\n"
            prompt += "以下指导原则将帮助你规划此请求。\n"
            prompt += "通用原则：\n"
            prompt += "1. 想要打开应用时使用`open_app`动作，不要使用应用抽屉打开应用。\n"
            prompt += "2. 如果搜索功能适用，使用搜索快速找到具有特定名称的文件或条目。\n"
            prompt += "任务特定原则：\n"
            
            if info_pool.additional_knowledge_manager:
                if isinstance(info_pool.additional_knowledge_manager, list) and len(info_pool.additional_knowledge_manager) > 1:
                    prompt += f"{info_pool.additional_knowledge_manager}\n\n"
                else:
                    knowledge = info_pool.additional_knowledge_manager[0] if isinstance(info_pool.additional_knowledge_manager, list) else info_pool.additional_knowledge_manager
                    prompt += f"{knowledge}\n\n"
            else:
                prompt += f"{info_pool.add_info_token}\n\n"
            
            prompt += "请按以下格式提供输出，包含两个部分：\n"
            prompt += "### 思考 ###\n"
            prompt += "详细解释你对计划和子目标的理由。\n\n"
            prompt += "### 计划 ###\n"
            prompt += "1. 第一个子目标\n"
            prompt += "2. 第二个子目标\n"
            prompt += "...\n"
        else:
            # 更新现有计划
            if info_pool.completed_plan != "没有已完成的子目标。":
                prompt += "### 历史操作 ###\n"
                prompt += "之前已完成的操作：\n"
                prompt += f"{info_pool.completed_plan}\n\n"
            
            prompt += "### 计划 ###\n"
            prompt += f"{info_pool.plan}\n\n"
            prompt += f"### 上次动作 ###\n"
            prompt += f"{info_pool.last_action}\n\n"
            prompt += f"### 上次动作描述 ###\n"
            prompt += f"{info_pool.last_summary}\n\n"
            prompt += "### 重要注意事项 ###\n"
            
            if info_pool.important_notes:
                prompt += f"{info_pool.important_notes}\n\n"
            else:
                prompt += "没有记录重要注意事项。\n\n"
            
            prompt += "### 指导原则 ###\n"
            prompt += "以下指导原则将帮助你规划此请求。\n"
            prompt += "通用原则：\n"
            prompt += "1. 想要打开应用时使用`open_app`动作，不要使用应用抽屉打开应用。\n"
            prompt += "2. 如果搜索功能适用，使用搜索快速找到具有特定名称的文件或条目。\n"
            prompt += "任务特定原则：\n"
            
            if info_pool.additional_knowledge_manager:
                if isinstance(info_pool.additional_knowledge_manager, list) and len(info_pool.additional_knowledge_manager) > 1:
                    prompt += f"{info_pool.additional_knowledge_manager}\n\n"
                else:
                    knowledge = info_pool.additional_knowledge_manager[0] if isinstance(info_pool.additional_knowledge_manager, list) else info_pool.additional_knowledge_manager
                    prompt += f"{knowledge}\n\n"
            else:
                prompt += f"{info_pool.add_info_token}\n\n"
            
            if info_pool.error_flag_plan:
                prompt += "### 可能卡住了！ ###\n"
                prompt += "你遇到了几次失败的尝试。以下是一些日志：\n"
                k = info_pool.err_to_manager_thresh
                recent_actions = info_pool.action_history[-k:] if len(info_pool.action_history) >= k else info_pool.action_history
                recent_summaries = info_pool.summary_history[-k:] if len(info_pool.summary_history) >= k else info_pool.summary_history
                recent_err_des = info_pool.error_descriptions[-k:] if len(info_pool.error_descriptions) >= k else info_pool.error_descriptions
                
                for i, (act, summ, err_des) in enumerate(zip(recent_actions, recent_summaries, recent_err_des)):
                    prompt += f"- 尝试: 动作: {act} | 描述: {summ} | 结果: 失败 | 反馈: {err_des}\n"

            prompt += "---\n"
            prompt += "仔细评估当前状态和提供的截图。检查当前计划是否需要修订。确定用户请求是否已完全完成。如果你确信不需要进一步的动作，在输出中将计划标记为\"已完成\"。如果用户请求未完成，更新计划。如果你因错误而卡住，逐步思考是否需要修订整体计划来解决错误。\n"
            prompt += "注意：1. 如果当前情况阻止按原计划进行或需要用户澄清，做出合理假设并相应修订计划。在这种情况下，像用户一样行动。2. 请首先参考指导原则中的有用信息和步骤进行规划。3. 如果计划中的第一个子目标已完成，请根据截图和进度及时更新计划，确保下一个子目标始终是计划中的第一项。4. 如果第一个子目标未完成，请复制上一轮的计划或根据子目标的完成情况更新计划。\n"
            prompt += "重要提示：如果下一步需要`answer`动作，确保有执行`answer`动作的计划。在这种情况下，除非最后一个动作是`answer`，否则不应将计划标记为\"已完成\"。\n"
            
            if task_specific_note:
                prompt += f"{task_specific_note}\n\n"

            prompt += "请按以下格式提供输出，包含三个部分：\n\n"
            prompt += "### 思考 ###\n"
            prompt += "解释你对更新计划和当前子目标的理由。\n\n"
            prompt += "### 历史操作 ###\n"
            prompt += "尝试在现有历史操作的顶部添加最近完成的子目标。请不要删除任何现有的历史操作。如果没有新完成的子目标，只需复制现有的历史操作。\n\n"
            prompt += "### 计划 ###\n"
            prompt += "请根据当前页面和进度更新或复制现有计划。请密切关注历史操作。除非你能从屏幕状态判断子目标确实未完成，否则请不要重复已完成内容的计划。\n"
            
        return prompt

    def _get_task_specific_note(self, instruction: str) -> str:
        """获取任务特定注意事项"""
        if ".html" in instruction:
            return "注意：.html文件可能包含额外的可交互元素，如绘图画布或游戏。在完成.html文件中的任务之前，不要打开其他应用。"
        elif "Audio Recorder" in instruction:
            return "注意：停止录音图标是一个白色方块，位于底部从左数第四个。请不要点击中间的圆形暂停图标。"
        return ""

    def parse_response(self, response: str) -> dict:
        """解析管理器响应"""
        try:
            if "### 历史操作" in response:
                thought = response.split("### 思考")[-1].split("### 历史操作")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
                completed_subgoal = response.split("### 历史操作")[-1].split("### 计划")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            else:
                thought = response.split("### 思考")[-1].split("### 计划")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
                completed_subgoal = "没有已完成的子目标。"
            
            plan = response.split("### 计划")[-1].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            
            return {
                "thought": thought, 
                "completed_subgoal": completed_subgoal,  
                "plan": plan
            }
        except Exception as e:
            logger.error(f"管理器响应解析失败: {e}")
            return {
                "thought": "解析失败", 
                "completed_subgoal": "没有已完成的子目标。",  
                "plan": "需要重新规划"
            }

# 原子动作签名 - 优化版本
from agents.new_json_action import *

ATOMIC_ACTION_SIGNATURES_V4 = {
    ANSWER: {
        "arguments": ["text"],
        "description": lambda info: "回答用户问题。使用示例：{\"action\": \"answer\", \"text\": \"你的答案内容\"}"
    },
    CLICK: {
        "arguments": ["coordinate"],
        "description": lambda info: "点击屏幕上指定(x, y)坐标的点。使用示例：{\"action\": \"click\", \"coordinate\": [x, y]}"
    },
    LONG_PRESS: {
        "arguments": ["coordinate"],
        "description": lambda info: "长按屏幕上位置(x, y)。使用示例：{\"action\": \"long_press\", \"coordinate\": [x, y]}"
    },
    TYPE: {
        "arguments": ["text"],
        "description": lambda info: "在当前激活的输入框或文本字段中输入文本。可能在激活的输入框中有光标。如果没有，请先点击输入框确认。请确保在输入之前激活了正确的输入框。使用示例：{\"action\": \"type\", \"text\": \"你要输入的文本\"}"
    },
    SYSTEM_BUTTON: {
        "arguments": ["button"],
        "description": lambda info: "按下系统按钮，包括返回、主页和回车。使用示例：{\"action\": \"system_button\", \"button\": \"Home\"}"
    },
    SWIPE: {
        "arguments": ["coordinate", "coordinate2"],
        "description": lambda info: "从坐标位置滑动到coordinate2位置。请确保滑动的起点和终点在可滑动区域内，远离键盘(y1 < 1400)。使用示例：{\"action\": \"swipe\", \"coordinate\": [x1, y1], \"coordinate2\": [x2, y2]}"
    },
    OPEN: {
        "arguments": ["text"],
        "description": lambda info: "打开应用。使用示例：{\"action\": \"open_app\", \"text\": \"应用名称\"}"
    }
}

class Executor(BaseAgent):
    """执行器智能体 - 优化版本，负责具体动作执行"""

    def __init__(self):
        super().__init__("Executor")

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "你是一个能够代表用户操作Android手机的智能体。你的目标是根据手机的当前状态和用户请求决定要执行的下一个动作。\n\n"

        prompt += "### 用户请求 ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### 整体计划 ###\n"
        prompt += f"{info_pool.plan}\n\n"
        
        prompt += "### 当前子目标 ###\n"
        current_goal = info_pool.plan
        current_goal = re.split(r'(?<=\d)\. ', current_goal)
        truncated_current_goal = ". ".join(current_goal[:4]) + '.'
        truncated_current_goal = truncated_current_goal[:-2].strip()
        prompt += f"{truncated_current_goal}\n\n"

        prompt += "### 进度状态 ###\n"
        if info_pool.progress_status:
            prompt += f"{info_pool.progress_status}\n\n"
        else:
            prompt += "尚无进度。\n\n"

        # 添加执行器特定指导原则
        if info_pool.additional_knowledge_executor:
            prompt += "### 指导原则 ###\n"
            if isinstance(info_pool.additional_knowledge_executor, list) and len(info_pool.additional_knowledge_executor) > 1:
                prompt += f"{info_pool.additional_knowledge_executor}\n"
            else:
                knowledge = info_pool.additional_knowledge_executor[0] if isinstance(info_pool.additional_knowledge_executor, list) else info_pool.additional_knowledge_executor
                prompt += f"{knowledge}\n"

        # 任务特定指导
        task_specific_guidance = self._get_task_specific_guidance(info_pool.instruction)
        if task_specific_guidance:
            prompt += f"任务特定指导：\n{task_specific_guidance}\n\n"
        else:
            prompt += "\n"
        
        prompt += "---\n"        
        prompt += "仔细检查上面提供的所有信息并决定要执行的下一个动作。如果你注意到上一个动作中有未解决的错误，像人类用户一样思考并尝试纠正它们。你必须从原子动作中选择你的动作。\n\n"
        
        prompt += "#### 原子动作 ####\n"
        prompt += "原子动作函数以`action(arguments): description`的格式列出如下：\n"

        for action, value in ATOMIC_ACTION_SIGNATURES_V4.items():
            prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info_pool)}\n"

        prompt += "\n"
        prompt += "### 最新动作历史 ###\n"
        if info_pool.action_history:
            prompt += "你之前采取的最近动作以及它们是否成功：\n"
            num_actions = min(5, len(info_pool.action_history))
            latest_actions = info_pool.action_history[-num_actions:]
            latest_summary = info_pool.summary_history[-num_actions:]
            latest_outcomes = info_pool.action_outcomes[-num_actions:]
            error_descriptions = info_pool.error_descriptions[-num_actions:]
            
            for act, summ, outcome, err_des in zip(latest_actions, latest_summary, latest_outcomes, error_descriptions):
                if outcome == "A":
                    prompt += f"动作: {act} | 描述: {summ} | 结果: 成功\n"
                else:
                    prompt += f"动作: {act} | 描述: {summ} | 结果: 失败 | 反馈: {err_des}\n"
            
            prompt += "\n"
        else:
            prompt += "尚未采取任何动作。\n\n"

        prompt += "---\n"
        prompt += "重要提示：\n1. 不要多次重复之前失败的动作。尝试改变为另一个动作。\n"
        prompt += "2. 请优先考虑当前子目标。\n\n"
        prompt += "请按以下格式提供输出，包含三个部分：\n"
        prompt += "### 思考 ###\n"
        prompt += "详细解释你选择该动作的理由。\n\n"

        prompt += "### 动作 ###\n"
        prompt += "从提供的选项中只选择一个动作或快捷方式。\n"
        prompt += "你必须使用有效的JSON格式提供你的决定，指定`action`和动作的参数。例如，如果你想打开一个应用，你应该写{\"action\":\"open_app\", \"text\": \"应用名称\"}。\n\n"
        
        prompt += "### 描述 ###\n"
        prompt += "对所选动作的简要描述。不要描述预期结果。\n"
        return prompt

    def _get_task_specific_guidance(self, instruction: str) -> str:
        """获取任务特定指导"""
        if "exact duplicates" in instruction:
            return "只有具有相同名称、日期和详细信息的两个项目才能被视为重复。"
        elif "Audio Recorder" in instruction:
            return "停止录音图标是一个白色方块，位于底部从左数第四个。请不要点击中间的圆形暂停图标。"
        return ""

    def parse_response(self, response: str) -> dict:
        """解析执行器响应"""
        try:
            thought = response.split("### 思考")[-1].split("### 动作")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            action = response.split("### 动作")[-1].split("### 描述")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            description = response.split("### 描述")[-1].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            
            return {
                "thought": thought, 
                "action": action, 
                "description": description
            }
        except Exception as e:
            logger.error(f"执行器响应解析失败: {e}")
            return {
                "thought": "解析失败", 
                "action": '{"action": "wait", "time": 1}', 
                "description": "等待1秒"
            }

class ActionReflector(BaseAgent):
    """动作反思器智能体 - 优化版本，负责验证动作效果"""

    def __init__(self):
        super().__init__("ActionReflector")

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "你是一个能够操作Android手机的智能体。你的目标是验证上次动作是否产生了预期的行为，并跟踪整体进度。\n\n"

        prompt += "### 用户请求 ###\n"
        prompt += f"{info_pool.instruction}\n\n"
        
        prompt += "### 进度状态 ###\n"
        if info_pool.completed_plan:
            prompt += f"{info_pool.completed_plan}\n\n"
        else:
            prompt += "尚无进度。\n\n"

        prompt += "---\n"
        prompt += "附加的两张图片是你上次动作前后拍摄的手机截图。\n"

        prompt += "---\n"
        prompt += "### 最新动作 ###\n"
        prompt += f"动作: {info_pool.last_action}\n"
        prompt += f"期望: {info_pool.last_summary}\n\n"

        prompt += "---\n"
        prompt += "仔细检查上面提供的信息，以确定上次动作是否产生了预期的行为。如果动作成功，相应地更新进度状态。如果动作失败，识别失败模式并提供导致此失败的潜在原因的推理。\n\n"
        prompt += "注意：对于滑动以滚动屏幕查看更多内容，如果滑动前后显示的内容完全相同，则滑动被认为是C：失败。上次动作没有产生变化。这可能是因为内容已滚动到底部。\n\n"

        prompt += "请按以下格式提供输出，包含两个部分：\n"
        prompt += "### 结果 ###\n"
        prompt += "从以下选项中选择。将你的响应给出为\"A\"、\"B\"或\"C\"：\n"
        prompt += "A: 成功或部分成功。上次动作的结果符合期望。\n"
        prompt += "B: 失败。上次动作导致错误页面。我需要返回到之前的状态。\n"
        prompt += "C: 失败。上次动作没有产生变化。\n\n"

        prompt += "### 错误描述 ###\n"
        prompt += "如果动作失败，提供错误的详细描述和导致此失败的潜在原因。如果动作成功，在这里填写\"无\"。\n"

        return prompt

    def parse_response(self, response: str) -> dict:
        """解析反思器响应"""
        try:
            outcome = response.split("### 结果")[-1].split("### 错误描述")[0].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            error_description = response.split("### 错误描述")[-1].replace("\n", " ").replace("###", "").replace("  ", " ").strip()
            
            return {
                "outcome": outcome, 
                "error_description": error_description
            }
        except Exception as e:
            logger.error(f"反思器响应解析失败: {e}")
            return {
                "outcome": "C", 
                "error_description": f"响应解析失败: {e}"
            }

class Notetaker(BaseAgent):
    """笔记记录器智能体 - 优化版本，负责记录重要信息"""

    def __init__(self):
        super().__init__("Notetaker")

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "你是一个用于操作手机的有用AI助手。你的目标是记录与用户请求相关的重要内容。\n\n"

        prompt += "### 用户请求 ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### 进度状态 ###\n"
        prompt += f"{info_pool.progress_status}\n\n"

        prompt += "### 现有重要注意事项 ###\n"
        if info_pool.important_notes:
            prompt += f"{info_pool.important_notes}\n\n"
        else:
            prompt += "没有记录重要注意事项。\n\n"

        # 任务特定指导
        task_guidance = self._get_task_guidance(info_pool.instruction)
        if task_guidance:
            prompt += f"### 指导原则 ###\n{task_guidance}\n"
        
        prompt += "---\n"
        prompt += "仔细检查上面的信息，以识别当前屏幕上需要记录的任何重要内容。\n"
        prompt += "重要提示：\n不要记录低级动作；只跟踪与用户请求相关的重要文本或视觉信息。不要重复用户请求或进度状态。不要编造你不确定的内容。\n\n"

        prompt += "请按以下格式提供输出：\n"
        prompt += "### 重要注意事项 ###\n"
        prompt += "更新的重要注意事项，结合旧的和新的。如果没有新内容要记录，复制现有的重要注意事项。\n"

        return prompt

    def _get_task_guidance(self, instruction: str) -> str:
        """获取任务特定指导"""
        if "transactions" in instruction and "Simple Gallery" in instruction:
            return "你只能记录DCIM中的交易信息，因为其他交易与任务无关。"
        elif "enter their product" in instruction:
            return "请记录每次出现的数字，以便最后计算它们的乘积。"
        return ""

    def parse_response(self, response: str) -> dict:
        """解析笔记记录器响应"""
        try:
            important_notes = response.split("### 重要注意事项")[-1].replace("\n", " ").replace("  ", " ").replace("###", "").strip()
            return {"important_notes": important_notes}
        except Exception as e:
            logger.error(f"笔记记录器响应解析失败: {e}")
            return {"important_notes": "解析失败"}
