#!/usr/bin/env python3
"""EDG 简易启动器：无需手动设置 PYTHONPATH。"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
os.chdir(ROOT)

from edg02 import EdgError, lines_of
from edg03 import Compiler, run


def dump(path):
    """编译并打印字节码，便于调试语言实现。"""
    try:
        with open(path, encoding="utf8") as f:
            chunk = Compiler().compile_lines(lines_of(f.read()))
        print(chunk.disassemble(path))
        return 0
    except (EdgError, OSError, TypeError, ValueError) as exc:
        print(f"EDG dump error: {exc}", file=sys.stderr)
        return 1


def check(path):
    """只解析和编译，不执行程序。"""
    try:
        with open(path, encoding="utf8") as f:
            Compiler().compile_lines(lines_of(f.read()))
        print(f"OK: {path}")
        return 0
    except (EdgError, OSError, TypeError, ValueError) as exc:
        print(f"EDG check error: {exc}", file=sys.stderr)
        return 1


def main():
    args = sys.argv[1:]
    if args in (["--repl"], ["-i"]):
        from edg_repl import main as repl_main
        return repl_main()
    if len(args) == 2 and args[0] in ("run", "check", "dump"):
        command, filename = args
    elif len(args) == 1 and args[0] not in ("-h", "--help"):
        # 保留旧用法：edg.py file.edg 等价于 edg.py run file.edg
        command, filename = "run", args[0]
    else:
        print("用法: python3 edg.py run <file.edg>")
        print("检查: python3 edg.py check <file.edg>")
        print("字节码: python3 edg.py dump <file.edg>")
        print("交互模式: python3 edg.py --repl")
        print("旧用法: python3 edg.py <file.edg>")
        return 0 if args in (["-h"], ["--help"]) else 2
    path = os.path.abspath(filename)
    if not os.path.isfile(path):
        print(f"EDG error: file not found: {filename}", file=sys.stderr)
        return 1
    if command == "check":
        return check(path)
    if command == "dump":
        return dump(path)
    return run(path)



if __name__ == "__main__":
    raise SystemExit(main())
