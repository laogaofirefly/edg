#!/usr/bin/env python3
"""EDG 0.3 - bytecode compiler and virtual machine prototype."""
import sys, os
from edg02 import EdgError, ReturnSignal, parse_expr, lines_of, value as eval_ast
try:
    import edg_hot
except ImportError:
    edg_hot = None

class Chunk:
    def __init__(self): self.code=[]; self.constants=[]
    def emit(self, op, arg=None):
        self.code.append((op,arg)); return len(self.code)-1
    def patch(self, pos, target): self.code[pos]=(self.code[pos][0],target)
    def const(self, value):
        self.constants.append(value); return len(self.constants)-1

def parameter_specs(text):
    result=[]
    for raw in [x.strip() for x in text.split(',') if x.strip()]:
        if '=' in raw:
            name, expr = [x.strip() for x in raw.split('=',1)]
            result.append((name, lambda expr=expr: eval_ast(parse_expr(expr), Env())))
        else: result.append((raw, None))
    return result

class Compiler:
    def __init__(self):
        self.chunk=Chunk()
        # 每层循环保存 continue/break 的待回填跳转位置。
        self.loop_stack=[]
    def append_chunk(self, other):
        offset = len(self.chunk.constants)
        self.chunk.constants.extend(other.constants)
        code_offset = len(self.chunk.code)
        relocatable = {'JUMP', 'JUMP_IF_FALSE', 'ITER_NEXT'}
        for op, arg in other.code:
            if op == 'CONST': arg += offset
            elif op in relocatable and arg is not None: arg += code_offset
            self.chunk.code.append((op, arg))
    def compile_expr(self, node):
        if not isinstance(node,tuple): self.chunk.emit('CONST',self.chunk.const(node)); return
        kind=node[0]
        if kind=='name': self.chunk.emit('LOAD',node[1]); return
        if kind=='list':
            for item in node[1]: self.compile_expr(item)
            self.chunk.emit('BUILD_LIST',len(node[1])); return
        if kind=='dict':
            for key,item in node[1]:
                self.compile_expr(key); self.compile_expr(item)
            self.chunk.emit('BUILD_DICT',len(node[1])); return
        if kind=='unary': self.compile_expr(node[2]); self.chunk.emit('UNARY',node[1]); return
        if kind=='get':
            self.compile_expr(node[1]); self.chunk.emit('GET_SAFE' if node[3] else 'GET',node[2]); return
        if kind=='index':
            self.compile_expr(node[1]); self.compile_expr(node[2]); self.chunk.emit('INDEX'); return
        if kind=='call':
            self.compile_expr(node[1])
            for arg in node[2]: self.compile_expr(arg)
            self.chunk.emit('CALL',len(node[2])); return
        if kind=='bin':
            self.compile_expr(node[2]); self.compile_expr(node[3]); self.chunk.emit('BINARY',node[1]); return
        raise EdgError('unknown expression node')

    def compile_lines(self, lines):
        i=0
        while i<len(lines):
            indent,text,line=lines[i]
            if text.startswith('import '):
                import re
                module=re.fullmatch(r'import\s+([A-Za-z_]\w*)',text)
                if not module: raise EdgError(f'line {line}: invalid import statement')
                self.chunk.emit('IMPORT',module.group(1)); self.chunk.emit('STORE',module.group(1)); i+=1; continue
            if text.startswith('export '):
                exported=text[7:].strip()
                self.compile_expr(parse_expr(exported)); self.chunk.emit('EXPORT',exported); i+=1; continue
            if text.startswith('fn '):
                import re
                m=re.fullmatch(r'fn\s+(\w+)\s*\((.*?)\)',text)
                if not m: raise EdgError(f'line {line}: invalid function declaration')
                body,i=split_block(lines,i+1,indent)
                sub=Compiler(); sub.compile_lines(body); sub.chunk.emit('CONST',sub.chunk.const(None)); sub.chunk.emit('RETURN')
                self.chunk.emit('MAKE_FUNCTION',(m.group(1),parameter_specs(m.group(2)),sub.chunk)); self.chunk.emit('STORE',m.group(1)); continue
            if text.startswith('class '):
                import re
                m=re.fullmatch(r'class\s+(\w+)', text)
                if not m: raise EdgError(f'line {line}: invalid class declaration')
                body,i=split_block(lines,i+1,indent); methods={}; defaults={}; j=0
                while j<len(body):
                    _,member,ml=body[j]
                    fm=re.fullmatch(r'(?:fn\s+)?(init|\w+)\s*\((.*?)\)',member)
                    if fm:
                        mb,j=split_block(body,j+1,body[j][0]); sub=Compiler(); sub.compile_lines(mb); sub.chunk.emit('CONST',sub.chunk.const(None)); sub.chunk.emit('RETURN')
                        methods[fm.group(1)]=ByteFunction(fm.group(1),[('self',None)]+parameter_specs(fm.group(2)),sub.chunk,None); continue
                    dm=re.fullmatch(r'(?:let|var)\s+(\w+)\s*=\s*(.+)',member)
                    if dm: defaults[dm.group(1)]=eval_ast(parse_expr(dm.group(2)),Env()); j+=1; continue
                    raise EdgError(f'line {ml}: invalid class member')
                self.chunk.emit('CONST',self.chunk.const(Class(m.group(1),methods,defaults))); self.chunk.emit('STORE',m.group(1)); continue
            if text == 'break':
                if not self.loop_stack: raise EdgError(f'line {line}: break outside loop')
                self.loop_stack[-1]['breaks'].append(self.chunk.emit('JUMP',None)); i+=1; continue
            if text == 'continue':
                if not self.loop_stack: raise EdgError(f'line {line}: continue outside loop')
                self.loop_stack[-1]['continues'].append(self.chunk.emit('JUMP',None)); i+=1; continue
            if text.startswith('while '):
                loop_start=len(self.chunk.code); self.compile_expr(parse_expr(text[6:].strip())); exit_jump=self.chunk.emit('JUMP_IF_FALSE',None)
                loop={'breaks':[],'continues':[],'continue_target':loop_start}; self.loop_stack.append(loop)
                body,i=split_block(lines,i+1,indent); sub=Compiler(); sub.loop_stack=self.loop_stack
                old_b,old_c=len(loop['breaks']),len(loop['continues']); sub.compile_lines(body)
                base=len(self.chunk.code); self.append_chunk(sub.chunk)
                loop['breaks'][old_b:]=[p+base for p in loop['breaks'][old_b:]]
                loop['continues'][old_c:]=[p+base for p in loop['continues'][old_c:]]
                self.chunk.emit('JUMP',loop_start); end=len(self.chunk.code); self.chunk.patch(exit_jump,end)
                for p in loop['breaks']+loop['continues']: self.chunk.patch(p,end if p in loop['breaks'] else loop['continue_target'])
                self.loop_stack.pop(); continue
            if text.startswith('for '):
                import re
                fm=re.fullmatch(r'for\s+(\w+)\s+in\s+(.+)',text)
                if not fm: raise EdgError(f'line {line}: invalid for statement')
                var,source=fm.groups()
                self.compile_expr(parse_expr(source)); self.chunk.emit('ITER_INIT')
                loop_start=len(self.chunk.code)
                next_jump=self.chunk.emit('ITER_NEXT',None); self.chunk.emit('STORE',var)
                loop={'breaks':[],'continues':[],'continue_target':loop_start}; self.loop_stack.append(loop)
                body,i=split_block(lines,i+1,indent); sub=Compiler(); sub.loop_stack=self.loop_stack
                old_b,old_c=len(loop['breaks']),len(loop['continues']); sub.compile_lines(body)
                base=len(self.chunk.code); self.append_chunk(sub.chunk)
                loop['breaks'][old_b:]=[p+base for p in loop['breaks'][old_b:]]
                loop['continues'][old_c:]=[p+base for p in loop['continues'][old_c:]]
                self.chunk.emit('JUMP',loop_start); end=len(self.chunk.code); self.chunk.patch(next_jump,end)
                for p in loop['breaks']: self.chunk.patch(p,end)
                for p in loop['continues']: self.chunk.patch(p,loop['continue_target'])
                self.loop_stack.pop(); continue
            if text.startswith('if '):
                branches=[]; body,next_i=split_block(lines,i+1,indent); branches.append((text[3:].strip(),body)); i=next_i
                while i<len(lines) and lines[i][0]==indent and (lines[i][1].startswith('elif ') or lines[i][1]=='else'):
                    q=lines[i][1]; body,next_i=split_block(lines,i+1,indent); branches.append((None if q=='else' else q[5:].strip(),body)); i=next_i
                exits=[]; next_tests=[]
                for index,(cond,body) in enumerate(branches):
                    if cond is not None:
                        self.compile_expr(parse_expr(cond)); jump=self.chunk.emit('JUMP_IF_FALSE',None); next_tests.append(jump)
                    sub=Compiler(); sub.loop_stack=self.loop_stack
                    old_b=len(self.loop_stack[-1]['breaks']) if self.loop_stack else 0
                    old_c=len(self.loop_stack[-1]['continues']) if self.loop_stack else 0
                    sub.compile_lines(body); base=len(self.chunk.code); self.append_chunk(sub.chunk)
                    if self.loop_stack:
                        loop=self.loop_stack[-1]
                        loop['breaks'][old_b:]=[p+base for p in loop['breaks'][old_b:]]
                        loop['continues'][old_c:]=[p+base for p in loop['continues'][old_c:]]
                    exits.append(self.chunk.emit('JUMP',None))
                    if cond is not None: self.chunk.patch(next_tests.pop(),len(self.chunk.code))
                end=len(self.chunk.code)
                for p in exits:self.chunk.patch(p,end)
                continue
            if text=='return': self.chunk.emit('CONST',self.chunk.const(None)); self.chunk.emit('RETURN'); i+=1; continue
            if text.startswith('return '): self.compile_expr(parse_expr(text[7:])); self.chunk.emit('RETURN'); i+=1; continue
            import re
            m=re.fullmatch(r'(?:let|var)\s+(\w+)(\?)?\s*=\s*(.+)',text)
            if m: self.compile_expr(parse_expr(m.group(3))); self.chunk.emit('STORE',m.group(1)); i+=1; continue
            # 容器下标赋值：obj[index] = value，以及复合赋值。
            m=re.fullmatch(r'(.+)\[(.+)\]\s*(=|\+=|-=|\*=|/=)\s*(.+)',text)
            if m:
                target,index,op,rhs=m.groups()
                self.compile_expr(parse_expr(target.strip())); self.compile_expr(parse_expr(index.strip()))
                if op != '=':
                    self.chunk.emit('DUP2'); self.chunk.emit('INDEX')
                self.compile_expr(parse_expr(rhs))
                if op != '=': self.chunk.emit('BINARY',op[0])
                self.chunk.emit('SET_INDEX'); i+=1; continue
            m=re.fullmatch(r'(\w+)\.(\w+)\s*(=|\+=|-=|\*=|/=)\s*(.+)',text)
            if m:
                obj,name,op,rhs=m.groups(); self.compile_expr(parse_expr(obj))
                if op != '=': self.chunk.emit('DUP'); self.chunk.emit('GET',name)
                self.compile_expr(parse_expr(rhs))
                if op != '=': self.chunk.emit('BINARY',op[0])
                self.chunk.emit('SET',name); i+=1; continue
            m=re.fullmatch(r'(\w+)\s*(=|\+=|-=|\*=|/=)\s*(.+)',text)
            if m:
                name,op,rhs=m.groups()
                if op!='=': self.chunk.emit('LOAD',name)
                self.compile_expr(parse_expr(rhs))
                if op!='=': self.chunk.emit('BINARY',op[0])
                self.chunk.emit('STORE',name); i+=1; continue
            self.compile_expr(parse_expr(text)); self.chunk.emit('POP'); i+=1
        return self.chunk

