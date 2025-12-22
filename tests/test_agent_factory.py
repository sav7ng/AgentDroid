"""
测试 Agent 工厂和 Mobile-Use-Agent
"""

from agents.factory import AgentFactory
from agents.mobile_use_agent import MobileUseAgent


def test_agent_factory():
    """测试 Agent 工厂功能"""
    
    print("=" * 80)
    print("测试 Agent 工厂")
    print("=" * 80)
    
    # 1. 列出已注册的 Agent 类型
    print("\n1. 已注册的 Agent 类型:")
    agent_types = AgentFactory.list_agents()
    for agent_type in agent_types:
        print(f"   - {agent_type}")
    
    # 2. 检查 mobile-use-agent 是否已注册
    print("\n2. 检查 mobile-use-agent 是否已注册:")
    is_registered = AgentFactory.is_registered("mobile-use-agent")
    print(f"   ✅ 已注册" if is_registered else "   ❌ 未注册")
    
    # 3. 创建 Mobile-Use-Agent 实例
    print("\n3. 创建 Mobile-Use-Agent 实例:")
    try:
        agent = AgentFactory.create_agent(
            agent_type="mobile-use-agent",
            config={
                "api_key": "test_key",
                "base_url": "http://test_url",
                "model_name": "test_model",
                "max_steps": 10
            }
        )
        print(f"   ✅ 成功创建: {agent}")
        
        # 4. 获取 Agent 信息
        print("\n4. Agent 信息:")
        info = agent.get_agent_info()
        for key, value in info.items():
            print(f"   - {key}: {value}")
        
    except Exception as e:
        print(f"   ❌ 创建失败: {e}")
    
    # 5. 测试不支持的 Agent 类型
    print("\n5. 测试不支持的 Agent 类型:")
    try:
        agent = AgentFactory.create_agent(
            agent_type="non-existent-agent",
            config={}
        )
        print(f"   ❌ 应该抛出异常但没有")
    except ValueError as e:
        print(f"   ✅ 正确抛出异常: {e}")
    
    print("\n" + "=" * 80)
    print("✅ 所有测试通过!")
    print("=" * 80)


def test_mobile_use_agent_direct():
    """测试直接创建 MobileUseAgent"""
    
    print("\n" + "=" * 80)
    print("测试直接创建 MobileUseAgent")
    print("=" * 80)
    
    try:
        agent = MobileUseAgent(
            api_key="test_key",
            base_url="http://test_url",
            model_name="test_model",
            max_steps=10
        )
        print(f"\n✅ 直接创建成功: {agent}")
        
        info = agent.get_agent_info()
        print("\nAgent 信息:")
        for key, value in info.items():
            print(f"   - {key}: {value}")
        
    except Exception as e:
        print(f"\n❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_agent_factory()
    test_mobile_use_agent_direct()
