"""
测试 PhoneAgent 接入到 AgentFactory
"""

from agents.factory import AgentFactory
from agents.phone_agent_wrapper import PhoneAgentWrapper


def test_phone_agent_registration():
    """测试 PhoneAgent 是否正确注册"""
    
    print("=" * 80)
    print("测试 PhoneAgent 注册")
    print("=" * 80)
    
    # 1. 列出所有已注册的 Agent
    print("\n1. 已注册的 Agent 类型:")
    agent_types = AgentFactory.list_agents()
    for agent_type in agent_types:
        print(f"   - {agent_type}")
    
    # 2. 检查 phone-agent 是否已注册
    print("\n2. 检查 phone-agent 是否已注册:")
    is_registered = AgentFactory.is_registered("phone-agent")
    print(f"   {'✅ 已注册' if is_registered else '❌ 未注册'}")
    
    # 3. 验证两种 Agent 都已注册
    print("\n3. 验证 Agent 类型:")
    for agent_type in ["mobile-use-agent", "phone-agent"]:
        status = "✅" if AgentFactory.is_registered(agent_type) else "❌"
        print(f"   {status} {agent_type}")
    
    print("\n" + "=" * 80)


def test_create_phone_agent():
    """测试创建 PhoneAgent 实例"""
    
    print("\n" + "=" * 80)
    print("测试创建 PhoneAgent 实例")
    print("=" * 80)
    
    try:
        # 创建 PhoneAgent 实例
        agent = AgentFactory.create_agent(
            agent_type="phone-agent",
            config={
                "api_key": "test_key",
                "base_url": "http://test_url",
                "model_name": "gpt-4-vision-preview",
                "max_steps": 20,
                "device_id": None,
                "lang": "cn"
            }
        )
        
        print(f"\n✅ 成功创建 PhoneAgent: {agent}")
        
        # 获取 Agent 信息
        print("\nAgent 信息:")
        info = agent.get_agent_info()
        for key, value in info.items():
            print(f"   - {key}: {value}")
        
    except Exception as e:
        print(f"\n❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


def test_create_both_agents():
    """测试创建两种 Agent 实例"""
    
    print("\n" + "=" * 80)
    print("测试创建两种 Agent 实例")
    print("=" * 80)
    
    configs = {
        "mobile-use-agent": {
            "api_key": "test_key",
            "base_url": "http://test_url",
            "model_name": "gui-owl",
            "max_steps": 50
        },
        "phone-agent": {
            "api_key": "test_key",
            "base_url": "http://test_url",
            "model_name": "gpt-4-vision-preview",
            "max_steps": 20,
            "device_id": None,
            "lang": "cn"
        }
    }
    
    for agent_type, config in configs.items():
        print(f"\n创建 {agent_type}:")
        try:
            agent = AgentFactory.create_agent(agent_type, config)
            print(f"   ✅ 成功: {agent}")
            
            info = agent.get_agent_info()
            print(f"   类型: {info['type']}")
            print(f"   模型: {info['model']}")
            print(f"   最大步数: {info['max_steps']}")
            
        except Exception as e:
            print(f"   ❌ 失败: {e}")
    
    print("\n" + "=" * 80)


def test_phone_agent_interface():
    """测试 PhoneAgent 的接口兼容性"""
    
    print("\n" + "=" * 80)
    print("测试 PhoneAgent 接口兼容性")
    print("=" * 80)
    
    try:
        agent = PhoneAgentWrapper(
            api_key="test_key",
            base_url="http://test_url",
            model_name="gpt-4-vision-preview",
            max_steps=20,
            device_id=None,
            lang="cn"
        )
        
        print("\n✅ PhoneAgentWrapper 实例化成功")
        
        # 检查必需的方法
        print("\n检查必需的方法:")
        methods = ['run', 'run_stream', 'get_agent_info', 'from_config']
        for method in methods:
            has_method = hasattr(agent, method)
            status = "✅" if has_method else "❌"
            print(f"   {status} {method}()")
        
        # 检查 AGENT_TYPE
        print(f"\n✅ AGENT_TYPE: {agent.AGENT_TYPE}")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_phone_agent_registration()
    test_create_phone_agent()
    test_create_both_agents()
    test_phone_agent_interface()
    
    print("\n" + "=" * 80)
    print("🎉 所有测试完成!")
    print("=" * 80)
