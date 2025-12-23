"""测试截图超时修复"""

import sys
from pathlib import Path

# 添加 agents 目录到路径
agents_dir = Path(__file__).parent / "agents"
sys.path.insert(0, str(agents_dir))

from phone_agent.config.timing import TIMING_CONFIG
from phone_agent.device_factory import get_device_factory

def test_timing_config():
    """测试超时配置"""
    print("=== 测试超时配置 ===")
    print(f"截图超时时间: {TIMING_CONFIG.screenshot.timeout}s (默认: 30s)")
    print(f"重试次数: {TIMING_CONFIG.screenshot.retry_count} (默认: 3)")
    print(f"重试延迟: {TIMING_CONFIG.screenshot.retry_delay}s (默认: 2s)")
    print(f"Pull超时: {TIMING_CONFIG.screenshot.pull_timeout}s (默认: 10s)")
    print()

def test_screenshot_with_retry():
    """测试带重试的截图功能"""
    print("=== 测试截图功能 ===")
    print("注意：此测试需要连接 ADB 设备")
    print()
    
    try:
        device_factory = get_device_factory()
        
        # 测试默认参数（使用配置文件的值）
        print("1. 使用默认超时和重试配置...")
        screenshot = device_factory.get_screenshot()
        
        if screenshot.is_sensitive:
            print("   ⚠️ 检测到敏感屏幕，返回黑色备用图片")
        else:
            print(f"   ✅ 截图成功！尺寸: {screenshot.width}x{screenshot.height}")
        print()
        
        # 测试自定义参数
        print("2. 使用自定义超时 (5秒) 和重试次数 (2次)...")
        screenshot = device_factory.get_screenshot(timeout=5, retry_count=2)
        
        if screenshot.is_sensitive:
            print("   ⚠️ 检测到敏感屏幕，返回黑色备用图片")
        else:
            print(f"   ✅ 截图成功！尺寸: {screenshot.width}x{screenshot.height}")
        print()
        
        print("✅ 所有测试通过！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=" * 60)
    print("截图超时修复 - 测试脚本")
    print("=" * 60)
    print()
    
    # 测试配置
    test_timing_config()
    
    # 测试截图功能（需要设备连接）
    response = input("是否测试截图功能？(需要连接 ADB 设备) [y/N]: ").strip().lower()
    if response == 'y':
        test_screenshot_with_retry()
    else:
        print("跳过截图测试")
    
    print()
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
