#!/usr/bin/env python3
"""验证字节码拼接后仍保留源码行号。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from edg02 import lines_of
from edg03 import Compiler


def main():
    source = "if true:\n    let x = 1\n    let y = x + 2\n"
    chunk = Compiler().compile_lines(lines_of(source))
    if len(chunk.code) != len(chunk.lines):
        print("FAIL: bytecode/source line length mismatch")
        return 1
    if not all(line > 0 for line in chunk.lines):
        print("FAIL: bytecode contains missing source line")
        return 1
    print("PASS: bytecode source lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
