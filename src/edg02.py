#!/usr/bin/env python3
"""EDG 0.2: lexer + Pratt expression parser + indentation interpreter."""
from dataclasses import dataclass
import re, sys

class EdgError(Exception): pass
class ReturnSignal(Exception):
    def __init__(self, value): self.value = value

@dataclass
class Tok:
    kind: str
    text: str

class Lexer:
    pattern = re.compile(r'''\s*(?:(\d+(?:\.\d+)?)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|([A-Za-z_]\w*)|(==|!=|<=|>=|\?\.|\?\?|\+=|-=|\*=|/=|=>|[+\-*/%<>=.,()\[\]{}?:]))''')
    def __init__(self, text):
        self.ts=[]; pos=0
        while pos < len(text):
            m=self.pattern.match(text,pos)
            if not m:
                raise EdgError(f"invalid expression near '{text[pos:]}'")
            pos=m.end(); number,string,name,op=m.groups()
            if number: self.ts.append(Tok('number',number))
            elif string: self.ts.append(Tok('string',string))
            elif name: self.ts.append(Tok('name',name))
            else: self.ts.append(Tok(op,op))
        self.ts.append(Tok('eof',''))

class Parser:
    def __init__(self,text): self.l=Lexer(text); self.i=0
    def peek(self): return self.l.ts[self.i]
    def take(self,kind=None):
        t=self.peek()
        if kind and t.kind!=kind: raise EdgError(f"expected '{kind}', got '{t.text}'")
        self.i+=1; return t
    def expr(self,minp=0):
        t=self.take()
        if t.kind=='number': left=float(t.text) if '.' in t.text else int(t.text)
        elif t.kind=='string':
            try: left=bytes(t.text[1:-1],'utf8').decode('unicode_escape')
            except Exception: left=t.text[1:-1]
        elif t.kind=='name':
            if t.text in ('true','false','nothing'): left={'true':True,'false':False,'nothing':None}[t.text]
            else: left=('name',t.text)
        elif t.kind=='-': left=('unary','-',self.expr(70))
        elif t.kind=='+': left=('unary','+',self.expr(70))
        elif t.kind=='(': left=self.expr(); self.take(')')
        elif t.kind=='[':
            left=('list',[] if self.peek().kind==']' else self.args(']')); self.take(']')
        elif t.kind=='{':
            items=[]
            while self.peek().kind!='}':
                # 字典键也按正常表达式解析，保证 "hp" 与 data["hp"] 使用同一个键值。
                key=self.expr(); self.take(':'); items.append((key,self.expr()))
                if self.peek().kind!=',': break
                self.take(',')
            self.take('}'); left=('dict',items)
        else: raise EdgError(f"unexpected '{t.text}'")
        while True:
            t=self.peek()
            if t.kind=='(':
                self.take(); left=('call',left,[] if self.peek().kind==')' else self.args(')')); self.take(')'); continue
            if t.kind in ('.','?.'):
                self.take(); left=('get',left,self.take('name').text,t.kind=='?.'); continue
            if t.kind=='[':
                self.take(); index=self.expr(); self.take(']'); left=('index',left,index); continue
            operator = t.text if t.kind == 'name' and t.text in ('and', 'or') else t.kind
            prec={'??':10,'or':15,'and':20,'==':30,'!=':30,'<':40,'>':40,'<=':40,'>=':40,'+':50,'-':50,'*':60,'/':60,'%':60}.get(operator)
            if prec is None or prec<minp: break
            self.take(); right=self.expr(prec+1); left=('bin',operator,left,right)
        return left
    def args(self,end):
        out=[]
        while True:
            out.append(self.expr())
            if self.peek().kind!=',': break
            self.take(',')
        return out

def parse_expr(s): return Parser(s).expr()

class Env(dict):
    def __init__(self,parent=None): super().__init__(); self.parent=parent
    def getv(self,k):
        if k in self:return self[k]
        if self.parent:return self.parent.getv(k)
        raise EdgError(f"name '{k}' is not defined")

class Fn:
    def __init__(self,name,params,body,env): self.name=name; self.params=params; self.body=body; self.env=env
    def __call__(self,*args):
        if len(args)!=len(self.params): raise EdgError(f"function {self.name} expects {len(self.params)} arguments")
        e=Env(self.env); e.update(zip(self.params,args))
        try: execute(self.body,e)
        except ReturnSignal as r:return r.value

