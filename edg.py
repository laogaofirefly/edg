#!/usr/bin/env python3
"""EDG 简易启动器：无需手动设置 PYTHONPATH。"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
os.chdir(ROOT)

from edg03 import run

def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("--repl", "-i"):
        from edg_repl import main as repl_main
        return repl_main()
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print("用法: python3 edg.py <file.edg>")
        print("交互模式: python3 edg.py --repl")
        print("示例: python3 edg.py examples/world_demo.edg")
        print("Termux 首次安装: pkg update && pkg install python")
        return 0 if len(sys.argv) == 2 else 2
    path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(path):
        print(f"EDG error: file not found: {sys.argv[1]}", file=sys.stderr)
        return 1
    return run(path)



if __name__ == "__main__":
    raise SystemExit(main())
