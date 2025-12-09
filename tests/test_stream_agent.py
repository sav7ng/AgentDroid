"""
流式 Agent 测试脚本
演示如何使用 run_mobile_agent_stream 函数
"""

import os
from agent_core import run_mobile_agent_stream

def test_stream_agent():
    """测试流式 Agent"""
    
    # 配置参数
    instruction = "打开设置"
    max_steps = 10
    api_key = os.getenv("OPENAI_API_KEY", "w6x1nIS9zuDmW8GQnnMTljyoDot4KbG9")
    base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")
    model_name = os.getenv("MODEL_NAME", "gui-owl")
    
    print("=" * 80)
    print("开始运行流式 Mobile Agent")
    print("=" * 80)
    print(f"指令: {instruction}")
    print(f"最大步数: {max_steps}")
    print(f"模型: {model_name}")
    print("=" * 80)
    print()
    
    # 运行流式 Agent
    event_count = 0
    current_step = None
    
    try:
        for event in run_mobile_agent_stream(
            instruction=instruction,
            max_steps=max_steps,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            output_dir="../agent_outputs"
        ):
            event_count += 1
            event_type = event.get("event_type")
            step = event.get("step")
            data = event.get("data", {})
            
            # 处理不同类型的事件
            if event_type == "task_init":
                print(f"\n📋 任务初始化")
                print(f"   任务ID: {event['task_id']}")
                print(f"   输出目录: {data.get('output_dir')}")
                
            elif event_type == "device_connected":
                print(f"\n📱 设备已连接")
                print(f"   设备型号: {data.get('device_model')}")
                
            elif event_type == "step_start":
                current_step = step
                print(f"\n{'='*60}")
                print(f"▶️  步骤 {step}/{data.get('total_steps')} 开始")
                print(f"{'='*60}")
                
            elif event_type == "screenshot":
                print(f"📸 截图完成")
                print(f"   尺寸: {data.get('width')}x{data.get('height')}")
                print(f"   保存路径: {data.get('screenshot_path')}")
                
            elif event_type == "llm_call_start":
                print(f"🤖 开始调用 LLM API...")
                print(f"   模型: {data.get('model')}")
                
            elif event_type == "llm_chunk":
                # 实时打印LLM输出片段
                chunk = data.get('chunk', '')
                print(chunk, end='', flush=True)
                
            elif event_type == "llm_complete":
                print(f"\n✅ LLM 响应完成")
                print(f"   响应长度: {data.get('response_length')} 字符")
                print(f"   接收块数: {data.get('chunks_received')}")
                print(f"   保存路径: {data.get('response_path')}")
                
            elif event_type == "action_parsed":
                print(f"\n🎯 动作解析完成")
                action = data.get('action', {})
                print(f"   动作类型: {action.get('action')}")
                print(f"   描述: {action.get('description')}")
                thinking = data.get('thinking', '')
                if thinking:
                    print(f"\n💭 思考过程:")
                    print(f"   {thinking[:200]}..." if len(thinking) > 200 else f"   {thinking}")
                
            elif event_type == "action_executing":
                print(f"\n⚙️  执行动作中...")
                print(f"   动作: {data.get('action')}")
                print(f"   描述: {data.get('description')}")
                
            elif event_type == "action_completed":
                print(f"✅ 动作执行完成")
                print(f"   状态: {data.get('status')}")
                
            elif event_type == "step_end":
                print(f"\n⏹️  步骤 {step} 结束")
                print(f"   状态: {data.get('status')}")
                if data.get('error'):
                    print(f"   错误: {data.get('error')}")
                    
            elif event_type == "task_completed":
                print(f"\n{'='*60}")
                print(f"🎉 任务完成!")
                print(f"{'='*60}")
                print(f"   最终状态: {data.get('status')}")
                print(f"   总步数: {data.get('total_steps')}")
                print(f"   输出目录: {data.get('output_dir')}")
                print(f"   元数据路径: {data.get('metadata_path')}")
                print(f"   执行日志: {data.get('log_path')}")
                
            elif event_type == "error":
                print(f"\n❌ 错误发生")
                print(f"   类型: {data.get('error_type')}")
                print(f"   消息: {data.get('message')}")
                if data.get('continue'):
                    print(f"   ⚠️  继续执行下一步")
                
            elif event_type == "no_action":
                print(f"\n⚠️  {data.get('message')}")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断任务")
    except Exception as e:
        print(f"\n\n❌ 发生异常: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*80}")
    print(f"总共处理了 {event_count} 个事件")
    print(f"{'='*80}")


def test_stream_with_web_integration():
    """演示如何将流式输出与Web服务集成"""
    import json
    
    print("\n演示: 流式输出的 JSON 格式 (适用于Web API)")
    print("=" * 80)
    
    instruction = "打开设置"
    max_steps = 5
    api_key = os.getenv("OPENAI_API_KEY", "w6x1nIS9zuDmW8GQnnMTljyoDot4KbG9")
    base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")
    model_name = os.getenv("MODEL_NAME", "gui-owl")
    
    try:
        for event in run_mobile_agent_stream(
            instruction=instruction,
            max_steps=max_steps,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name
        ):
            # 模拟发送到Web前端的JSON格式
            # 在实际应用中,这可以通过 WebSocket 或 SSE 发送
            json_event = json.dumps(event, ensure_ascii=False, indent=2)
            print(f"\n📤 发送事件到前端:")
            print(json_event)
            print("-" * 80)
            
            # 如果是截图事件,可以选择不打印base64数据以节省空间
            if event.get("event_type") == "screenshot":
                print("(截图数据已省略,实际会包含base64编码的图片)")
                
    except KeyboardInterrupt:
        print("\n⚠️  演示中断")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        test_stream_with_web_integration()
    else:
        test_stream_agent()
