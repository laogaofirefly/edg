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
assert run_native("""let values = [1, 2]
print(len(values))
""") == "2\n"
assert run_native("""let values = [1, 2]
print(values[0])
""") == "1\n"
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
assert run_native("""let values = []
for i in range(20)
    push(values, i)
let last = pop(values)
print(last)
print(len(values))
clear(values)
compact(values)
print(len(values))
for i in range(5)
    push(values, [i, i + 1])
print(len(values))
clear(values)
compact(values)
print(len(values))
""") == "19\n19\n0\n5\n0\n"
assert run_native("""let empty = []
let words = [\"a\", \"b\", 3, true, nothing]
print(join(words, \",\"))
print(join(empty, \"|\"))
print(contains(words, \"b\"))
print(contains(words, \"z\"))
print(contains(words, 3))
print(contains(words, true))
print(contains(words, nothing))
print(contains(empty, 1))
""") == "a,b,3,true,nothing\n\ntrue\nfalse\ntrue\ntrue\ntrue\nfalse\n"
assert run_native("""let values = [\"a\", 2, true, nothing]
let joined = join(values, \"|\")
print(joined)
let empty_joined = join([], \",\")
print(empty_joined)
""") == "a|2|true|nothing\n\n"
assert run_native("""let left = \"hello\"
let right = \" world\"
let combined = left + right
print(combined)
let chained = (left + right) + \"!\"
print(chained)
let empty = \"\"
print(empty + left)
fn make(a, b)
    return a + b
let result = make(left, right)
print(result)
""") == "hello world\nhello world!\nhello\nhello world\n"
assert run_native("""let a = \"left\"
let b = \"right\"
let x = a and b
print(x)
let y = \"\" and b
print(y)
let z = a or b
print(z)
let q = \"\" or b
print(q)
let n = nothing or b
print(n)
let e = nothing and b
print(e)
""") == "right\n\nleft\nright\nright\nnothing\n"
print("PASS: native backend")
