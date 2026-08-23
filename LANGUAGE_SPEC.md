# EDG 语言规范（V1 草案）

EDG 的目标不是“能执行几段脚本”，而是一门具有稳定语法、明确语义、可诊断错误和可测试工具链的通用编程语言。

## 设计原则

1. **语法稳定**：新版本不随意改变已有程序的含义。
2. **错误可定位**：错误必须包含文件、行、列和源代码片段。
3. **运行时可控**：脚本不能默认访问任意 Python 对象或系统能力。
4. **宿主可扩展**：游戏、Android、文件和网络能力通过明确模块提供。
5. **实现可替换**：解释器、字节码 VM 和未来的原生编译器共享同一套 AST/语义规范。

## V1 语言范围

### 基础值

- `number`：整数和浮点数
- `text`：单引号或双引号字符串
- `boolean`：`true`、`false`
- `nothing`：空值
- `list`：列表
- `dict`：字典
- `function`、`class`、`object`

### 声明

```edg
let name = "EDG"
var score = 0
fn add(a, b = 0)
    return a + b
```

V1 中 `let` 和 `var` 都是变量绑定；不可变语义将在 V2 设计，不允许当前实现悄悄改变含义。

### 控制流

```edg
if condition
    pass
elif other
    pass
else
    pass

while condition
    break

for item in values
    continue
```

### 模块

```edg
import math
export add
```

模块以 `.edg` 为单位，从入口文件所在目录和显式标准库路径搜索。模块只执行一次并缓存。

## 保留字

`let var fn return if elif else while for in break continue class init import export true false nothing and or`

## 运算符优先级

从高到低：调用/下标/属性、一元 `+ -`、`* / %`、`+ -`、比较、相等、`and`、`or`、`??`。

## 运行时边界

EDG 程序不能直接导入任意 Python 模块。宿主必须显式注册模块和函数。默认标准库只提供纯数据操作；设备、文件、网络和游戏 API 由宿主权限控制。

## 版本策略

- `0.x`：允许实验性变化。
- `1.0`：冻结核心语法、错误模型和标准库命名。
- 后续版本优先增加能力，不删除已有语义。
