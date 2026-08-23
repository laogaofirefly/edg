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
        self.lines = ["#include <stdio.h>\n", "#include <stdbool.h>\n"]
        self.functions_code = []
        self.target = self.lines
        self.indent = 1
        self.names = set()
        self.functions = set()
        self.return_mode = False
        self.loop_depth = 0

    def emit(self, text):
        self.target.append("    " * self.indent + text + "\n")

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
                    x = self.expr(node[2][0])
                    return f"(({x}) < 0 ? -({x}) : ({x}))"
                if name in self.functions:
                    return f"{name}({', '.join(self.expr(a) for a in node[2])})"
            raise EdgError("native backend does not support this function call")
        raise EdgError("native backend supports only numeric expressions")

    def function(self, rows, index, level):
        text = rows[index][1]
        m = re.fullmatch(r"fn\s+([A-Za-z_]\w*)\s*\((.*?)\)", text)
        if not m:
            raise EdgError(f"line {rows[index][2]}: invalid native function declaration")
        name, raw_params = m.groups()
        params = [x.strip() for x in raw_params.split(',') if x.strip()]
        if any(not re.fullmatch(r"[A-Za-z_]\w*", p) for p in params):
            raise EdgError(f"line {rows[index][2]}: invalid native function parameter")
        self.functions.add(name)
        body, end = self._nested(rows, index + 1, level)
        old_target = self.target
        self.target = self.functions_code
        self.emit(f"double {name}({', '.join('double ' + p for p in params)}) {{")
        self.indent += 1
        old = self.return_mode; self.return_mode = True
        self.block(body, 0, -1)
        self.return_mode = old
        self.emit("return 0.0;")
        self.indent -= 1; self.emit("}")
        self.target = old_target
        return end

    def _nested(self, rows, start, parent):
        if start >= len(rows) or rows[start][0] <= parent:
            raise EdgError(f"line {rows[start - 1][2]}: expected indented block")
        i = start
        while i < len(rows) and rows[i][0] > parent: i += 1
        return rows[start:i], i

    def block(self, rows, start=0, parent=-1):
        i = start
        while i < len(rows):
            level, text, line = rows[i]
            if level <= parent: break
            # EDG 使用实际空格宽度表示缩进；子块只需比父块更深。
            if text.startswith("fn ") and not self.return_mode:
                i = self.function(rows, i, level); continue
            if text == "return" or text.startswith("return "):
                if not self.return_mode:
                    raise EdgError(f"line {line}: return outside function")
                rhs = "0.0" if text == "return" else self.expr(parse_expr(text[7:]))
                self.emit(f"return {rhs};"); i += 1; continue
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
                value = self.expr(parse_expr(m.group(1).strip()))
                self.emit(f"printf(\"%g\\n\", {value});")
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
                self.loop_depth += 1
                self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1
                self.loop_depth -= 1; self.emit("}")
                continue
            if text.startswith("for "):
                m = re.fullmatch(r"for\s+([A-Za-z_]\w*)\s+in\s+range\((.*?)\)", text)
                if not m:
                    raise EdgError(f"line {line}: native for currently requires range()")
                var, raw = m.groups()
                parts = [p.strip() for p in raw.split(",") if p.strip()]
                if len(parts) == 1:
                    start, stop, step = "0", parts[0], "1"
                elif len(parts) == 2:
                    start, stop, step = parts[0], parts[1], "1"
                elif len(parts) == 3:
                    start, stop, step = parts
                else:
                    raise EdgError(f"line {line}: range expects 1 to 3 arguments")
                self.emit(f"for (double {var} = {self.expr(parse_expr(start))}; {var} < {self.expr(parse_expr(stop))}; {var} += {self.expr(parse_expr(step))}) {{")
                self.loop_depth += 1
                self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1
                self.loop_depth -= 1; self.emit("}")
                continue
            if text == "break" or text == "continue":
                if self.loop_depth == 0:
                    raise EdgError(f"line {line}: {text} outside loop")
                self.emit(text + ";"); i += 1; continue
            if text == "pass": self.emit(";"); i += 1; continue
            if text.startswith("fn "): 
                raise EdgError(f"line {line}: construct is not supported by native backend yet")
            raise EdgError(f"line {line}: unsupported native statement '{text}'")
        return i

    def compile(self, source):
        rows = lines_of(source)
        # 预扫描函数名，允许函数在调用点之前或之后声明。
        for level, text, line in rows:
            m = re.fullmatch(r"fn\s+([A-Za-z_]\w*)\s*\(.*?\)", text)
            if m: self.functions.add(m.group(1))
        self.lines.append("\n".join(self.functions_code)) if self.functions_code else None
        self.lines.append("int main(void) {\n")
        self.target = self.lines
        self.block(rows, 0, -1)
        self.lines.append("    return 0;\n}\n")
        # 函数体是在主函数编译过程中收集的，插入到 main 之前。
        if self.functions_code:
            self.lines[2:2] = self.functions_code
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
