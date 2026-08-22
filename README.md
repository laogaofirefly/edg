# EDG

EDG 是面向 Android 应用与 2D/3D 游戏开发的简洁动态语言。

当前版本：0.9 World 游戏世界原型

## 当前目标

- Python 风格缩进代码块
- 动态值
- `let` / `var`
- 函数与 `return`
- `if` / `elif` / `else`
- 算术与比较表达式
- `print()` 内置函数
- 类、实例、属性和方法
- `init` 构造函数与默认参数
- 字典字面量
- `len()` 与 `type()` 标准库函数

## 示例

```edg
let name = "EDG"
let score = 10

fn add(a, b)
    return a + b

if score > 5
    print(name)
    print(add(score, 20))
```

## 运行原型

当前原型使用 Python 实现：

```bash
python3 edg.py examples/hello.edg
```

推荐使用项目根目录下的 `edg.py` 启动器。它会自动配置 `src` 路径，不需要手动设置 `PYTHONPATH`。

运行 World 示例：

```bash
python3 edg.py examples/world_demo.edg
```
