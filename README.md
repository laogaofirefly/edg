# EDG

EDG（Embedded Dynamic Game language）是一门面向 Android 应用、2D/3D 游戏逻辑和嵌入式脚本场景的动态语言原型。

它的目标是：用简洁的缩进语法描述游戏对象、规则和流程，再由宿主应用提供渲染、输入、音频、网络和设备能力。

> 当前项目仍处于原型阶段。Python 字节码编译器和虚拟机是主要运行时，Rust 部分提供独立的 VM/高性能计算原型，尚未完全替换 Python 运行时。

## 目录

- [特性概览](#特性概览)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [语法](#语法)
- [数据类型](#数据类型)
- [运算符](#运算符)
- [函数](#函数)
- [控制流](#控制流)
- [类与对象](#类与对象)
- [列表与字典](#列表与字典)
- [模块与导出](#模块与导出)
- [游戏世界 API](#游戏世界-api)
- [高性能计算 API](#高性能计算-api)
- [错误处理与限制](#错误处理与限制)
- [Rust 原型](#rust-原型)
- [开发与测试](#开发与测试)
- [路线图](#路线图)

## 特性概览

当前 Python 运行时支持：

- 空格缩进代码块，不使用大括号
- `let` / `var` 变量声明
- 数字、字符串、布尔值、`nothing`
- 列表和字典字面量
- 函数、闭包式环境和 `return`
- 默认参数
- `if` / `elif` / `else`
- `while` / `for ... in`
- `break` / `continue`
- 算术、比较、逻辑和空值合并运算
- 属性访问、可选属性访问和下标访问
- 类、实例、字段、方法和 `init` 构造函数
- `.edg` 模块导入和 `export`
- `print`、`len`、`range`、`type` 内置函数
- `world` 游戏世界模块
- Rust 加速的批量移动、范围检测和空间查询（如果动态库存在）

## 快速开始

### 环境要求

- Python 3.10 或更高版本
- 可选：Rust/Cargo，用于构建 Rust 原型和加速动态库

### 运行示例

在仓库根目录执行：

```bash
python3 edg.py examples/hello.edg
python3 edg.py examples/try_now.edg
python3 edg.py examples/world_demo.edg
```

Windows 可使用：

```powershell
py edg.py examples/hello.edg
```

根目录 `edg.py` 会自动把 `src` 加入 Python 模块搜索路径，因此不需要手动设置 `PYTHONPATH`。

### 第一个程序

创建 `hello.edg`：

```edg
let name = "EDG"
let score = 10

fn add(a, b)
    return a + b

if score > 5
    print(name)
    print(add(score, 20))
```

运行：

```bash
python3 edg.py hello.edg
```

输出：

```text
EDG
30
```

## 项目结构

```text
edg/
├── edg.py                 # 推荐启动器
├── README.md              # 项目文档
├── .gitignore
├── examples/              # EDG 示例程序
├── src/
│   ├── edg02.py           # 词法分析、Pratt 表达式解析和早期解释器
│   ├── edg03.py           # 当前字节码编译器和 Python VM
│   ├── edg_hot.py         # Rust 动态库桥接与 Python 回退实现
│   ├── spatial.py         # 空间查询
│   └── world.py           # 游戏世界和实体模型
└── rust/
    ├── Cargo.toml
    ├── README.md
    └── src/                # Rust VM、空间算法和 FFI 实现
```

`edg03.py` 是当前启动器使用的主要运行时；`edg02.py` 主要作为解析和求值组件被复用，不建议直接作为应用入口。

## 语法

### 注释与缩进

使用 `#` 开始单行注释。代码块必须使用空格缩进，不能使用 Tab：

```edg
# 这是注释
if true
    print("缩进块")
```

同一代码块的缩进应保持一致。空行会被忽略。

### 变量

```edg
let name = "player"
var hp = 100
hp -= 10
hp += 5
hp *= 2
hp /= 5
```

`let` 和 `var` 当前都表示普通变量绑定，暂未实现不可变变量语义。

### 常量值

```edg
let integer = 42
let decimal = 3.14
let text = 'hello'
let enabled = true
let disabled = false
let empty = nothing
```

字符串支持单引号和双引号，并支持常见转义。

## 数据类型

| 类型 | 示例 | 说明 |
|---|---|---|
| number | `10`, `2.5` | Python `int` 或 `float` |
| text | `"hello"` | 字符串 |
| boolean | `true`, `false` | 布尔值 |
| nothing | `nothing` | 空值，对应 Python `None` |
| list | `[1, 2, 3]` | 有序可迭代容器 |
| dict | `{ "hp": 100 }` | 键值容器 |
| object | `Player()` | 类实例或宿主对象 |

## 运算符

优先级从高到低：

| 运算符 | 作用 |
|---|---|
| `()` | 分组、函数调用 |
| `[]` | 下标访问 |
| `.`, `?.` | 属性访问、空安全属性访问 |
| 一元 `+`, `-` | 正负号 |
| `*`, `/`, `%` | 乘除模 |
| `+`, `-` | 加减 |
| `<`, `>`, `<=`, `>=` | 比较 |
| `==`, `!=` | 相等比较 |
| `and` | 逻辑与，短路 |
| `or` | 逻辑或，短路 |
| `??` | 空值合并 |

示例：

```edg
let total = 2 + 3 * 4
let ok = total >= 10 and total < 20
let name = nothing ?? "unknown"
```

`?.` 只在左侧为 `nothing` 时返回 `nothing`，普通 `.` 访问空值会报错：

```edg
let player = nothing
print(player?.name)
```

## 函数

```edg
fn greet(name)
    return "hello " + name

print(greet("player"))
```

支持默认参数：

```edg
fn damage(value = 10)
    return value * 2

print(damage())
print(damage(5))
```

函数可以访问声明时所在环境中的变量。当前不支持命名参数、可变参数和异常捕获语法。

## 控制流

### 条件

```edg
if hp <= 0
    print("dead")
elif hp < 30
    print("danger")
else
    print("alive")
```

### while、break、continue

```edg
let i = 0
while i < 10
    i += 1
    if i == 3
        continue
    if i == 8
        break
    print(i)
```

### for

```edg
let total = 0
for value in [1, 2, 3, 4]
    total += value
print(total)
```

`for` 当前遍历列表、字符串和其他可迭代宿主对象。可以使用 `range`：

```edg
for i in range(5)
    print(i)
```

## 列表与字典

### 列表

```edg
let values = [10, 20, 30]
print(values[1])
values[1] = 25
values[1] += 5
```

列表下标从 `0` 开始。

### 字典

```edg
let player = {
    "name": "hero",
    "hp": 100
}

print(player["hp"])
player["hp"] -= 25
player["name"] = "player"
print(player.hp)
```

字典键可以是表达式，但应使用可哈希值。属性形式 `player.hp` 等价于读取字典键 `"hp"`。

## 类与对象

```edg
class Player
    var health = 100

    fn damage(value)
        self.health -= value

let player = Player()
player.damage(10)
print(player.health)
```

构造函数使用 `init`：

```edg
class Enemy
    fn init(name, hp)
        self.name = name
        self.hp = hp

let enemy = Enemy("slime", 30)
print(enemy.name)
```

类字段定义的默认值会复制到实例初始字段中。方法调用时，`self` 会由运行时自动传入。

## 模块与导出

### 导入 `.edg` 模块

模块文件需要位于当前工作目录，文件名为 `模块名.edg`：

```edg
# math.edg
fn add(a, b)
    return a + b

export add
```

调用方：

```edg
import math
print(math.add(20, 22))
```

### 宿主模块

运行时目前内置桥接：`world`、预留的 `game`，以及可选的 `hot` 加速模块。

## 游戏世界 API

```edg
import world

let game = world.World()
let hero = world.body("hero", 0, 0, 2, 0)
let enemy = world.body("enemy", 1, 0, 0, 0)
game.add(hero)
game.add(enemy)

game.tick(0.5)
print(hero.x)
print(game.size())
print(len(game.hit_box(0, 0, 2, 2)))
print(len(game.collisions()))
```

`world.body(name, x, y, vx, vy, size)` 创建实体。实体包含 `name`、`x`、`y`、`vx`、`vy`、`size` 字段。

`World` 方法：

| 方法 | 说明 |
|---|---|
| `add(item)` | 添加实体并返回实体 |
| `remove(item)` | 移除实体并返回实体 |
| `size()` | 实体数量 |
| `tick(dt)` | 按速度更新位置并返回世界时间 |
| `nearby(radius, cell_size)` | 统计半径内实体对数量 |
| `hit_box(min_x, min_y, max_x, max_y)` | 返回矩形内实体列表 |
| `collisions()` | 返回 AABB 碰撞实体对 |
| `positions()` | 返回所有坐标列表 |
| `clear()` | 清空实体 |

## 高性能计算 API

`hot` 模块由 `src/edg_hot.py` 提供。存在 Rust 动态库时使用 Rust，否则自动使用 Python 回退实现。

```edg
let xs = [0, 1, 2, 10]
let ys = [0, 1, 2, 10]
print(hot.sum_f64(xs))
print(hot.dot_f64(xs, ys))
print(hot.dist(0, 0, 3, 4))
print(hot.in_circle(xs, ys, 0, 0, 3))
print(hot.hit_box(xs, ys, 0, 0, 2, 2))
```

主要函数：`sum_f64` 求和、`dot_f64` 点积、`dist` 平方距离、`in_circle` 统计圆内点数、`move` 批量移动、`hit_box` 返回 0/1 标记列表。

## 错误处理与限制

错误通常显示为：

```text
EDG error: name 'x' is not defined
```

常见问题包括 Tab 缩进、变量未定义、参数数量错误、空值属性访问、下标越界、字典键不存在和模块文件找不到。

当前限制：没有完整静态类型系统、异常捕获语法、异步/协程、标准包管理器；模块搜索路径主要依赖当前工作目录；`let` 尚未实现真正不可变语义；Rust VM 尚未成为默认运行时；Android 图形、输入、音频和网络 API 仍需宿主层接入。

## Rust 原型

```bash
cd rust
cargo run --release
```

Rust 示例等价于遍历 `[1, 2, 3, 4]` 并输出 `10`。Rust 构建产物不应提交到 Git，`.gitignore` 已忽略 `rust/target/` 和常见动态库文件。

## 开发与测试

```bash
python3 -m py_compile edg.py src/edg02.py src/edg03.py src/edg_hot.py src/spatial.py src/world.py
python3 edg.py examples/try_now.edg
python3 edg.py examples/dict_assign.edg
python3 edg.py examples/world_demo.edg
python3 edg.py examples/hot_demo.edg
```

新增功能时，建议同时增加一个最小 `examples/*.edg` 示例，并验证 Python 回退路径和 Rust 加速路径。

## 版本控制

```bash
git clone https://github.com/laogaofirefly/edg.git
cd edg
python3 edg.py examples/hello.edg
git diff --check
```

不要提交 `__pycache__/`、`rust/target/`、编译动态库、私钥、Token 或 `.env` 文件。

## 路线图

1. 完善词法和语法错误位置提示
2. 统一 `edg02` 与 `edg03` 的解析接口
3. 增加字符串、列表方法和标准库
4. 增加模块搜索路径和缓存管理
5. 补充单元测试、集成测试和基准测试
6. 接入 Android 输入、绘制、音频和资源系统
7. 将 Rust VM 与 Python 编译器逐步打通
8. 增加沙箱、权限控制和脚本热更新
9. 提供实体组件系统和事件系统

## 许可证

当前仓库尚未声明正式开源许可证。计划公开分发时，请补充 `LICENSE` 文件并明确代码、示例和第三方依赖的授权范围。

## 项目地址

https://github.com/laogaofirefly/edg