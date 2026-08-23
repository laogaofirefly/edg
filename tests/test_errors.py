#!/usr/bin/env python3
"""EDG 错误诊断回归测试。"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "edg.py")


def run_source(source, command="run"):
    with tempfile.NamedTemporaryFile("w", suffix=".edg", encoding="utf8", delete=False) as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, CLI, command, path],
            cwd=ROOT, text=True, capture_output=True,
        )
    finally:
        os.unlink(path)


def check(name, source, fragments, command="run"):
    result = run_source(source, command)
    output = result.stdout + result.stderr
    missing = [x for x in fragments if x not in output]
    if result.returncode == 0 or missing:
        print(f"FAIL: {name}\n{output}", file=sys.stderr)
        return False
    print(f"PASS: {name}")
    return True


def main():
    cases = [
        ("undefined name", "let x = missing_name\n", ["name 'missing_name' is not defined", "^"]),
        ("break outside loop", "break\n", ["break outside loop", ":1:"]),
        ("invalid function", "fn broken(\n", ["invalid function declaration", ":1:"]),
        ("index error", "let x = [1]\nprint(x[3])\n", ["list index out of range", "^"]),
    ]
    return 0 if all(check(*case) for case in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