def split_block(lines,start,parent):
    if start>=len(lines) or lines[start][0]<=parent: raise EdgError(f'line {lines[start-1][2]}: expected indented block')
    i=start
    while i<len(lines) and lines[i][0]>parent:i+=1
    return lines[start:i],i

class Frame:
    def __init__(self,chunk,env): self.chunk=chunk; self.env=env; self.stack=[]; self.ip=0

class Env(dict):
    def __init__(self,parent=None): super().__init__(); self.parent=parent
    def getv(self,k):
        if k in self:return self[k]
        if self.parent:return self.parent.getv(k)
        raise EdgError(f"name '{k}' is not defined")
class ByteFunction:
    def __init__(self,name,params,chunk,closure):
        self.name=name; self.params=params; self.chunk=chunk; self.closure=closure
    def __call__(self,*args):
        required=len([p for p,d in self.params if d is None])
        if len(args)<required or len(args)>len(self.params): raise EdgError(f'function {self.name} argument count mismatch')
        env=Env(self.closure)
        for index,(param,default) in enumerate(self.params):
            env[param]=args[index] if index<len(args) else (default() if callable(default) else default)
        return VM().run(self.chunk,env)

class Instance:
    def __init__(self, cls): self.cls=cls; self.fields={}
    def get(self, name):
        if name in self.fields: return self.fields[name]
        fn=self.cls.methods.get(name)
        if fn is not None:
            return lambda *args: fn(self,*args)
        return None
    def set(self,name,value): self.fields[name]=value
    def __repr__(self): return f'<{self.cls.name}>'

