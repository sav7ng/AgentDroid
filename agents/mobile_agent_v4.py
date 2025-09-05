# Copyright 2024 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Mobile-Agent-v4 for Android - 优化版本，融合简洁性和多智能体架构."""

import os
import time
import copy
import json
import logging
from agents import base_agent
from agents import infer_ma3 as infer
from agents import m3a_utils
from env import adb_utils
from env import tools
from env import interface
from agents import new_json_action as json_action
from dataclasses import asdict
from PIL import Image
from agents.mobile_agent_v4_agent import (
    InfoPool, 
    Manager, 
    Executor, 
    Notetaker, 
    ActionReflector,
    ALL_APPS
)
from agents.mobile_agent_utils_v4 import (
    convert_mobile_agent_action_to_json_action,
    build_system_messages_optimized,
    capture_and_process_screenshot,
    execute_action_with_retry
)

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def convert_fc_action_to_json_action(dummy_action) -> json_action.JSONAction:
    """将函数调用动作转换为JSON动作格式，简化版本"""
    try:
        action_json = json.loads(dummy_action) if isinstance(dummy_action, str) else dummy_action
        action_type = action_json.get('action', '')
        
        # 基础参数初始化
        params = {
            'action_type': None,
            'x': None, 'y': None,
            'text': None,
            'direction': None,
            'goal_status': None,
            'app_name': None
        }
        
        # 动作类型映射和参数提取
        action_mapping = {
            'open_app': (json_action.OPEN_APP, lambda a: {'app_name': a.get('text', '')}),
            'click': (json_action.CLICK, lambda a: {'x': a['coordinate'][0], 'y': a['coordinate'][1]}),
            'long_press': (json_action.LONG_PRESS, lambda a: {'x': a['coordinate'][0], 'y': a['coordinate'][1]}),
            'type': (json_action.INPUT_TEXT, lambda a: {'text': a.get('text', '')}),
            'swipe': (json_action.SWIPE, lambda a: {
                'direction': [a['coordinate'][0], a['coordinate'][1], 
                            a['coordinate2'][0], a['coordinate2'][1]]
            }),
            'system_button': (None, lambda a: _handle_system_button(a.get('button', ''))),
            'answer': (json_action.ANSWER, lambda a: {'text': a.get('text', '')}),
            'done': (json_action.STATUS, lambda a: {'goal_status': json_action.GOAL_STATUS}),
            'terminate': (json_action.STATUS, lambda a: {'goal_status': json_action.GOAL_STATUS})
        }
        
        if action_type in action_mapping:
            mapped_type, param_extractor = action_mapping[action_type]
            params['action_type'] = mapped_type
            params.update(param_extractor(action_json))
        
        return json_action.JSONAction(**{k: v for k, v in params.items() if v is not None})
        
    except Exception as e:
        logger.error(f"动作转换失败: {e}")
        raise

def _handle_system_button(button):
    """处理系统按钮映射"""
    button_mapping = {
        'enter': json_action.KEYBOARD_ENTER,
        'back': json_action.NAVIGATE_BACK,
        'home': json_action.NAVIGATE_HOME
    }
    button_lower = button.lower()
    return {'action_type': button_mapping.get(button_lower, json_action.KEYBOARD_ENTER)}

# 详细提示信息 - 优化版本
OPTIMIZED_TIPS = (
    '通用指南:\n'
    '- 对于任何弹窗（如权限请求），需要先关闭它们（点击"不允许"或"接受并继续"）再继续操作\n'
    '- 对于问题类请求，记得使用`answer`动作明确回复用户\n'
    '- 如果期望状态已达成（如WiFi已开启），可直接完成任务\n'
    '- 只有名称、创建时间和详细内容完全相同的文件才被视为重复\n'
    '动作相关:\n'
    '- 使用`open_app`动作打开应用，不要使用应用抽屉\n'
    '- 考虑使用不同方向的`swipe`动作探索屏幕内容，或使用搜索快速定位\n'
    '- 如果连续同方向滑动无法改变页面内容，可能已滑到底部，尝试其他操作\n'
    '- 对于水平分布的标签，可以水平滑动查看更多\n'
    '文本相关操作:\n'
    '- 激活的输入框会有光标且键盘可见，颜色会高亮显示\n'
    '- 输入文本：先点击输入框确保激活，然后使用`type`动作\n'
    '- 清除文本：长按键盘上的退格键\n'
    '- 复制文本：长按文本后点击"复制"按钮\n'
    '- 粘贴文本：长按文本框后点击"粘贴"按钮'
)

