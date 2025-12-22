`"""测试 Take_over 开关功能"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "agents"))

from phone_agent.agent import PhoneAgent, AgentConfig
from phone_agent.actions.handler import ActionHandler, ActionResult
from phone_agent.model import ModelConfig


def test_takeover_disabled():
    """测试关闭 Take_over 功能"""
    print("=" * 60)
    print("测试 1: Take_over 开关关闭 (enable_takeover=False)")
    print("=" * 60)
    
    # 创建 ActionHandler，关闭 Take_over
    handler = ActionHandler(
        device_id=None,
        enable_takeover=False
    )
    
    # 模拟 Take_over 动作
    action = {
        "_metadata": "do",
        "action": "Take_over",
        "message": "需要登录验证"
    }
    
    # 执行动作
    result = handler.execute(action, screen_width=1080, screen_height=1920)
    
    # 验证结果
    print(f"✓ 执行成功: {result.success}")
    print(f"✓ 应该终止: {result.should_finish}")
    print(f"✓ 返回消息: {result.message}")
    
    assert result.success == False, "应该返回 success=False"
    assert result.should_finish == True, "应该返回 should_finish=True 以终止任务"
    assert "disabled" in result.message.lower(), "消息应该包含 'disabled'"
    
    print("\n✅ 测试通过！Take_over 开关关闭时会直接终止任务\n")


def test_takeover_enabled():
    """测试启用 Take_over 功能"""
    print("=" * 60)
    print("测试 2: Take_over 开关打开 (enable_takeover=True)")
    print("=" * 60)
    
    # 创建一个模拟的 takeover_callback
    callback_called = {"called": False, "message": None}
    
    def mock_takeover_callback(message: str):
        callback_called["called"] = True
        callback_called["message"] = message
        print(f"  [模拟] takeover_callback 被调用，消息: {message}")
    
    # 创建 ActionHandler，启用 Take_over
    handler = ActionHandler(
        device_id=None,
        enable_takeover=True,
        takeover_callback=mock_takeover_callback
    )
    
    # 模拟 Take_over 动作
    action = {
        "_metadata": "do",
        "action": "Take_over",
        "message": "需要登录验证"
    }
    
    # 执行动作
    result = handler.execute(action, screen_width=1080, screen_height=1920)
    
    # 验证结果
    print(f"✓ 执行成功: {result.success}")
    print(f"✓ 应该终止: {result.should_finish}")
    print(f"✓ 回调被调用: {callback_called['called']}")
    print(f"✓ 回调消息: {callback_called['message']}")
    
    assert result.success == True, "应该返回 success=True"
    assert result.should_finish == False, "应该返回 should_finish=False 继续执行"
    assert callback_called["called"] == True, "应该调用 takeover_callback"
    assert callback_called["message"] == "需要登录验证", "回调消息应该正确传递"
    
    print("\n✅ 测试通过！Take_over 开关打开时会调用回调并继续执行\n")


def test_agent_config():
    """测试 AgentConfig 配置"""
    print("=" * 60)
    print("测试 3: AgentConfig enable_takeover 参数")
    print("=" * 60)
    
    # 测试默认值
    config1 = AgentConfig()
    assert config1.enable_takeover == True, "默认应该启用 Take_over"
    print("✓ 默认值: enable_takeover = True")
    
    # 测试设置为 False
    config2 = AgentConfig(enable_takeover=False)
    assert config2.enable_takeover == False, "应该可以设置为 False"
    print("✓ 自定义值: enable_takeover = False")
    
    print("\n✅ 测试通过！AgentConfig 正确支持 enable_takeover 参数\n")


def test_phone_agent_integration():
    """测试 PhoneAgent 集成"""
    print("=" * 60)
    print("测试 4: PhoneAgent 集成测试")
    print("=" * 60)
    
    # 测试配置传递
    model_config = ModelConfig(
        api_key="test-key",
        base_url="http://test.com"
    )
    
    agent_config = AgentConfig(
        max_steps=10,
        enable_takeover=False,
        verbose=False
    )
    
    try:
        agent = PhoneAgent(
            model_config=model_config,
            agent_config=agent_config
        )
        
        # 验证配置传递
        assert agent.agent_config.enable_takeover == False, "配置应该正确传递"
        assert agent.action_handler.enable_takeover == False, "配置应该传递到 ActionHandler"
        
        print("✓ PhoneAgent 创建成功")
        print("✓ enable_takeover 配置正确传递到 ActionHandler")
        
        print("\n✅ 测试通过！PhoneAgent 正确传递 enable_takeover 配置\n")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("开始测试 Take_over 开关功能")
    print("=" * 60 + "\n")
    
    try:
        test_takeover_disabled()
        test_takeover_enabled()
        test_agent_config()
        test_phone_agent_integration()
        
        print("=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        print("\n功能说明：")
        print("1. enable_takeover=False: 遇到 Take_over 时直接终止任务")
        print("2. enable_takeover=True:  遇到 Take_over 时调用回调继续原有逻辑")
        print("3. 默认值为 True，保持向后兼容")
        print("\n使用示例：")
        print("```python")
        print("# 关闭 Take_over")
        print("agent_config = AgentConfig(enable_takeover=False)")
        print("agent = PhoneAgent(agent_config=agent_config)")
        print("")
        print("# 或通过 PhoneAgentWrapper")
        print("wrapper = PhoneAgentWrapper(")
        print("    api_key='...',")
        print("    base_url='...',")
        print("    enable_takeover=False")
        print(")")
        print("```")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60 + "\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