class Class:
    def __init__(self,name,methods,defaults): self.name=name; self.methods=methods; self.defaults=defaults
    def __call__(self,*args):
        obj=Instance(self)
        obj.fields.update(self.defaults)
        init=self.methods.get('init')
        if init is not None: init(obj,*args)
        elif args: raise EdgError(f'class {self.name} has no init method')
        return obj


def binary(op,a,b):
    if op=='??': return a if a is not None else b
    if op=='+': return a+b
    if op=='-': return a-b
    if op=='*': return a*b
    if op=='/': return a/b
    if op=='%': return a%b
    if op=='==': return a==b
    if op=='!=': return a!=b
    if op=='<': return a<b
    if op=='>': return a>b
    if op=='<=': return a<=b
    if op=='>=': return a>=b
    if op=='and': return bool(a) and bool(b)
    if op=='or': return bool(a) or bool(b)
    raise EdgError(f'unknown operator {op}')

def load_module(name, base_dir, cache):
    if name in cache: return cache[name]
    # Python 标准模块桥接：用于 World、Android 和图形运行时。
    if name in ('world', 'game'):
        import importlib
        module = importlib.import_module(name)
        cache[name] = {k: v for k, v in vars(module).items() if not k.startswith('_')}
        return cache[name]
    path = os.path.join(base_dir, name + '.edg')
    if not os.path.exists(path): raise EdgError(f"module '{name}' not found")
    with open(path, encoding='utf8') as f: lines=lines_of(f.read())
    compiler=Compiler(); chunk=compiler.compile_lines(lines); exports={}
    env=Env(); env['print']=lambda *x:print(*x); env['len']=len
    if edg_hot is not None: env['hot']=edg_hot
    cache[name]=exports
    VM().run(chunk,env,exports)
    if not exports: exports.update({k:v for k,v in env.items() if not k.startswith('_')})
    return exports

