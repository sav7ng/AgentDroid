import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# 将项目根目录添加到Python路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.mobile_agent_v4 import MobileAgentV4_Optimized
from agents.mobile_agent_v4_agent import InfoPool
from agents import base_agent

class TestMobileAgentV4(unittest.TestCase):
    """测试MobileAgentV4_Optimized智能体"""

    def setUp(self):
        """测试设置"""
        # 模拟环境和vLLM
        self.mock_env = MagicMock()
        self.mock_vllm = MagicMock()
        
        # 实例化智能体
        self.agent = MobileAgentV4_Optimized(
            env=self.mock_env,
            vllm=self.mock_vllm,
            name='TestAgentV4',
            output_path='./test_output'
        )

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists('./test_output'):
            # 清理测试输出目录
            for root, dirs, files in os.walk('./test_output', topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir('./test_output')

    def test_initialization(self):
        """测试智能体初始化"""
        self.assertEqual(self.agent.name, 'TestAgentV4')
        self.assertIsInstance(self.agent.info_pool, InfoPool)
        self.assertEqual(self.agent.wait_after_action_seconds, 2.0)
        self.assertTrue(os.path.exists('./test_output'))

    def test_reset(self):
        """测试重置功能"""
        # 修改info_pool状态
        self.agent.info_pool.instruction = "test instruction"
        self.agent.stats['total_steps'] = 10
        
        # 重置
        self.agent.reset()
        
        # 验证状态是否重置
        self.assertEqual(self.agent.info_pool.instruction, "")
        self.assertEqual(self.agent.stats['total_steps'], 0)
        self.mock_env.hide_automation_ui.assert_called_with()

    @patch('agents.mobile_agent_v4.Image.fromarray')
    @patch('agents.mobile_agent_v4.MobileAgentV4_Optimized.get_post_transition_state')
    def test_step_execution_flow(self, mock_get_state, mock_fromarray):
        """测试单步执行流程"""
        # 模拟状态和截图
        mock_state = MagicMock()
        mock_state.pixels.copy.return_value = MagicMock()
        mock_get_state.return_value = mock_state
        
        # 模拟vLLM响应
        self.mock_vllm.predict_mm.side_effect = [
            # 管理器响应
            (
                "### 思考 ###\n制定计划\n### 历史操作 ###\n无\n### 计划 ###\n1. 打开设置", 
                None, True
            ),
            # 执行器响应
            (
                "### 思考 ###\n执行打开设置\n### 动作 ###\n{\"action\": \"open_app\", \"text\": \"settings\"}\n### 描述 ###\n打开设置应用",
                None, True
            ),
            # 反思器响应
            (
                "### 结果 ###\nA: 成功\n### 错误描述 ###\n无",
                None, True
            )
        ]
        
        # 执行一步
        result = self.agent.step("打开设置")
        
        # 验证结果
        self.assertIsInstance(result, base_agent.AgentInteractionResult)
        self.assertFalse(result.task_completed)
        self.assertEqual(self.agent.info_pool.plan, "1. 打开设置")
        self.assertEqual(self.agent.info_pool.last_action['action'], "open_app")
        self.assertEqual(self.agent.info_pool.action_outcomes[-1], "A")
        self.assertEqual(self.mock_vllm.predict_mm.call_count, 3)


if __name__ == '__main__':
    unittest.main()
