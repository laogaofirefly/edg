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
import json

from edg02 import EdgError, lines_of, parse_expr


class NativeCompiler:
    def __init__(self):
        self.lines = ["#include <stdio.h>\n", "#include <stdbool.h>\n", "#include <stdlib.h>\n", "#include <string.h>\n", "\n", "static char *edg_num_to_str(double x) {\n", "    char *s = malloc(64);\n", "    if (!s) return NULL;\n", "    snprintf(s, 64, \"%g\", x);\n", "    return s;\n", "}\n"]
        self.lines += ["\n", "static char *edg_concat(const char *a, const char *b) {\n", "    size_t n = strlen(a) + strlen(b) + 1;\n", "    char *s = malloc(n);\n", "    if (!s) return NULL;\n", "    strcpy(s, a);\n", "    strcat(s, b);\n", "    return s;\n", "}\n"]
        self.lines += ["\n", "static double edg_array_get(const double *a, size_t n, int i) {\n", "    if (i < 0 || (size_t)i >= n) {\n", "        fprintf(stderr, \"EDG array index out of bounds: %d (length %zu)\\n\", i, n);\n", "        exit(1);\n", "    }\n", "    return a[i];\n", "}\n", "\n", "static void edg_array_set(double *a, size_t n, int i, double value) {\n", "    if (i < 0 || (size_t)i >= n) {\n", "        fprintf(stderr, \"EDG array index out of bounds: %d (length %zu)\\n\", i, n);\n", "        exit(1);\n", "    }\n", "    a[i] = value;\n", "}\n"]
        self.functions_code = []
        self.target = self.lines
        self.indent = 1
        self.names = set()
        self.string_names = set()
        self.array_names = set()
        self.array_lengths = {}
        self.functions = set()
        self.return_mode = False
        self.loop_depth = 0
        self.function_has_return = False
        self.function_depth = 0

    def emit(self, text):
        self.target.append("    " * self.indent + text + "\n")

    def is_string(self, node):
        if isinstance(node, list):
            return False
        if isinstance(node, str):
            return True
        if not isinstance(node, tuple):
            return False
        if node[0] == "name":
            return node[1] in self.string_names
        if node[0] == "bin" and node[1] == "+":
            return self.is_string(node[2]) or self.is_string(node[3])
        if node[0] == "call" and isinstance(node[1], tuple) and node[1][0] == "name":
            return node[1][1] == "str"
        return False

    def expr(self, node):
        if not isinstance(node, tuple):
            if node is None: return "0.0"
            if node is True: return "1.0"
            if node is False: return "0.0"
            if isinstance(node, str):
                return json.dumps(node)
            return repr(float(node))
        kind = node[0]
        if kind == "name": return node[1]
        if kind == "list":
            items = node[1]
            if not items:
                raise EdgError("line: native arrays cannot be empty")
            if any(self.is_string(x) for x in items):
                raise EdgError("native arrays currently support numeric elements only")
            return "{" + ", ".join(self.expr(x) for x in items) + "}"
        if kind == "index":
            base, index = node[1], node[2]
            if isinstance(base, tuple) and base[0] == "name" and base[1] in self.array_names:
                name = base[1]
                idx = self.expr(index)
                length = self.array_lengths[name]
                return f"edg_array_get({name}, {length}, (int)({idx}))"
            raise EdgError("native indexing is supported for numeric arrays only")
        if kind == "unary": return f"({node[1]}{self.expr(node[2])})"
        if kind == "bin":
            op = node[1]
            if op == "+" and (self.is_string(node[2]) or self.is_string(node[3])):
                return f"edg_concat({self.expr(node[2])}, {self.expr(node[3])})"
            if op in ("==", "!=") and (self.is_string(node[2]) or self.is_string(node[3])):
                cmp = "== 0" if op == "==" else "!= 0"
                return f"(strcmp({self.expr(node[2])}, {self.expr(node[3])}) {cmp})"
            left = self.expr(node[2])
            right = self.expr(node[3])
            if op == "+" and (self.is_string(node[2]) or self.is_string(node[3])):
                return f"edg_concat({left}, {right})"
            if op in ("and", "or"):
                op = "&&" if op == "and" else "||"
            return f"({left} {op} {right})"
        if kind == "call":
            fn = node[1]
            if isinstance(fn, tuple) and fn[0] == "name":
                name = fn[1]
                if name == "abs" and len(node[2]) == 1:
                    x = self.expr(node[2][0])
                    return f"(({x}) < 0 ? -({x}) : ({x}))"
                if name == "str" and len(node[2]) == 1:
                    x = self.expr(node[2][0])
                    return f"edg_num_to_str({x})"
                if name == "len" and len(node[2]) == 1 and self.is_string(node[2][0]):
                    return f"((double)strlen({self.expr(node[2][0])}))"
                if name == "len" and len(node[2]) == 1:
                    arg = node[2][0]
                    if isinstance(arg, tuple) and arg[0] == "name" and arg[1] in self.array_names:
                        return repr(float(self.array_lengths[arg[1]]))
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
        old_depth = self.function_depth
        self.function_depth += 1
        self.target = self.functions_code
        self.emit(f"double {name}({', '.join('double ' + p for p in params)}) {{")
        self.indent += 1
        old = self.return_mode; old_return = self.function_has_return
        self.return_mode = True; self.function_has_return = False
        self.block(body, 0, -1)
        self.return_mode = old; has_return = self.function_has_return; self.function_has_return = old_return
        if not has_return:
            self.emit("return 0.0;")
        self.indent -= 1; self.emit("}")
        self.target = old_target
        self.function_depth = old_depth
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
                self.emit(f"return {rhs};"); self.function_has_return = True; i += 1; continue
            if text.startswith("let ") or text.startswith("var "):
                m = re.fullmatch(r"(?:let|var)\s+([A-Za-z_]\w*)\s*=\s*(.+)", text)
                if not m: raise EdgError(f"line {line}: invalid native declaration")
                name, rhs = m.groups(); self.names.add(name)
                node = parse_expr(rhs)
                if isinstance(node, str):
                    self.string_names.add(name)
                    self.emit(f"char *{name} = {self.expr(node)};")
                elif isinstance(node, tuple) and node[0] == "list":
                    items = node[1]
                    if not items or any(self.is_string(x) for x in items):
                        raise EdgError(f"line {line}: native arrays require non-empty numeric elements")
                    self.array_names.add(name)
                    self.array_lengths[name] = len(items)
                    self.emit(f"double {name}[{len(items)}] = {self.expr(node)};")
                else:
                    self.emit(f"double {name} = {self.expr(node)};")
                i += 1; continue
            m = re.fullmatch(r"([A-Za-z_]\w*)\[([^]]+)\]\s*=\s*(.+)", text)
            if m:
                name, index, rhs = m.groups()
                if name not in self.array_names:
                    raise EdgError(f"line {line}: native indexed assignment requires an array")
                idx = self.expr(parse_expr(index))
                self.emit(f"edg_array_set({name}, {self.array_lengths[name]}, (int)({idx}), {self.expr(parse_expr(rhs))});")
                i += 1; continue
            m = re.fullmatch(r"([A-Za-z_]\w*)\s*(=|\+=|-=|\*=|/=)\s*(.+)", text)
            if m:
                name, op, rhs = m.groups(); self.names.add(name)
                self.emit(f"{name} {op} {self.expr(parse_expr(rhs))};")
                i += 1; continue
            m = re.fullmatch(r"print\((.*)\)", text)
            if m:
                node = parse_expr(m.group(1).strip())
                value = self.expr(node)
                if self.is_string(node):
                    self.emit(f"printf(\"%s\\n\", {value});")
                else:
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
                try:
                    if float(step) == 0:
                        raise EdgError(f"line {line}: range step cannot be zero")
                except ValueError:
                    pass
                start_c = self.expr(parse_expr(start))
                stop_c = self.expr(parse_expr(stop))
                step_c = self.expr(parse_expr(step))
                self.emit(f"for (double {var} = {start_c}; ({step_c}) > 0 ? {var} < {stop_c} : {var} > {stop_c}; {var} += {step_c}) {{")
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


def compile_source(source):
    return NativeCompiler().compile(source)


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
