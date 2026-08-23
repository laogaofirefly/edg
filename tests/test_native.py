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
