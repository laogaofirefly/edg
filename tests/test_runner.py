#!/usr/bin/env python3
"""EDG 最小端到端回归测试。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "edg.py")


def run(*args):
    return subprocess.run([sys.executable, CLI, *args], cwd=ROOT, text=True, capture_output=True)


def main():
    cases = [
        (["check", "examples/hello.edg"], 0, "OK:"),
        (["run", "examples/hello.edg"], 0, "EDG\n30"),
        (["run", "examples/method_demo.edg"], 0, "HELLO,EDG"),
        (["run", "examples/import_demo.edg"], 0, "42"),
    ]
    for args, expected_code, expected_text in cases:
        result = run(*args)
        output = result.stdout + result.stderr
        if result.returncode != expected_code or expected_text not in output:
            print(f"FAIL: {' '.join(args)}\n{output}", file=sys.stderr)
            return 1
        print(f"PASS: {' '.join(args)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
