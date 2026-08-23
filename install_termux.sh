#!/data/data/com.termux/files/usr/bin/bash
# EDG Termux 安装辅助脚本
set -e

if ! command -v pkg >/dev/null 2>&1; then
    echo "错误：当前环境不是 Termux，无法使用 pkg。"
    echo "请先安装 Python 3，再运行：python3 edg.py examples/hello.edg"
    exit 1
fi

echo "[1/3] 更新 Termux 软件源..."
pkg update -y

echo "[2/3] 安装 Python..."
pkg install -y python

echo "[3/3] 请求 Android 存储权限..."
if command -v termux-setup-storage >/dev/null 2>&1; then
    termux-setup-storage || true
fi

echo
echo "安装完成："
python3 --version
echo
echo "运行示例："
echo "  python3 edg.py examples/hello.edg"
echo "  ./run_edg.sh examples/hello.edg"
