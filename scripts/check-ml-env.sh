#!/usr/bin/env bash
set -e

echo ">>> 检查 Python 环境 ..."
python3 -V || { echo "❌ 未找到 Python3"; exit 1; }

echo ">>> 检查 PyTorch + CUDA + TensorFlow ..."
python3 - <<'EOF'
import importlib, sys

def check_module(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        print(f"❌ {name} 未安装")
        return None

# 检查 PyTorch
torch = check_module("torch")
if torch:
    print(f"✅ PyTorch 版本: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"   CUDA 支持: {torch.version.cuda}, GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("   CUDA 不可用 (CPU 模式)")

# 检查 TensorFlow
tf = check_module("tensorflow")
if tf:
    print(f"✅ TensorFlow 版本: {tf.__version__}")
    if tf.test.is_built_with_cuda():
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            print(f"   CUDA 支持: GPU 数量 = {len(gpus)}")
            for i, gpu in enumerate(gpus):
                print(f"   GPU[{i}]: {gpu.name}")
        else:
            print("   CUDA 可用但未检测到 GPU")
    else:
        print("   未编译 CUDA 支持 (CPU 模式)")
EOF