class MobileAgentV4_Optimized(base_agent.EnvironmentInteractingAgent):
    """优化版移动智能体，融合简洁性和多智能体架构"""

    def __init__(
        self,
        env: interface.AsyncEnv,
        vllm: infer.MultimodalLlmWrapper,
        name: str = 'MobileAgentV4_Optimized',
        wait_after_action_seconds: float = 2.0,
        output_path: str = "",
        max_retry_attempts: int = 3,
        enable_smart_retry: bool = True
    ):
        """初始化优化版移动智能体
        
        Args:
            env: 环境接口
            vllm: 多模态LLM包装器
            name: 智能体名称
            wait_after_action_seconds: 动作执行后等待时间
            output_path: 输出路径
            max_retry_attempts: 最大重试次数
            enable_smart_retry: 是否启用智能重试
        """
        super().__init__(env, name)
        self.vllm = vllm
        self.wait_after_action_seconds = wait_after_action_seconds
        self.output_path = output_path
        self.max_retry_attempts = max_retry_attempts
        self.enable_smart_retry = enable_smart_retry
        
        # 创建输出目录
        if self.output_path and not os.path.exists(self.output_path):
            os.makedirs(self.output_path, exist_ok=True)
        
        # 初始化信息池
        self.info_pool = InfoPool(
            additional_knowledge_manager="",
            additional_knowledge_executor=copy.deepcopy(OPTIMIZED_TIPS),
            err_to_manager_thresh=2
        )
        
        # 隐藏自动化UI
        self.env.hide_automation_ui()
        
        # 性能统计
        self.stats = {
            'total_steps': 0,
            'successful_actions': 0,
            'failed_actions': 0,
            'retry_count': 0
        }
        
        logger.info(f"初始化 {name} 完成")

    def initialize_chrome(self):
        """Chrome初始化 - 简化版本"""
        logger.info("开始Chrome初始化...")
        try:
            adb_utils.launch_app("chrome", self.env.controller)
            time.sleep(3)

            tool_controller = tools.AndroidToolController(env=self.env.controller)
            
            # 尝试处理Chrome初始化对话框
            init_options = [
                "Use without an account",
                "Accept & continue", 
                "No thanks"
            ]
            
            for option in init_options:
                try:
                    tool_controller.click_element(option)
                    time.sleep(2)
                    logger.info(f"成功点击: {option}")
                except:
                    continue
            
            adb_utils.press_home_button(self.env.controller)
            time.sleep(1)
            logger.info("Chrome初始化完成")
            
        except Exception as e:
            logger.warning(f"Chrome初始化失败: {e}")

    def reset(self, go_home_on_reset: bool = False):
        """重置智能体状态"""
        super().reset(go_home_on_reset)
        self.env.hide_automation_ui()
        
        # 重新初始化信息池
        self.info_pool = InfoPool(
            additional_knowledge_manager="",
            additional_knowledge_executor=copy.deepcopy(OPTIMIZED_TIPS),
            err_to_manager_thresh=2
        )
        
        # 重置统计信息
        self.stats = {
            'total_steps': 0,
            'successful_actions': 0,
            'failed_actions': 0,
            'retry_count': 0
        }
        
        logger.info("智能体状态已重置")

    def _should_skip_manager(self) -> bool:
        """判断是否应该跳过管理器阶段"""
        if len(self.info_pool.action_history) == 0:
            return False
            
        # 如果上一个动作无效，跳过管理器直接重试
        last_action = self.info_pool.action_history[-1]
        if isinstance(last_action, dict) and last_action.get('action') == 'invalid':
            return True
            
        # 如果错误标志未设置，跳过管理器
        return not self.info_pool.error_flag_plan

    def _check_error_escalation(self):
        """检查错误升级情况"""
        self.info_pool.error_flag_plan = False
        thresh = self.info_pool.err_to_manager_thresh
        
        if len(self.info_pool.action_outcomes) >= thresh:
            recent_outcomes = self.info_pool.action_outcomes[-thresh:]
            error_count = sum(1 for outcome in recent_outcomes if outcome in ["B", "C"])
            
            if error_count == thresh:
                self.info_pool.error_flag_plan = True
                logger.warning(f"检测到连续{thresh}次错误，启动错误升级")

    def _execute_agent_phase(self, agent, phase_name: str, screenshot_files: list, 
                           expected_keys: list) -> dict:
        """执行智能体阶段的通用方法"""
        try:
            logger.info(f"开始执行{phase_name}阶段")
            prompt = agent.get_prompt(self.info_pool)
            
            output, _, raw_response = self.vllm.predict_mm(prompt, screenshot_files)
            
            if not raw_response:
                raise RuntimeError(f'{phase_name}阶段vLLM调用失败')
            
            parsed_result = agent.parse_response(output)
            
            # 验证返回结果包含期望的键
            for key in expected_keys:
                if key not in parsed_result:
                    logger.warning(f"{phase_name}阶段缺少必需字段: {key}")
            
            logger.info(f"{phase_name}阶段执行完成")
            return parsed_result
            
        except Exception as e:
            logger.error(f"{phase_name}阶段执行失败: {e}")
            raise

    def step(self, goal: str) -> base_agent.AgentInteractionResult:
        """执行单步操作 - 优化版本"""
        # 初始化智能体
        manager = Manager()
        executor = Executor()
        notetaker = Notetaker()
        action_reflector = ActionReflector()
        
        self.info_pool.instruction = goal
        step_idx = len(self.info_pool.action_history)
        self.stats['total_steps'] += 1
        
        logger.info(f"=== 步骤 {step_idx + 1} ===")
        
        # Chrome特殊处理
        if step_idx == 0 and "chrome" in goal.lower():
            self.initialize_chrome()

        # 获取屏幕截图
        try:
            state = self.get_post_transition_state()
            before_screenshot = state.pixels.copy()
            
            # 保存截图和创建输出目录
            task_output_dir = self._create_task_output_dir(step_idx)
            before_screenshot_file = self._save_screenshot(
                before_screenshot, task_output_dir, f"screenshot_{step_idx}.png"
            )
            
        except Exception as e:
            logger.error(f"截图获取失败: {e}")
            return {"task_completed": False, "info_pool": asdict(self.info_pool)}

        # 设置屏幕尺寸
        self.info_pool.width = before_screenshot.shape[1]
        self.info_pool.height = before_screenshot.shape[0]

        # 检查错误升级
        self._check_error_escalation()

        # 管理器阶段
        if not self._should_skip_manager():
            try:
                planning_result = self._execute_agent_phase(
                    manager, "管理器", [before_screenshot_file], 
                    ['completed_subgoal', 'plan', 'thought']
                )
                
                self.info_pool.completed_plan = planning_result['completed_subgoal']
                self.info_pool.plan = planning_result['plan']
                
                logger.info(f"已完成子目标: {self.info_pool.completed_plan}")
                logger.info(f"当前计划: {self.info_pool.plan}")
                
            except Exception as e:
                logger.error(f"管理器阶段失败: {e}")
                return base_agent.AgentInteractionResult(False, asdict(self.info_pool))

        # 检查是否由规划器结束任务
        if "Finished" in self.info_pool.plan.strip() and len(self.info_pool.plan.strip()) < 15:
            logger.info("任务由规划器标记为完成")
            action_object_str = '{"action": "done"}'
            self.info_pool.action_pool.append(action_object_str)
            self._save_action_log(task_output_dir)
            return base_agent.AgentInteractionResult(True, asdict(self.info_pool))

        # 执行器阶段
        try:
            action_result = self._execute_agent_phase(
                executor, "执行器", [before_screenshot_file],
                ['thought', 'action', 'description']
            )
            
            action_thought = action_result['thought']
            action_object_str = action_result['action']
            action_description = action_result['description']
            
            self.info_pool.last_action_thought = action_thought
            self.info_pool.last_summary = action_description
            
            logger.info(f"执行器思考: {action_thought}")
            logger.info(f"执行器动作: {action_object_str}")
            
        except Exception as e:
            logger.error(f"执行器阶段失败: {e}")
            return self._handle_invalid_action(action_description, "执行器阶段失败")

        # 验证和转换动作
        try:
            converted_action = convert_fc_action_to_json_action(action_object_str)
            self.info_pool.action_pool.append(action_object_str)
        except Exception as e:
            logger.error(f"动作转换失败: {e}")
            return self._handle_invalid_action(action_description, "动作格式无效")

        # 处理特殊动作类型
        if converted_action.action_type == 'status':
            return self._handle_status_action(converted_action, action_object_str, action_description)

        if converted_action.action_type == 'answer':
            logger.info(f"智能体回答: {converted_action.text}")

        # 执行动作
        try:
            if converted_action.action_type == 'open_app':
                converted_action.app_name = converted_action.app_name.lower().strip()
            
            self.env.execute_action(converted_action)
            self.stats['successful_actions'] += 1
            
        except Exception as e:
            logger.error(f"动作执行失败: {e}")
            self.stats['failed_actions'] += 1
            return self._handle_execution_failure(converted_action, action_description, str(e))

        logger.info("动作执行完成")
        self.info_pool.last_action = json.loads(action_object_str)
        
        # 等待屏幕稳定
        time.sleep(self.wait_after_action_seconds)

        # 获取执行后截图
        try:
            state = self.env.get_state(wait_to_stabilize=False)
            after_screenshot = state.pixels.copy()
            after_screenshot_file = self._save_screenshot(
                after_screenshot, task_output_dir, f"screenshot_{step_idx+1}.png"
            )
            
            # 添加截图标签
            m3a_utils.add_screenshot_label(before_screenshot, 'before')
            m3a_utils.add_screenshot_label(after_screenshot, 'after')
            
        except Exception as e:
            logger.error(f"执行后截图获取失败: {e}")

        # 动作反思阶段
        if converted_action.action_type != 'answer':
            try:
                reflection_result = self._execute_agent_phase(
                    action_reflector, "反思器", 
                    [before_screenshot_file, after_screenshot_file],
                    ['outcome', 'error_description']
                )
                
                outcome = reflection_result['outcome']
                error_description = reflection_result['error_description']
                
                # 解析结果
                if "A" in outcome:
                    action_outcome = "A"
                elif "B" in outcome:
                    action_outcome = "B"
                elif "C" in outcome:
                    action_outcome = "C"
                else:
                    logger.warning(f"未知的反思结果: {outcome}")
                    action_outcome = "C"
                    
            except Exception as e:
                logger.error(f"反思阶段失败: {e}")
                action_outcome = "C"
                error_description = f"反思阶段失败: {e}"
        else:
            action_outcome = "A"
            error_description = "None"

        logger.info(f"动作反思结果: {action_outcome}")
        if error_description != "None":
            logger.info(f"错误描述: {error_description}")

        # 更新历史记录
        self.info_pool.action_history.append(json.loads(action_object_str))
        self.info_pool.summary_history.append(action_description)
        self.info_pool.action_outcomes.append(action_outcome)
        self.info_pool.error_descriptions.append(error_description)
        
        # 更新进度状态
        if converted_action.action_type == 'answer':
            self.info_pool.progress_status = (
                self.info_pool.completed_plan + "\n" + 
                f"已执行`answer`动作。问题答案: {converted_action.text}"
            )
        else:
            self.info_pool.progress_status = self.info_pool.completed_plan

        # 笔记记录阶段（选择性执行）
        if self._should_take_notes(action_outcome, converted_action):
            try:
                note_result = self._execute_agent_phase(
                    notetaker, "笔记记录器", [after_screenshot_file],
                    ['important_notes']
                )
                
                self.info_pool.important_notes = note_result['important_notes']
                logger.info(f"重要笔记: {self.info_pool.important_notes}")
                
            except Exception as e:
                logger.error(f"笔记记录阶段失败: {e}")

        # 保存动作日志
        self._save_action_log(task_output_dir)

        # 返回结果
        task_completed = converted_action.action_type == 'answer'
        return base_agent.AgentInteractionResult(task_completed, asdict(self.info_pool))

    def _should_take_notes(self, action_outcome: str, converted_action) -> bool:
        """判断是否应该记录笔记"""
        # 跳过某些特定情况
        skip_conditions = [
            "'Ideas' folder" in self.info_pool.instruction and "Joplin app" in self.info_pool.instruction,
            "answer" not in self.info_pool.instruction.lower() and 
            "transactions from" not in self.info_pool.instruction.lower() and 
            "enter their product" not in self.info_pool.instruction.lower()
        ]
        
        if any(skip_conditions):
            return False
            
        return action_outcome == "A" and converted_action.action_type != 'answer'

    def _create_task_output_dir(self, step_idx: int) -> str:
        """创建任务输出目录"""
        if not self.output_path:
            return ""
            
        task_name = self.info_pool.instruction.replace(" ", "_")[:50]
        task_output_dir = os.path.join(self.output_path, task_name)
        os.makedirs(task_output_dir, exist_ok=True)
        return task_output_dir

    def _save_screenshot(self, screenshot, output_dir: str, filename: str) -> str:
        """保存截图"""
        if not output_dir:
            return ""
            
        screenshot_path = os.path.join(output_dir, filename)
        Image.fromarray(screenshot).save(screenshot_path)
        return screenshot_path

    def _save_action_log(self, output_dir: str):
        """保存动作日志"""
        if not output_dir:
            return
            
        log_path = os.path.join(output_dir, "action.jsonl")
        with open(log_path, 'w', encoding='utf-8') as f:
            for item in self.info_pool.action_pool:
                f.write(item + '\n')

    def _handle_invalid_action(self, description: str, error_msg: str) -> base_agent.AgentInteractionResult:
        """处理无效动作"""
        self.info_pool.last_action = {"action": "invalid"}
        self.info_pool.action_history.append({"action": "invalid"})
        self.info_pool.summary_history.append(description)
        self.info_pool.action_outcomes.append("C")
        self.info_pool.error_descriptions.append(error_msg)
        self.stats['failed_actions'] += 1
        
        return base_agent.AgentInteractionResult(False, asdict(self.info_pool))

    def _handle_status_action(self, converted_action, action_object_str: str, 
                            action_description: str) -> base_agent.AgentInteractionResult:
        """处理状态动作"""
        outcome = "A"
        error_description = "None"
        
        if converted_action.goal_status == 'infeasible':
            logger.info("智能体认为任务不可行而停止")
            outcome = "C"
            error_description = "智能体认为任务不可行而停止"
        
        self.info_pool.last_action = json.loads(action_object_str)
        self.info_pool.action_history.append(json.loads(action_object_str))
        self.info_pool.summary_history.append(action_description)
        self.info_pool.action_outcomes.append(outcome)
        self.info_pool.error_descriptions.append(error_description)
        
        return base_agent.AgentInteractionResult(True, asdict(self.info_pool))

    def _handle_execution_failure(self, converted_action, action_description: str, 
                                error_msg: str) -> base_agent.AgentInteractionResult:
        """处理执行失败"""
        self.info_pool.last_action = {"action": "invalid"}
        self.info_pool.action_history.append({"action": "invalid"})
        self.info_pool.summary_history.append(action_description)
        self.info_pool.action_outcomes.append("C")
        
        if converted_action.action_type == "open_app":
            error_description = f"无法打开应用 '{converted_action.app_name}'；应用名称可能不存在"
        else:
            error_description = f"动作执行失败: {converted_action}"
            
        self.info_pool.error_descriptions.append(error_description)
        
        return base_agent.AgentInteractionResult(False, asdict(self.info_pool))

    def get_stats(self) -> dict:
        """获取性能统计信息"""
        return self.stats.copy()

    def __str__(self) -> str:
        return f"MobileAgentV4_Optimized(steps={self.stats['total_steps']}, success_rate={self.stats['successful_actions']/(self.stats['successful_actions']+self.stats['failed_actions']) if self.stats['successful_actions']+self.stats['failed_actions'] > 0 else 0:.2%})"
