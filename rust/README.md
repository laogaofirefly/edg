# EDG Rust VM

EDG 的 Rust 虚拟机原型。当前与 Python 原型并行存在，尚未替换 Python 编译器。

## 结构

```text
Value   动态值
Op      类型安全字节码
Vm      栈式虚拟机
```

## 当前支持

- 数字、布尔值、文本、列表
- 常量与变量
- 加减乘除
- 比较运算
- 条件跳转
- 列表迭代
- `print`
- `return`

## 运行

需要安装 Rust：

```bash
cd rust
cargo run --release
```

当前内置测试程序等价于：

```edg
let total = 0
for value in [1, 2, 3, 4]
    total += value
print(total)
```

预期输出：

```text
10
```
