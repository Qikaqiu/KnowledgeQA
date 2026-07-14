#!/usr/bin/env bash
# Oracle Cloud Ubuntu 实例一键部署 KnowledgeQA（demo 分支）
# 用法：curl -fsSL ... | bash   或   bash deploy/oracle-setup.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Qikaqiu/KnowledgeQA.git}"
APP_DIR="${APP_DIR:-$HOME/KnowledgeQA}"
BRANCH="${BRANCH:-demo}"

echo "==> 安装 Docker..."
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl git
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

echo "==> 拉取代码 ($BRANCH)..."
if [ -d "$APP_DIR/.git" ]; then
  cd "$APP_DIR"
  git fetch origin
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
else
  git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "请编辑 $APP_DIR/.env ，至少填入 DEMO_API_KEY"
  echo "  nano $APP_DIR/.env"
  echo ""
fi

mkdir -p data

echo "==> 构建并启动容器..."
sudo docker compose build
sudo docker compose up -d

echo ""
echo "部署完成。本机访问: http://127.0.0.1:8000"
echo "健康检查: curl http://127.0.0.1:8000/api/health"
echo ""
echo "下一步："
echo "  1. 在 Oracle 安全列表开放 80/443 端口"
echo "  2. 配置域名 DNS 指向本机公网 IP"
echo "  3. 安装 Nginx + Certbot（见 README Oracle 部署章节）"
