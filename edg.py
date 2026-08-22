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
    if len(sys.argv) != 2:
        print("用法: python3 edg.py <file.edg>")
        print("示例: python3 edg.py examples/world_demo.edg")
        return 2
    return run(os.path.abspath(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
