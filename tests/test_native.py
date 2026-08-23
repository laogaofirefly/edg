#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDG = os.path.join(ROOT, "edg.py")


def run_native(source):
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "test.edg")
        out = os.path.join(tmp, "test.out")
        with open(src, "w", encoding="utf8") as f:
            f.write(source)
        result = subprocess.run([sys.executable, EDG, "native", src, "-o", out], cwd=ROOT, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        result = subprocess.run([out], text=True, capture_output=True)
        assert result.returncode == 0
        return result.stdout


assert run_native("""let greeting = "hello EDG"
let suffix = " native"
print(greeting + suffix)
print("native string")
""") == "hello EDG native\nnative string\n"
assert run_native("""let name = "EDG"
if name == "EDG"
    print(len(name))
if name != "VM"
    print("matched")
""") == "3\nmatched\n"
assert run_native("""let values = [10, 20, 30]
print(values[1])
values[2] = 42
print(values[2])
""") == "20\n42\n"
assert run_native("""let total = 0
for i in range(5, 0, -2)
    total += i
print(total)
""") == "9\n"
assert run_native("""fn add(a, b)
    return a + b
print(add(20, 22))
""") == "42\n"
assert run_native("""let total = 0
for i in range(5)
    if i == 2
        continue
    if i == 4
        break
    total += i
print(total)
""") == "4\n"
print("PASS: native backend")
