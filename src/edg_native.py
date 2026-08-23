#!/usr/bin/env python3
"""EDG native AOT prototype.

This backend deliberately supports a small numeric subset and emits C, which is
then compiled by the platform C compiler into a native executable.
"""
import os
import re
import shutil
import subprocess
import tempfile

from edg02 import EdgError, lines_of, parse_expr


class NativeCompiler:
    def __init__(self):
        self.lines = ["#include <stdio.h>\n", "#include <stdbool.h>\n", "int main(void) {\n"]
        self.indent = 1
        self.names = set()

    def emit(self, text):
        self.lines.append("    " * self.indent + text + "\n")

    def expr(self, node):
        if not isinstance(node, tuple):
            if node is None: return "0.0"
            if node is True: return "1.0"
            if node is False: return "0.0"
            if isinstance(node, str):
                raise EdgError("native backend only supports numeric expressions")
            return repr(float(node))
        kind = node[0]
        if kind == "name": return node[1]
        if kind == "unary": return f"({node[1]}{self.expr(node[2])})"
        if kind == "bin":
            op = node[1]
            if op in ("and", "or"):
                op = "&&" if op == "and" else "||"
            return f"({self.expr(node[2])} {op} {self.expr(node[3])})"
        if kind == "call":
            fn = node[1]
            if isinstance(fn, tuple) and fn[0] == "name":
                name = fn[1]
                if name == "abs" and len(node[2]) == 1:
                    return f"(({self.expr(node[2][0])}) < 0 ? -({self.expr(node[2][0])}) : ({self.expr(node[2][0])}))"
            raise EdgError("native backend does not support this function call")
        raise EdgError("native backend supports only numeric expressions")

    def block(self, rows, start=0, parent=-1):
        i = start
        while i < len(rows):
            level, text, line = rows[i]
            if level <= parent: break
            # EDG 使用实际空格宽度表示缩进；子块只需比父块更深。
            if text.startswith("let ") or text.startswith("var "):
                m = re.fullmatch(r"(?:let|var)\s+([A-Za-z_]\w*)\s*=\s*(.+)", text)
                if not m: raise EdgError(f"line {line}: invalid native declaration")
                name, rhs = m.groups(); self.names.add(name)
                self.emit(f"double {name} = {self.expr(parse_expr(rhs))};")
                i += 1; continue
            m = re.fullmatch(r"([A-Za-z_]\w*)\s*(=|\+=|-=|\*=|/=)\s*(.+)", text)
            if m:
                name, op, rhs = m.groups(); self.names.add(name)
                self.emit(f"{name} {op} {self.expr(parse_expr(rhs))};")
                i += 1; continue
            m = re.fullmatch(r"print\((.*)\)", text)
            if m:
                args = [x.strip() for x in m.group(1).split(",") if x.strip()]
                if len(args) != 1: raise EdgError(f"line {line}: native print accepts one argument")
                self.emit(f"printf(\"%g\\n\", {self.expr(parse_expr(args[0]))});")
                i += 1; continue
            if text.startswith("if "):
                condition = text[3:].strip()
                self.emit(f"if ({self.expr(parse_expr(condition))}) {{")
                self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1; self.emit("}")
                while i < len(rows) and rows[i][0] == level and (rows[i][1].startswith("elif ") or rows[i][1] == "else"):
                    branch = rows[i][1]
                    if branch == "else":
                        self.emit("else {")
                    else:
                        self.emit(f"else if ({self.expr(parse_expr(branch[5:].strip()))}) {{")
                    self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1; self.emit("}")
                continue
            if text.startswith("while "):
                condition = text[6:].strip()
                self.emit(f"while ({self.expr(parse_expr(condition))}) {{")
                self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1; self.emit("}")
                continue
            if text == "pass": self.emit(";"); i += 1; continue
            if text.startswith("fn ") or text.startswith("for "):
                raise EdgError(f"line {line}: construct is not supported by native backend yet")
            raise EdgError(f"line {line}: unsupported native statement '{text}'")
        return i

    def compile(self, source):
        rows = lines_of(source)
        self.block(rows, 0, -1)
        self.lines.append("    return 0;\n}\n")
        return "".join(self.lines)


def compile_file(source_path, output):
    with open(source_path, encoding="utf8") as f:
        c_source = NativeCompiler().compile(f.read())
    cc = shutil.which(os.environ.get("CC", "cc")) or shutil.which("gcc") or shutil.which("clang")
    if not cc: raise EdgError("native compiler not found (install cc, gcc, or clang)")
    with tempfile.TemporaryDirectory(prefix="edg-native-") as tmp:
        c_path = os.path.join(tmp, "program.c")
        with open(c_path, "w", encoding="utf8") as f: f.write(c_source)
        result = subprocess.run([cc, "-O2", c_path, "-o", output], text=True, capture_output=True)
        if result.returncode:
            raise EdgError("C compiler failed: " + (result.stderr.strip() or result.stdout.strip()))
    return output