class VM:
    def __init__(self, cache=None): self.cache=cache if cache is not None else {}
    def run(self,chunk,env,exports=None):
        f=Frame(chunk,env); c=chunk.code
        while f.ip<len(c):
            op,arg=c[f.ip]; f.ip+=1
            if op=='CONST':f.stack.append(f.chunk.constants[arg])
            elif op=='LOAD':f.stack.append(env.getv(arg))
            elif op=='IMPORT': f.stack.append(load_module(arg, os.getcwd(), getattr(self,'cache',{})))
            elif op=='EXPORT':
                if exports is not None: exports[arg]=f.stack.pop()
                else: f.stack.pop()
            elif op=='STORE':env[arg]=f.stack.pop()
            elif op=='POP':f.stack.pop()
            elif op=='DUP':f.stack.append(f.stack[-1])
            elif op=='SET':
                value=f.stack.pop(); obj=f.stack.pop()
                if isinstance(obj,Instance): obj.set(arg,value)
                elif isinstance(obj,dict): obj[arg]=value
                else: raise EdgError('cannot set property on this value')
            elif op=='SWAP':a=f.stack.pop(); b=f.stack.pop(); f.stack.extend([a,b])
            elif op=='BUILD_LIST':f.stack.append([f.stack.pop() for _ in range(arg)][::-1])
            elif op=='BUILD_DICT':
                d={}
                for _ in range(arg): value=f.stack.pop(); key=f.stack.pop(); d[key]=value
                f.stack.append(d)
            elif op=='ITER_INIT': f.stack.append(iter(f.stack.pop()))
            elif op=='ITER_NEXT':
                try: f.stack.append(next(f.stack[-1]))
                except StopIteration: f.stack.pop(); f.ip=arg
            elif op=='BREAK': raise BreakSignal()
            elif op=='CONTINUE': raise ContinueSignal()
            elif op=='UNARY':
                a=f.stack.pop(); f.stack.append(-a if arg=='-' else a)
            elif op=='BINARY':
                b=f.stack.pop(); a=f.stack.pop(); f.stack.append(binary(arg,a,b))
            elif op=='GET' or op=='GET_SAFE':
                a=f.stack.pop()
                if a is None and op=='GET_SAFE': f.stack.append(None)
                elif a is None: raise EdgError('null value accessed without ?.')
                elif isinstance(a,dict): f.stack.append(a.get(arg))
                elif isinstance(a,Instance): f.stack.append(a.get(arg))
                else: f.stack.append(getattr(a,arg,None))
            elif op=='INDEX':b=f.stack.pop();a=f.stack.pop();f.stack.append(a[b])
            elif op=='DUP2':
                # [obj, index] -> [obj, index, obj, index]
                obj, index = f.stack[-2], f.stack[-1]; f.stack.extend([obj, index])
            elif op=='SET_INDEX':
                value=f.stack.pop(); index=f.stack.pop(); obj=f.stack.pop()
                try: obj[index]=value
                except (TypeError, KeyError, IndexError) as e: raise EdgError(f'cannot assign index: {e}')
            elif op=='CALL':
                args=f.stack[-arg:] if arg else []; del f.stack[len(f.stack)-arg:]; fn=f.stack.pop(); f.stack.append(fn(*args))
            elif op=='MAKE_FUNCTION':
                name,params,sub=arg; f.stack.append(ByteFunction(name,params,sub,env))
            elif op=='JUMP':f.ip=arg
            elif op=='JUMP_IF_FALSE':
                if not f.stack.pop():f.ip=arg
            elif op=='RETURN':return f.stack.pop() if f.stack else None
        return None

def run(path):
    try:
        with open(path,encoding='utf8') as f: lines=lines_of(f.read())
        compiler=Compiler(); chunk=compiler.compile_lines(lines); env=Env()
        env['print']=lambda *x:print(*x)
        if edg_hot is not None:
            env['hot']=edg_hot
            try:
                from spatial import nearby
                env['nearby']=nearby
            except ImportError:
                pass
        env['len']=lambda x:len(x)
        env['range']=lambda *x:list(range(*x))

        env['type']=lambda x: 'nothing' if x is None else ('number' if isinstance(x,(int,float)) else ('text' if isinstance(x,str) else ('list' if isinstance(x,list) else 'object')))
        vm=VM({}); vm.run(chunk,env); return 0
    except (EdgError,FileNotFoundError,TypeError,KeyError,IndexError,StopIteration) as e:
        print('EDG error:',e,file=sys.stderr); return 1

if __name__=='__main__':
    if len(sys.argv)!=2: print('usage: python3 src/edg03.py file.edg'); sys.exit(2)
    sys.exit(run(sys.argv[1]))