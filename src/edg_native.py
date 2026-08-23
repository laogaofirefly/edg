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
from edg_native_runtime import RUNTIME_C



class NativeCompiler:
    def __init__(self):
        # Keep the old generated helpers isolated while the public C Runtime
        # is introduced.  This prevents duplicate EdgValue/EDG_* symbols and
        # lets generated programs link the shared ABI incrementally.
        self.lines = ["#include \"__EDG_VALUE_HEADER__\"\n" + RUNTIME_C + "\n"]
        self.lines += ["\n", "static char *edg_concat(const char *a, const char *b) {\n", "    size_t n = strlen(a) + strlen(b) + 1;\n", "    char *s = malloc(n);\n", "    if (!s) return NULL;\n", "    strcpy(s, a);\n", "    strcat(s, b);\n", "    return s;\n", "}\n"]
        self.lines += ["\n", "static double edg_array_get(const double *a, size_t n, int i) {\n", "    if (i < 0 || (size_t)i >= n) {\n", "        fprintf(stderr, \"EDG array index out of bounds: %d (length %zu)\\n\", i, n);\n", "        exit(1);\n", "    }\n", "    return a[i];\n", "}\n", "\n", "static void edg_array_set(double *a, size_t n, int i, double value) {\n", "    if (i < 0 || (size_t)i >= n) {\n", "        fprintf(stderr, \"EDG array index out of bounds: %d (length %zu)\\n\", i, n);\n", "        exit(1);\n", "    }\n", "    a[i] = value;\n", "}\n"]
        self.functions_code = []
        self.target = self.lines
        self.indent = 1
        self.names = set()
        self.value_names = set()
        self.string_names = set()
        self.array_names = set()
        self.array_lengths = {}
        self.functions = set()
        self.return_mode = False
        self.loop_depth = 0
        self.function_has_return = False
        self.function_depth = 0
        self.temp_counter = 0
        self.function_locals = []
    def new_temp(self, prefix):
        self.temp_counter += 1
        return f"__edg_{prefix}_{self.temp_counter}"
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

    def value_expr(self, node):
        """Emit an EdgValue expression, including value-preserving logic ops."""
        if isinstance(node, tuple) and node[0] == "bin":
            op, left, right = node[1], node[2], node[3]
            if op == "+":
                return f"edg_add({self.value_expr(left)}, {self.value_expr(right)})"
            if op == "-":
                return f"edg_sub({self.value_expr(left)}, {self.value_expr(right)})"
            if op == "*":
                return f"edg_mul({self.value_expr(left)}, {self.value_expr(right)})"
            if op == "/":
                return f"edg_div({self.value_expr(left)}, {self.value_expr(right)})"
            if op in ("==", "!="): 
                eq = f"edg_equal({self.value_expr(left)}, {self.value_expr(right)})"
                return f"edg_bool({eq if op == '==' else '!(' + eq + ')'})"
            if op == "and":
                # Logical operators return values. Clone the selected branch
                # so assigning the result never aliases an owned variable.
                return f"(edg_truthy({self.value_expr(left)}) ? edg_clone_value({self.value_expr(right)}) : edg_clone_value({self.value_expr(left)}))"
            if op == "or":
                return f"(edg_truthy({self.value_expr(left)}) ? edg_clone_value({self.value_expr(left)}) : edg_clone_value({self.value_expr(right)}))"
        if isinstance(node, tuple) and node[0] == "name" and node[1] in self.value_names:
            return node[1]
        if isinstance(node, tuple) and node[0] == "list":
            items = node[1]
            temp = f"edg_array_new({len(items)})"
            # Array literals in return/value contexts are emitted as a compound helper.
            # Use a generated temporary to preserve each element's EdgValue type.
            tmp = self.new_temp("array")
            self.emit(f"EdgValue {tmp} = {temp};")
            for array_index, item in enumerate(items):
                self.emit(f"edg_array_value_set({tmp}, {array_index}, {self.value_expr(item)});")
            return tmp
        if isinstance(node, tuple) and node[0] == "index":
            base, index = node[1], node[2]
            if isinstance(base, tuple) and base[0] == "name" and (base[1] in self.array_names or base[1] in self.value_names):
                return f"edg_array_value_get({base[1]}, (int)({self.expr(index)}))"
            if isinstance(base, tuple) and base[0] == "index":
                return f"edg_array_value_get({self.value_expr(base)}, (int)({self.expr(index)}))"
        if isinstance(node, tuple) and node[0] == "call" and isinstance(node[1], tuple) and node[1][0] == "name":
            name = node[1][1]
            args = ', '.join(self.value_expr(a) for a in node[2])
            if name == "pop" and len(node[2]) == 1:
                return f"edg_array_pop({args})"
            if name == "contains" and len(node[2]) == 2:
                return f"edg_bool(edg_array_contains({self.value_expr(node[2][0])}, {self.value_expr(node[2][1])}))"
            if name == "clear" and len(node[2]) == 1:
                return f"(edg_array_clear({self.value_expr(node[2][0])}), edg_nothing())"
            if name == "join" and len(node[2]) == 2:
                return f"edg_array_join({self.value_expr(node[2][0])}, {self.value_expr(node[2][1])})"
            if name == "compact" and len(node[2]) == 1:
                return f"(edg_array_compact({self.value_expr(node[2][0])}), edg_nothing())"
            if name in self.functions:
                return f"{name}({args})"
        value = self.expr(node)
        if node is None:
            return "edg_nothing()"
        if node is True or node is False:
            return f"edg_bool({value})"
        if self.is_string(node):
            return f"edg_string({value})"
        return f"edg_number({value})"

    def truth_expr(self, node):
        return f"edg_truthy({self.value_expr(node)})"

    def expr(self, node):
        if not isinstance(node, tuple):
            if node is None: return "0.0"
            if node is True: return "1.0"
            if node is False: return "0.0"
            if isinstance(node, str):
                return json.dumps(node)
            return repr(float(node))
        kind = node[0]
        if kind == "name":
            if node[1] in self.value_names:
                return f"({node[1]}).as.number"
            return node[1]
        if kind == "list":
            raise EdgError("native array literals are only supported in value contexts")
        if kind == "index":
            raise EdgError("native indexing is only supported in value contexts")
        if kind == "unary": return f"({node[1]}{self.expr(node[2])})"
        if kind == "bin":
            op = node[1]
            if op == "+":
                left_v = self.value_expr(node[2])
                right_v = self.value_expr(node[3])
                result = f"edg_add({left_v}, {right_v})"
                if self.is_string(node[2]) or self.is_string(node[3]):
                    return f"({result}).as.string"
                return f"({result}).as.number"
            if op in ("-", "*", "/"):
                fn = {"-": "edg_sub", "*": "edg_mul", "/": "edg_div"}[op]
                return f"({fn}({self.value_expr(node[2])}, {self.value_expr(node[3])})).as.number"
            if op in ("==", "!="):
                comparison = f"edg_equal({self.value_expr(node[2])}, {self.value_expr(node[3])})"
                return comparison if op == "==" else f"(!({comparison}))"
            left = self.expr(node[2])
            right = self.expr(node[3])
            if op in ("and", "or"):
                # Preserve short-circuiting while applying EDG truthiness.
                right_truth = self.truth_expr(node[3])
                if op == "and":
                    return f"(edg_truthy({self.value_expr(node[2])}) && ({right_truth}))"
                return f"(edg_truthy({self.value_expr(node[2])}) || ({right_truth}))"
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
                if name == "push" and len(node[2]) == 2:
                    self.emit(f"edg_array_push({self.value_expr(node[2][0])}, {self.value_expr(node[2][1])});")
                    return "0.0"
                if name == "pop" and len(node[2]) == 1:
                    return "edg_array_pop(%s).as.number" % self.value_expr(node[2][0])
                if name == "len" and len(node[2]) == 1 and self.is_string(node[2][0]):
                    arg = node[2][0]
                    if isinstance(arg, tuple) and arg[0] == "name" and arg[1] in self.value_names:
                        return f"((double)strlen(({arg[1]}).as.string))"
                    return f"((double)strlen({self.expr(arg)}))"
                if name == "len" and len(node[2]) == 1:
                    arg = node[2][0]
                    if isinstance(arg, tuple) and arg[0] == "name" and (arg[1] in self.array_names or arg[1] in self.value_names):
                        return f"edg_array_value_len({arg[1]})"
                    if isinstance(arg, tuple) and arg[0] == "list":
                        return repr(float(len(arg[1])))
                if name in self.functions:
                    args = ', '.join(self.value_expr(a) for a in node[2])
                    return f"({name}({args})).as.number"
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
        old_value_names = self.value_names
        old_function_locals = self.function_locals
        self.value_names = set(old_value_names) | set(params)
        old_target = self.target
        old_depth = self.function_depth
        self.function_depth += 1
        self.target = self.functions_code
        raw_params = [f"__edg_arg_{p}" for p in params]
        self.emit(f"EdgValue {name}({', '.join('EdgValue ' + p for p in raw_params)}) {{")
        self.indent += 1
        self.function_locals = list(params)
        for p, raw in zip(params, raw_params):
            self.emit(f"EdgValue {p} = edg_clone_value({raw});")
        old = self.return_mode; old_return = self.function_has_return
        self.return_mode = True; self.function_has_return = False
        self.block(body, 0, -1)
        self.return_mode = old; has_return = self.function_has_return; self.function_has_return = old_return
        if not has_return:
            for local in reversed(self.function_locals): self.emit(f"edg_free_value({local});")
            self.emit("return edg_nothing();")
        self.indent -= 1; self.emit("}")
        self.target = old_target
        self.function_depth = old_depth
        self.value_names = old_value_names
        self.function_locals = old_function_locals
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
                rhs = "edg_nothing()" if text == "return" else self.value_expr(parse_expr(text[7:]))
                result = self.new_temp("return")
                self.emit(f"EdgValue {result} = edg_clone_value({rhs});")
                for local in reversed(self.function_locals): self.emit(f"edg_free_value({local});")
                self.emit(f"return {result};"); self.function_has_return = True; i += 1; continue
            if text.startswith("let ") or text.startswith("var "):
                m = re.fullmatch(r"(?:let|var)\s+([A-Za-z_]\w*)\s*=\s*(.+)", text)
                if not m: raise EdgError(f"line {line}: invalid native declaration")
                name, rhs = m.groups(); self.names.add(name)
                node = parse_expr(rhs)
                # Keep declarations primitive for ABI compatibility, while
                # allowing values assigned from EdgValue expressions to retain
                # their runtime type at expression boundaries.
                if (isinstance(node, tuple) and node[0] in ("bin", "index")) or (isinstance(node, tuple) and node[0] == "call" and isinstance(node[1], tuple) and node[1][0] == "name" and (node[1][1] in self.functions or node[1][1] in ("pop", "join"))): 
                    self.value_names.add(name)
                    self.emit(f"EdgValue {name} = {self.value_expr(node)};")
                    i += 1; continue
                if isinstance(node, str):
                    self.string_names.add(name)
                    self.value_names.add(name)
                    self.emit(f"EdgValue {name} = edg_string({self.expr(node)});")
                elif isinstance(node, tuple) and node[0] == "list":
                    items = node[1]
                    self.array_names.add(name)
                    self.value_names.add(name)
                    self.array_lengths[name] = len(items)
                    self.emit(f"EdgValue {name} = edg_array_new({len(items)});")
                    for array_index, item in enumerate(items):
                        self.emit(f"edg_array_value_set({name}, {array_index}, {self.value_expr(item)});")
                else:
                    self.emit(f"double {name} = {self.expr(node)};")
                if self.return_mode and name in self.value_names: self.function_locals.append(name)
                i += 1; continue
            m = re.fullmatch(r"([A-Za-z_]\w*)\[([^]]+)\]\s*=\s*(.+)", text)
            if m:
                name, index, rhs = m.groups()
                if name not in self.array_names and name not in self.value_names:
                    raise EdgError(f"line {line}: native indexed assignment requires an array")
                idx = self.expr(parse_expr(index))
                self.emit(f"edg_array_value_set({name}, (int)({idx}), {self.value_expr(parse_expr(rhs))});")
                i += 1; continue
            m = re.fullmatch(r"([A-Za-z_]\w*)\s*(=|\+=|-=|\*=|/=)\s*(.+)", text)
            if m:
                name, op, rhs = m.groups(); self.names.add(name)
                node = parse_expr(rhs)
                if name in self.value_names:
                    if op == "=":
                        self.emit(f"edg_assign_value(&{name}, {self.value_expr(node)});")
                    else:
                        fn = {"+=": "edg_add", "-=": "edg_sub", "*=": "edg_mul", "/=": "edg_div"}.get(op)
                        if fn is None:
                            raise EdgError(f"line {line}: unsupported assignment operator")
                        self.emit(f"edg_assign_value(&{name}, {fn}({name}, {self.value_expr(node)}));")
                else:
                    self.emit(f"{name} {op} {self.expr(node)};")
                i += 1; continue
            m = re.fullmatch(r"(push|pop|clear|compact)\((.*)\)", text)
            if m:
                args = [x.strip() for x in m.group(2).split(',', 1)] if m.group(2).strip() else []
                if m.group(1) == "push":
                    if len(args) != 2:
                        raise EdgError(f"line {line}: push expects array and value")
                    self.emit(f"edg_array_push({self.value_expr(parse_expr(args[0]))}, {self.value_expr(parse_expr(args[1]))});")
                elif m.group(1) == "pop":
                    if len(args) != 1:
                        raise EdgError(f"line {line}: pop expects an array")
                    self.emit(f"edg_free_value(edg_array_pop({self.value_expr(parse_expr(args[0]))}));")
                elif m.group(1) == "clear":
                    if len(args) != 1:
                        raise EdgError(f"line {line}: clear expects an array")
                    self.emit(f"edg_array_clear({self.value_expr(parse_expr(args[0]))});")
                else:
                    if len(args) != 1:
                        raise EdgError(f"line {line}: compact expects an array")
                    self.emit(f"edg_array_compact({self.value_expr(parse_expr(args[0]))});")
                i += 1; continue
            # push and clear are handled by the combined builtin statement parser above.
            m = re.fullmatch(r"print\((.*)\)", text)
            if m:
                node = parse_expr(m.group(1).strip())
                printed = self.new_temp("print")
                self.emit(f"EdgValue {printed} = edg_clone_value({self.value_expr(node)});")
                self.emit(f"edg_print_value({printed});")
                self.emit(f"edg_free_value({printed});")
                i += 1; continue
            if text.startswith("if "):
                condition = text[3:].strip()
                self.emit(f"if ({self.truth_expr(parse_expr(condition))}) {{")
                self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1; self.emit("}")
                while i < len(rows) and rows[i][0] == level and (rows[i][1].startswith("elif ") or rows[i][1] == "else"):
                    branch = rows[i][1]
                    if branch == "else":
                        self.emit("else {")
                    else:
                        self.emit(f"else if ({self.truth_expr(parse_expr(branch[5:].strip()))}) {{")
                    self.indent += 1; i = self.block(rows, i + 1, level); self.indent -= 1; self.emit("}")
                continue
            if text.startswith("while "):
                condition = text[6:].strip()
                self.emit(f"while ({self.truth_expr(parse_expr(condition))}) {{")
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
        for name in reversed(sorted(self.value_names)):
            self.emit(f"edg_free_value({name});")
        self.lines.append("    return 0;\n}\n")
        # Keep the runtime visible to later compiler stages and make the
        # migration explicit without changing existing primitive codegen.
        self.lines.append("/* Native backend runtime: EdgValue is available. */\n")
        # 函数体是在主函数编译过程中收集的，插入到 main 之前。
        if self.functions_code:
            self.lines[2:2] = self.functions_code
        # Generated code still uses the compatibility layout for now; rename
        # it explicitly so the public EdgValue ABI remains available beside it.
        return "".join(self.lines).replace("__EDG_VALUE_HEADER__", "edg_value.h").replace("EdgValue", "EdgLegacyValue")
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
        # Keep the shared C runtime in the native build during migration.
        # Its public ABI is available to generated code as features move over.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shared_runtime = os.path.join(project_root, "c", "edg_value.c")
        command = [cc, "-O2", "-I", os.path.join(project_root, "include"), c_path]
        if os.path.isfile(shared_runtime):
            command.append(shared_runtime)
        command += ["-o", output]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise EdgError("C compiler failed: " + (result.stderr.strip() or result.stdout.strip()))
    return output
