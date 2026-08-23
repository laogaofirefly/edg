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


def diagnostic(path, exc, line=None):
    """将异常转换为统一的文件、行号和源码指针诊断。"""
    message = str(exc)
    import re
    if line is None:
        match = re.search(r'line (\d+)', message)
        line = int(match.group(1)) if match else 1
    try:
        with open(path, encoding="utf8") as source:
            source_line = source.read().splitlines()[line - 1]
    except (OSError, IndexError):
        source_line = ""
    print(f"{path}:{line}:1: {message}", file=sys.stderr)
    if source_line:
        print(f"    {source_line}", file=sys.stderr)
        print("    ^", file=sys.stderr)


def dump(path):
    """编译并打印字节码，便于调试语言实现。"""
    try:
        with open(path, encoding="utf8") as f:
            chunk = Compiler().compile_lines(lines_of(f.read()))
        print(chunk.disassemble(path))
        return 0
    except (EdgError, OSError, TypeError, ValueError) as exc:
        diagnostic(path, exc)
        return 1


def check(path):
    """只解析和编译，不执行程序。"""
    try:
        with open(path, encoding="utf8") as f:
            Compiler().compile_lines(lines_of(f.read()))
        print(f"OK: {path}")
        return 0
    except (EdgError, OSError, TypeError, ValueError) as exc:
        diagnostic(path, exc)
        return 1


def main():
    args = sys.argv[1:]
    if args in (["--repl"], ["-i"]):
        from edg_repl import main as repl_main
        return repl_main()
    if len(args) == 1 and args[0] == "test":
        import subprocess
        test_dir = os.path.join(ROOT, "tests")
        scripts = ["test_runner.py", "test_errors.py", "test_bytecode_lines.py", "test_native.py"]
        status = 0
        for script in scripts:
            result = subprocess.run([sys.executable, os.path.join(test_dir, script)], cwd=ROOT)
            status = status or result.returncode
        return status
    if len(args) >= 2 and args[0] == "native":
        from edg_native import compile_file
        filename = args[1]
        output = args[3] if len(args) == 4 and args[2] == "-o" else os.path.splitext(filename)[0]
        path = os.path.abspath(filename)
        try:
            compile_file(path, os.path.abspath(output))
            print(f"OK: native executable {output}")
            return 0
        except (EdgError, OSError, ValueError) as exc:
            diagnostic(path, exc)
            return 1
    if len(args) == 3 and args[0] == "emit-c":
        from edg_native import compile_source
        path, output = os.path.abspath(args[1]), os.path.abspath(args[2])
        try:
            with open(path, encoding="utf8") as f:
                c_source = compile_source(f.read())
            with open(output, "w", encoding="utf8") as f:
                f.write(c_source)
            print(f"OK: C source {args[2]}")
            return 0
        except (EdgError, OSError, ValueError) as exc:
            diagnostic(path, exc)
            return 1
    if len(args) == 2 and args[0] in ("run", "check", "dump"):
        command, filename = args
    elif len(args) == 1 and args[0] not in ("-h", "--help"):
        # 保留旧用法：edg.py file.edg 等价于 edg.py run file.edg
        command, filename = "run", args[0]
    else:
        print("用法: python3 edg.py run <file.edg>")
        print("检查: python3 edg.py check <file.edg>")
        print("字节码: python3 edg.py dump <file.edg>")
        print("原生编译: python3 edg.py native <file.edg> [-o output]")
        print("生成C代码: python3 edg.py emit-c <file.edg> <output.c>")
        print("测试: python3 edg.py test")
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
