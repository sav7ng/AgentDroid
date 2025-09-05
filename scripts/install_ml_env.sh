#!/usr/bin/env bash
set -e

# ==================================================
# 一键安装 Miniconda + ML 环境 (PyTorch + TensorFlow)
# CUDA 11.4 驱动兼容
# ==================================================

MINICONDA_DIR="$HOME/miniconda"
ENV_NAME="ml-env"
PYTHON_VERSION="3.10"
PYTORCH_VERSION="1.12.1"
TENSORFLOW_VERSION="2.10"
CUDA_TOOLKIT="11.3"

# 1️⃣ 安装 / 更新 Miniconda
if [ -d "$MINICONDA_DIR" ]; then
    echo ">>> Miniconda 已存在，执行更新 ..."
    bash "$MINICONDA_DIR/condabin/conda" update -y conda || true
else
    echo ">>> 安装 Miniconda ..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
    bash ~/miniconda.sh -b -p "$MINICONDA_DIR"
fi

# 2️⃣ 配置 PATH（当前 shell 有效）
export PATH="$MINICONDA_DIR/bin:$PATH"
eval "$($MINICONDA_DIR/bin/conda shell.bash hook)"

# 2️⃣ 永久写入 ~/.bashrc
grep -qxF 'export PATH="$HOME/miniconda/bin:$PATH"' ~/.bashrc || echo 'export PATH="$HOME/miniconda/bin:$PATH"' >> ~/.bashrc
grep -qxF 'eval "$($HOME/miniconda/bin/conda shell.bash hook)"' ~/.bashrc || echo 'eval "$($HOME/miniconda/bin/conda shell.bash hook)"' >> ~/.bashrc

# 3️⃣ 接受官方 TOS
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# 4️⃣ 配置国内镜像源
echo ">>> 配置 Conda 国内镜像源 ..."
conda config --add channels defaults
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
conda config --set show_channel_urls true

# 5️⃣ 清理缓存
conda clean -a -y

# 6️⃣ 创建 Conda 环境
echo ">>> 创建 Conda 环境: $ENV_NAME (Python $PYTHON_VERSION) ..."
conda create -y -n "$ENV_NAME" python="$PYTHON_VERSION"
conda activate "$ENV_NAME"

# 7️⃣ 安装 PyTorch + CUDA
# echo ">>> 安装 PyTorch $PYTORCH_VERSION + CUDA $CUDA_TOOLKIT ..."
# conda install -y pytorch="$PYTORCH_VERSION" torchvision torchaudio cudatoolkit="$CUDA_TOOLKIT" -c pytorch

# 8️⃣ 安装 TensorFlow + 兼容 NumPy
# echo ">>> 安装 TensorFlow $TENSORFLOW_VERSION（兼容 NumPy <2）..."
# pip install "numpy<2" --force-reinstall -i https://pypi.tuna.tsinghua.edu.cn/simple
# pip install tensorflow=="$TENSORFLOW_VERSION" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 9️⃣ 验证安装
# echo ">>> 验证安装环境 ..."
# python - <<EOF
# import torch, tensorflow as tf, numpy as np
# print("✅ NumPy:", np.__version__)
# print("✅ PyTorch:", torch.__version__, "CUDA:", torch.version.cuda, "GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only")
# print("✅ TensorFlow:", tf.__version__)
# EOF

echo ">>> 安装完成！"
echo "    直接打开新终端即可使用 conda"
echo "    激活环境: conda activate $ENV_NAME"



export CKPT=/root/workspace/models/gui-owl-7b

PIXEL_ARGS='{"min_pixels":3136,"max_pixels":5000000}'
IMAGE_LIMIT_ARGS='image=1'
MP_SIZE=1
MM_KWARGS=(
    --mm-processor-kwargs $PIXEL_ARGS
    --limit-mm-per-prompt $IMAGE_LIMIT_ARGS
)

vllm serve $CKPT \
    --max-model-len 32768 ${MM_KWARGS[@]} \
    --tensor-parallel-size $MP_SIZE \
    --allowed-local-media-path '/' \
    --port 8000 \
    --served-model-name gui-owl \
    --api-key w6x1nIS9zuDmW8GQnnMTljyoDot4KbG9
