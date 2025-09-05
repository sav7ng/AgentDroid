#!/usr/bin/env bash
set -e

# ==================================================
# 一键安装 Docker + Docker Compose
# 适用于 Ubuntu 22.04+
# 使用阿里云 Docker 镜像 GPG key
# ==================================================

# 1️⃣ 更新系统
echo ">>> 更新系统软件包 ..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2️⃣ 安装依赖
echo ">>> 安装依赖 ..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common

# 3️⃣ 添加 Docker 官方 GPG key（阿里云镜像）
echo ">>> 添加 Docker 官方 GPG key ..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 4️⃣ 添加 Docker 仓库
echo ">>> 添加 Docker 仓库 ..."
ARCH=$(dpkg --print-architecture)
echo \
  "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5️⃣ 安装 Docker Engine
echo ">>> 安装 Docker Engine ..."
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6️⃣ 配置国内镜像源（可选）
# echo ">>> 配置 Docker 国内镜像源 ..."
# sudo mkdir -p /etc/docker
# sudo tee /etc/docker/daemon.json > /dev/null <<EOF
# {
#   "registry-mirrors": ["https://06fd2b4bc38025320fedc00a8770f200.mirror.swr.myhuaweicloud.com/"]
# }
# EOF
# sudo systemctl daemon-reload
# sudo systemctl restart docker

# 7️⃣ 添加当前用户到 docker 组（无需 sudo）
echo ">>> 添加当前用户到 docker 组 ..."
sudo usermod -aG docker $USER

# 8️⃣ 测试 Docker & Docker Compose
echo ">>> 测试 Docker 与 Docker Compose 安装 ..."
docker --version
docker compose version
docker run --rm hello-world

echo ">>> 安装完成！请注销或重启以应用 docker 用户组权限"
echo ">>> 安装完成后，你可以直接使用 docker 和 docker compose"
