"""
Mobile Agent V4 Core - 基于mobile_agent_v4引擎的核心接口实现
参考run-agent业务模式，提供统一的智能体调用接口
"""

import os
import json
import logging
import asyncio
import adbutils
import time
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from agents.mobile_agent_v4 import MobileAgentV4_Optimized
from agents import infer_ma3 as infer
from env import interface
from env import adb_utils
from agents import new_json_action as json_action
from PIL import Image
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# A simplified state object to match what the agent expects.
from collections import namedtuple
State = namedtuple('State', ['pixels', 'forest', 'elements'])

class SimpleAdbEnv:
    """A simplified environment that uses adbutils directly, mimicking agent_core.py."""
    def __init__(self, device):
        self.device = device
        self.controller = device # For compatibility with agent's use of env.controller

    def get_state(self, wait_to_stabilize: bool = False) -> State:
        """Captures a screenshot and returns it as the state."""
        if wait_to_stabilize:
            time.sleep(1.0) # Simple delay to wait for screen to stabilize
        
        screenshot = self.device.screenshot()
        # Convert PIL Image to numpy array
        pixels = np.array(screenshot)
        return State(pixels=pixels, forest=None, elements=[])

    def reset(self, go_home: bool = False):
        """Resets the environment, optionally going to the home screen."""
        logger.info(f"Resetting environment. Go home: {go_home}")
        if go_home:
            self.device.shell("input keyevent 3")
            time.sleep(1.0) # Wait for home screen to settle
        return self.get_state()

    def execute_action(self, action: json_action.JSONAction):
        """Executes an action using adb shell commands."""
        action_type = action.action_type
        logger.info(f"Executing action: {action_type} with params: {action}")

        if action_type == json_action.CLICK:
            self.device.shell(f"input tap {action.x} {action.y}")
        elif action_type == json_action.INPUT_TEXT:
            # Use the broadcast method from agent_core.py for better text input
            self.device.shell(f'am broadcast -a ADB_INPUT_TEXT --es msg "{action.text}"')
        elif action_type == json_action.SWIPE:
            # Direction is a list [x1, y1, x2, y2]
            x1, y1, x2, y2 = action.direction
            self.device.shell(f"input swipe {x1} {y1} {x2} {y2} 500")
        elif action_type == json_action.OPEN_APP:
            # Use monkey to launch the app, similar to agent_core.py
            self.device.shell(f"monkey -p {action.app_name} -c android.intent.category.LAUNCHER 1")
        elif action_type == json_action.NAVIGATE_BACK:
            self.device.shell("input keyevent 4")
        elif action_type == json_action.NAVIGATE_HOME:
            self.device.shell("input keyevent 3")
        elif action_type == json_action.KEYBOARD_ENTER:
            self.device.shell("input keyevent 66")
        elif action_type == json_action.LONG_PRESS:
            self.device.shell(f"input swipe {action.x} {action.y} {action.x} {action.y} 1000")
        elif action_type in [json_action.STATUS, json_action.ANSWER]:
            # These are logical actions that don't require device interaction.
            pass
        else:
            logger.warning(f"Unsupported action type: {action_type}")

    def hide_automation_ui(self):
        """Placeholder method to satisfy the agent's call."""
        pass # Not applicable in this simple environment

