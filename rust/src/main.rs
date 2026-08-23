use std::collections::HashMap;
use std::fmt;

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Nothing,
    Number(f64),
    Bool(bool),
    Text(String),
    List(Vec<Value>),
}

impl Value {
    fn truthy(&self) -> bool {
        match self { Value::Nothing => false, Value::Bool(v) => *v, Value::Number(v) => *v != 0.0, Value::Text(v) => !v.is_empty(), Value::List(v) => !v.is_empty() }
    }
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self { Value::Nothing => write!(f, "nothing"), Value::Number(v) if v.fract() == 0.0 => write!(f, "{}", *v as i64), Value::Number(v) => write!(f, "{}", v), Value::Bool(v) => write!(f, "{}", v), Value::Text(v) => write!(f, "{}", v), Value::List(v) => { write!(f, "[")?; for (i, x) in v.iter().enumerate() { if i > 0 { write!(f, ", ")?; } write!(f, "{}", x)?; } write!(f, "]") } }
    }
}

#[derive(Clone, Debug)]
pub enum Op {
    Const(Value), Load(String), Store(String), Pop,
    Add, Sub, Mul, Div, Less, Greater, Equal,
    Jump(usize), JumpIfFalse(usize),
    BuildList(usize), IterInit, IterNext(usize),
    Print(usize), Return,
}

#[derive(Default)]
pub struct Vm { pub ip: usize, pub stack: Vec<Value>, pub globals: HashMap<String, Value>, iterators: Vec<Vec<Value>> }

impl Vm {
    pub fn run(&mut self, code: &[Op]) -> Result<Value, String> {
        while self.ip < code.len() {
            let op = code[self.ip].clone(); self.ip += 1;
            match op {
                Op::Const(v) => self.stack.push(v),
                Op::Load(name) => self.stack.push(self.globals.get(&name).cloned().ok_or(format!("name '{}' is not defined", name))?),
                Op::Store(name) => { let v = self.stack.pop().ok_or("stack underflow")?; self.globals.insert(name, v); },
                Op::Pop => { self.stack.pop().ok_or("stack underflow")?; },
                Op::Add | Op::Sub | Op::Mul | Op::Div | Op::Less | Op::Greater | Op::Equal => self.binary(op)?,
                Op::Jump(target) => self.ip = target,
                Op::JumpIfFalse(target) => if !self.stack.pop().ok_or("stack underflow")?.truthy() { self.ip = target },
                Op::BuildList(n) => { let start = self.stack.len() - n; let items: Vec<Value> = self.stack.drain(start..).collect(); self.stack.push(Value::List(items)); },
                Op::IterInit => { let v = self.stack.pop().ok_or("stack underflow")?; match v { Value::List(items) => self.iterators.push(items), _ => return Err("for requires a list".into()) } },
                Op::IterNext(end) => { match self.iterators.last_mut().and_then(|x| if x.is_empty() { None } else { Some(x.remove(0)) }) { Some(v) => self.stack.push(v), None => { self.iterators.pop(); self.ip = end; } } },
                Op::Print(n) => { let start = self.stack.len() - n; let args: Vec<_> = self.stack.drain(start..).collect(); println!("{}", args.iter().map(ToString::to_string).collect::<Vec<_>>().join(" ")); },
                Op::Return => return Ok(self.stack.pop().unwrap_or(Value::Nothing)),
            }
        }
        Ok(Value::Nothing)
    }

    fn binary(&mut self, op: Op) -> Result<(), String> {
        let b = self.stack.pop().ok_or("stack underflow")?; let a = self.stack.pop().ok_or("stack underflow")?;
        let (x, y) = match (&a, &b) { (Value::Number(x), Value::Number(y)) => (*x, *y), _ => return Err("numeric operation requires numbers".into()) };
        let out = match op { Op::Add => Value::Number(x+y), Op::Sub => Value::Number(x-y), Op::Mul => Value::Number(x*y), Op::Div => Value::Number(x/y), Op::Less => Value::Bool(x<y), Op::Greater => Value::Bool(x>y), Op::Equal => Value::Bool(a==b), _ => unreachable!() };
        self.stack.push(out); Ok(())
    }
}

fn main() -> Result<(), String> {
    // 等价于：let total = 0; for value in [1,2,3,4] { total += value }; print(total)
    let code = vec![Op::Const(Value::Number(0.0)), Op::Store("total".into()), Op::Const(Value::List((1..5).map(|x| Value::Number(x as f64)).collect())), Op::IterInit, Op::IterNext(11), Op::Store("value".into()), Op::Load("total".into()), Op::Load("value".into()), Op::Add, Op::Store("total".into()), Op::Jump(4), Op::Load("total".into()), Op::Print(1), Op::Return];
    let mut vm = Vm::default(); vm.run(&code)?; Ok(())
}
