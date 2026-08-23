#!/data/data/com.termux/files/usr/bin/bash
# EDG Termux 运行脚本
set -e

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "未检测到 Python 3。请先执行："
    echo "  pkg update && pkg install python"
    exit 127
fi

if [ "$#" -ne 1 ]; then
    echo "用法：./run_edg.sh <file.edg>"
    echo "示例：./run_edg.sh examples/hello.edg"
    exit 2
fi

cd "$ROOT"
exec python3 edg.py "$1"