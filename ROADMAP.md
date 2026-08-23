# EDG 走向真正编程语言的路线图

## 阶段 1：语言基础冻结

- [x] 词法分析、表达式解析、缩进代码块
- [ ] Native 函数、类、模块和运行时对象模型
- [x] 基础容器和标准函数
- [ ] 将解析器与 Native IR 统一
- [ ] 补齐 `pass`、`else`、`break`、`continue` 的边界行为
- [ ] 明确变量作用域和赋值规则

## 阶段 2：编译器质量

- [ ] Token 保存文件、行、列、长度
- [ ] 统一的 `SyntaxError`、`NameError`、`TypeError`、`RuntimeError`
- [ ] 错误显示源代码行和 `^` 指针
- [ ] AST pretty printer 和字节码反汇编器
- [ ] 端到端回归测试

## 阶段 3：真正的标准库

- [ ] `std.text`、`std.collections`、`std.math`
- [ ] JSON 编解码
- [ ] 文件 API（权限控制）
- [ ] 时间和随机数 API
- [ ] 包清单和模块搜索路径

## 阶段 4：工具链

- [ ] `edg run file.edg`
- [ ] `edg repl`
- [ ] `edg check file.edg`
- [ ] `edg format file.edg`
- [ ] `edg test`
- [ ] VS Code / LSP 基础支持

## 阶段 5：性能和发布
- [x] 实验性 C Native 后端基础值运行时
- [x] Native 字符串、数组、函数和短路逻辑
- [x] Native 生命周期管理与回归测试
- [ ] Native 闭包、外部变量捕获和完整作用域
- [ ] Native 字典、类、模块和异常支持
- [ ] 优化 Native 运行时与 C 代码生成
- [ ] Rust 高性能模块与 Native 运行时协作
- [ ] 可选打包为单文件程序
- [ ] 沙箱、权限和资源限制
- [ ] 发布 EDG 1.0 语言规范