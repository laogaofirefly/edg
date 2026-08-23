#!/usr/bin/env python3
"""EDG Native-first command-line launcher."""
import os
import subprocess
import sys
import tempfile
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
os.chdir(ROOT)
from edg02 import EdgError
from edg_native import compile_file, compile_source

def diagnostic(path, exc):
    import re
    message = str(exc)
    match = re.search(r"line (\d+)", message)
    line = int(match.group(1)) if match else 1
    try:
        source_line = open(path, encoding="utf8").read().splitlines()[line - 1]
    except (OSError, IndexError):
        source_line = ""
    print(f"{path}:{line}:1: {message}", file=sys.stderr)
    if source_line:
        print(f"    {source_line}\n    ^", file=sys.stderr)

def native_run(path):
    with tempfile.TemporaryDirectory(prefix="edg-native-run-") as tmp:
        output = os.path.join(tmp, "program")
        compile_file(path, output)
        return subprocess.run([output], cwd=ROOT).returncode

def native_check(path):
    with tempfile.TemporaryDirectory(prefix="edg-native-check-") as tmp:
        compile_file(path, os.path.join(tmp, "program"))
    print(f"OK: native check {path}")
    return 0

def main():
    args = sys.argv[1:]
    if len(args) == 1 and args[0] == "test":
        return subprocess.run([sys.executable, os.path.join(ROOT, "tests", "test_native.py")], cwd=ROOT).returncode
    if len(args) >= 2 and args[0] == "native":
        command, filename = "native", args[1]
        output = args[3] if len(args) == 4 and args[2] == "-o" else os.path.splitext(filename)[0]
    elif len(args) == 3 and args[0] == "emit-c":
        filename, output = args[1], args[2]
        path = os.path.abspath(filename)
        try:
            with open(path, encoding="utf8") as source, open(output, "w", encoding="utf8") as target:
                target.write(compile_source(source.read()))
            print(f"OK: C source {output}")
            return 0
        except (EdgError, OSError, ValueError) as exc:
            diagnostic(path, exc)
            return 1
    elif len(args) == 2 and args[0] in ("run", "check"):
        command, filename = args
    elif len(args) == 1 and args[0] not in ("-h", "--help"):
        command, filename = "run", args[0]
    else:
        print("用法: python3 edg.py run <file.edg>")
        print("检查: python3 edg.py check <file.edg>")
        print("原生编译: python3 edg.py native <file.edg> [-o output]")
        print("生成C代码: python3 edg.py emit-c <file.edg> <output.c>")
        print("测试: python3 edg.py test")
        return 0 if args in (["-h"], ["--help"]) else 2
    path = os.path.abspath(filename)
    if not os.path.isfile(path):
        print(f"EDG error: file not found: {filename}", file=sys.stderr)
        return 1
    try:
        if command == "check":
            return native_check(path)
        if command == "native":
            compile_file(path, os.path.abspath(output))
            print(f"OK: native executable {output}")
            return 0
        return native_run(path)
    except (EdgError, OSError, ValueError) as exc:
        diagnostic(path, exc)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())