class MobileAgentV4Runner:
    """Mobile Agent V4 运行器 - 封装mobile_agent_v4的业务逻辑"""
    
    def __init__(self, 
                 api_key: str,
                 base_url: str,
                 model_name: str = "gui-owl",
                 max_steps: int = 50,
                 output_path: str = "./agent_outputs",
                 wait_after_action_seconds: float = 2.0):
        """
        初始化Mobile Agent V4运行器
        
        Args:
            api_key: OpenAI API密钥
            base_url: OpenAI API基础URL
            model_name: 使用的模型名称
            max_steps: 最大执行步数
            output_path: 输出路径
            wait_after_action_seconds: 动作执行后等待时间
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.max_steps = max_steps
        self.output_path = output_path
        self.wait_after_action_seconds = wait_after_action_seconds
        
        # 创建输出目录
        os.makedirs(self.output_path, exist_ok=True)
        
        # 初始化组件
        self.env = self._initialize_environment()
        self.vllm = self._initialize_vllm()
        self.agent = self._initialize_agent()
        
        logger.info(f"MobileAgentV4Runner初始化完成，模型: {model_name}")

    def _get_adb_device(self):
        """获取ADB设备连接"""
        try:
            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            device = adb.device()
            logger.info(f"设备型号: {device.getprop('ro.product.model')}")
            return device
        except Exception as e:
            logger.error(f"Failed to connect to ADB device: {e}")
            raise

    def _initialize_environment(self) -> SimpleAdbEnv:
        """初始化Android环境"""
        try:
            adb_device = self._get_adb_device()
            env = SimpleAdbEnv(adb_device)
            logger.info("Simple ADB environment initialized successfully")
            return env
        except Exception as e:
            logger.error(f"Android环境初始化失败: {e}")
            raise

    def _initialize_vllm(self) -> infer.MultimodalLlmWrapper:
        """初始化多模态LLM包装器"""
        try:
            vllm = infer.GUIOwlWrapper(
                api_key=self.api_key,
                base_url=self.base_url,
                model_name=self.model_name
            )
            logger.info(f"vLLM包装器初始化成功，模型: {self.model_name}")
            return vllm
        except Exception as e:
            logger.error(f"vLLM包装器初始化失败: {e}")
            raise

    def _initialize_agent(self) -> MobileAgentV4_Optimized:
        """初始化Mobile Agent V4智能体"""
        try:
            if not self.env:
                self.env = self._initialize_environment()
            if not self.vllm:
                self.vllm = self._initialize_vllm()
                
            agent = MobileAgentV4_Optimized(
                env=self.env,
                vllm=self.vllm,
                name='MobileAgentV4_API',
                wait_after_action_seconds=self.wait_after_action_seconds,
                output_path=self.output_path,
                max_retry_attempts=3,
                enable_smart_retry=True
            )
            
            logger.info("Mobile Agent V4智能体初始化成功")
            return agent
        except Exception as e:
            logger.error(f"Mobile Agent V4智能体初始化失败: {e}")
            raise

    def run_task(self, instruction: str) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            instruction: 用户指令
            
        Returns:
            包含执行结果的字典
        """
        try:
            logger.info(f"开始执行任务: {instruction}")
            
            # 初始化智能体（如果尚未初始化）
            if not self.agent:
                self.agent = self._initialize_agent()
            
            # 重置智能体状态
            self.agent.reset(go_home_on_reset=True)
            
            # 执行任务
            results = []
            task_completed = False
            step_count = 0
            
            while step_count < self.max_steps and not task_completed:
                step_count += 1
                logger.info(f"执行第 {step_count} 步")
                
                try:
                    # 执行单步
                    result = self.agent.step(instruction)
                    
                    # 记录结果
                    step_result = {
                        'step': step_count,
                        'completed': result.task_completed,
                        'info_pool': result.info_pool,
                        'timestamp': self._get_timestamp()
                    }
                    results.append(step_result)
                    
                    # 检查是否完成
                    if result.task_completed:
                        task_completed = True
                        logger.info(f"任务在第 {step_count} 步完成")
                        break
                        
                    # 检查是否有严重错误
                    if self._should_stop_execution(result):
                        logger.warning("检测到严重错误，停止执行")
                        break
                        
                except Exception as e:
                    logger.error(f"第 {step_count} 步执行失败: {e}")
                    step_result = {
                        'step': step_count,
                        'completed': False,
                        'error': str(e),
                        'timestamp': self._get_timestamp()
                    }
                    results.append(step_result)
                    break
            
            # 获取最终统计信息
            stats = self.agent.get_stats() if self.agent else {}
            
            # 构建返回结果
            final_result = {
                'status': 'completed' if task_completed else 'failed',
                'instruction': instruction,
                'total_steps': step_count,
                'max_steps_reached': step_count >= self.max_steps,
                'task_completed': task_completed,
                'results': results,
                'stats': stats,
                'timestamp': self._get_timestamp()
            }
            
            # 如果任务完成，添加最终答案
            if task_completed and results:
                last_result = results[-1]
                info_pool = last_result.get('info_pool', {})
                if 'last_action' in info_pool:
                    last_action = info_pool['last_action']
                    if isinstance(last_action, dict) and last_action.get('action') == 'answer':
                        final_result['answer'] = last_action.get('text', '')
            
            logger.info(f"任务执行完成，状态: {final_result['status']}")
            return final_result
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return {
                'status': 'error',
                'instruction': instruction,
                'error': str(e),
                'timestamp': self._get_timestamp()
            }

    def _should_stop_execution(self, result) -> bool:
        """判断是否应该停止执行"""
        try:
            info_pool = result.info_pool
            
            # 检查连续错误
            if 'action_outcomes' in info_pool:
                outcomes = info_pool['action_outcomes']
                if len(outcomes) >= 3:
                    recent_outcomes = outcomes[-3:]
                    if all(outcome in ['B', 'C'] for outcome in recent_outcomes):
                        return True
            
            # 检查是否有不可行标记
            if 'last_action' in info_pool:
                last_action = info_pool['last_action']
                if isinstance(last_action, dict):
                    if last_action.get('action') == 'done' or last_action.get('action') == 'terminate':
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"检查停止条件时出错: {e}")
            return False

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        import datetime
        return datetime.datetime.now().isoformat()

    def cleanup(self):
        """清理资源"""
        try:
            if self.agent:
                # 这里可以添加智能体清理逻辑
                pass
            if self.env:
                # 这里可以添加环境清理逻辑
                pass
            logger.info("资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")

    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体信息"""
        return {
            'model_name': self.model_name,
            'max_steps': self.max_steps,
            'output_path': self.output_path,
            'wait_after_action_seconds': self.wait_after_action_seconds,
            'agent_initialized': self.agent is not None,
            'env_initialized': self.env is not None,
            'vllm_initialized': self.vllm is not None
        }


def run_mobile_agent_v4(instruction: str,
                       max_steps: int,
                       api_key: str,
                       base_url: str,
                       model_name: str = "gui-owl",
                       output_path: str = "./agent_outputs") -> Dict[str, Any]:
    """
    运行Mobile Agent V4的便捷函数
    
    Args:
        instruction: 用户指令
        max_steps: 最大执行步数
        api_key: OpenAI API密钥
        base_url: OpenAI API基础URL
        model_name: 使用的模型名称
        output_path: 输出路径
        
    Returns:
        执行结果字典
    """
    runner = None
    try:
        runner = MobileAgentV4Runner(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            max_steps=max_steps,
            output_path=output_path
        )
        
        result = runner.run_task(instruction)
        return result
        
    except Exception as e:
        logger.error(f"运行Mobile Agent V4失败: {e}")
        return {
            'status': 'error',
            'instruction': instruction,
            'error': str(e),
            'timestamp': runner._get_timestamp() if runner else None
        }
    finally:
        if runner:
            runner.cleanup()


# 异步版本支持
async def run_mobile_agent_v4_async(instruction: str,
                                   max_steps: int,
                                   api_key: str,
                                   base_url: str,
                                   model_name: str = "gui-owl",
                                   output_path: str = "./agent_outputs") -> Dict[str, Any]:
    """
    异步运行Mobile Agent V4
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        run_mobile_agent_v4,
        instruction,
        max_steps,
        api_key,
        base_url,
        model_name,
        output_path
    )
