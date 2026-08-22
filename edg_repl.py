#!/usr/bin/env python3
"""EDG 交互式 REPL。空行提交当前代码块，输入 :help 查看帮助。"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
os.chdir(ROOT)

from edg02 import EdgError, lines_of
from edg03 import Compiler, Env, VM, edg_hot


def make_env():
    env = Env()
    env["print"] = lambda *x: print(*x)
    env["len"] = len
    env["range"] = lambda *x: list(range(*x))
    env["type"] = lambda x: (
        "nothing" if x is None else
        "number" if isinstance(x, (int, float)) else
        "text" if isinstance(x, str) else
        "list" if isinstance(x, list) else "object"
    )
    if edg_hot is not None:
        env["hot"] = edg_hot
    return env


def execute(source, env):
    compiler = Compiler()
    chunk = compiler.compile_lines(lines_of(source))
    return VM({}).run(chunk, env)


def main():
    print("EDG REPL 0.9 | 输入 :help 查看帮助，:quit 退出")
    env = make_env()
    buffer = []
    prompt = "edg> "
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        command = line.strip()
        if not buffer and command in (":quit", ":q", ":exit"):
            return 0
        if not buffer and command == ":help":
            print("输入 EDG 表达式或语句；空行执行代码块。")
            print("示例：let x = 2，然后输入 print(x + 3)")
            print(":quit / :q    退出 REPL")
            continue
        if not buffer and command == ":clear":
            env = make_env()
            print("环境已清空")
            continue
        if not line.strip():
            if not buffer:
                continue
            try:
                result = execute("\n".join(buffer), env)
                if result is not None:
                    print(result)
            except (EdgError, TypeError, KeyError, IndexError, ValueError) as exc:
                print(f"EDG error: {exc}", file=sys.stderr)
            buffer = []
            prompt = "edg> "
            continue
        buffer.append(line)
        prompt = "...   "


if __name__ == "__main__":
    raise SystemExit(main())