class Obj:
    def __init__(self): self.fields={}
    def __repr__(self): return '<object>'

def truth(v): return bool(v)
def value(x,e):
    if not isinstance(x,tuple): return x
    k=x[0]
    if k=='name': return e.getv(x[1])
    if k=='list': return [value(a,e) for a in x[1]]
    if k=='unary': return -value(x[2],e) if x[1]=='-' else value(x[2],e)
    if k=='call':
        fn=value(x[1],e); return fn(*[value(a,e) for a in x[2]])
    if k=='get':
        base=value(x[1],e)
        if base is None and x[3]: return None
        if base is None: raise EdgError('null value accessed without ?.')
        if isinstance(base,dict): return base.get(x[2])
        return getattr(base,x[2],None) if not hasattr(base,x[2]) else getattr(base,x[2])
    if k=='index': return value(x[1],e)[value(x[2],e)]
    if k=='bin':
        op=x[1]; a=value(x[2],e)
        if op=='??': return a if a is not None else value(x[3],e)
        if op=='and' and not truth(a): return False
        if op=='or' and truth(a): return True
        b=value(x[3],e)
        return {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b,'%':lambda:a%b,'==':lambda:a==b,'!=':lambda:a!=b,'<':lambda:a<b,'>':lambda:a>b,'<=':lambda:a<=b,'>=':lambda:a>=b,'and':lambda:truth(a) and truth(b),'or':lambda:truth(a) or truth(b)}[op]()
    raise EdgError('invalid expression')

def lines_of(src):
    out=[]
    for n,r in enumerate(src.splitlines(),1):
        if '\t' in r: raise EdgError(f'line {n}: use spaces, not tabs')
        s=r.strip()
        if s and not s.startswith('#'): out.append((len(r)-len(r.lstrip()),s,n))
    return out

def block(ls,start,parent):
    if start>=len(ls) or ls[start][0]<=parent: raise EdgError(f"line {ls[start-1][2]}: expected indented block")
    i=start
    while i<len(ls) and ls[i][0]>parent:i+=1
    return ls[start:i],i

def execute(ls,e):
    i=0
    while i<len(ls):
        ind,s,n=ls[i]
        m=re.fullmatch(r'fn\s+(\w+)\s*\((.*?)\)',s)
        if m:
            b,i=block(ls,i+1,ind); e[m.group(1)]=Fn(m.group(1),[x.strip() for x in m.group(2).split(',') if x.strip()],b,e); continue
        if s.startswith('if '):
            branches=[]; cond=s[3:]; b,i=block(ls,i+1,ind); branches.append((cond,b))
            while i<len(ls) and ls[i][0]==ind and (ls[i][1].startswith('elif ') or ls[i][1]=='else'):
                q=ls[i][1]; b,i=block(ls,i+1,ind); branches.append((None if q=='else' else q[5:],b))
            for q,b in branches:
                if q is None or truth(value(parse_expr(q),e)): execute(b,e); break
            continue
        if s=='return': raise ReturnSignal(None)
        if s.startswith('return '): raise ReturnSignal(value(parse_expr(s[7:]),e))
        m=re.fullmatch(r'(?:let|var)\s+(\w+)(\?)?\s*=\s*(.+)',s)
        if m: e[m.group(1)]=value(parse_expr(m.group(3)),e); i+=1; continue
        m=re.fullmatch(r'(\w+)\s*(=|\+=|-=|\*=|/=)\s*(.+)',s)
        if m:
            name,op,rhs=m.groups(); v=value(parse_expr(rhs),e)
            if op=='=': e[name]=v
            else: e[name]={'+' : lambda a:a+v,'-' :lambda a:a-v,'*':lambda a:a*v,'/':lambda a:a/v}[op[0]](e.getv(name))
            i+=1; continue
        value(parse_expr(s),e); i+=1

def run(path):
    e=Env(); e['print']=lambda *x:print(*x)
    try:
        with open(path,encoding='utf8') as f: execute(lines_of(f.read()),e)
    except (EdgError,FileNotFoundError) as x: print('EDG error:',x,file=sys.stderr); return 1
    return 0

if __name__=='__main__':
    if len(sys.argv)!=2: print('usage: python3 src/edg02.py file.edg'); sys.exit(2)
    sys.exit(run(sys.argv[1]))