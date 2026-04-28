# ADR-000 执行方案 001

- **ADR**: ADR-000
- **ADR Title**: 采用 ADR 方法论
- **Stage**: validate
- **Created At**: 2026-04-28T13:20:22
- **Summary**: 前端 TUI 增加文字选择和复制功能

## Clarification

- 动机与上下文: TUI 用户需要选择任意可见区域的文字并复制到系统剪贴板，这是 TUI 的基础交互能力，当前完全缺失。
- 目标与边界: 覆盖聊天历史/思考侧边栏/输入框全部 3 个区域。鼠标左键拖拽选择，Ctrl+C/Ctrl+Shift+C 复制，Ctrl+V 粘贴。退出改 Ctrl+D。不涉及后端 Bridge 协议。
- 设计与架构: 新增 SelectionState 数据结构存储选区坐标和内容。扩展 MouseHandler 处理 Drag 事件（从空操作变为选区计算）。渲染层（chat_view/sidebar）根据 SelectionState 对选中文本加反色高亮。添加 arboard crate 访问系统剪贴板。所有改动在 frontend/ 内完成。
- 实现路径: 1. Cargo.toml 添加 arboard 依赖; 2. 创建 selection.rs 模块定义 SelectionState; 3. 改 keyboard_handler 键盘映射(Ctrl+D退出/Ctrl+C复制/Ctrl+Shift+C复制/Ctrl+V粘贴); 4. 实现 mouse_handler Drag 事件->坐标->文本偏移映射; 5. chat_view + sidebar 渲染时根据选择状态高亮; 6. build+test+clippy 验证
- 验证与测试: cargo build 无错误, cargo test 全部通过, cargo clippy 无 warning, 手动拖拽选择+Ctrl+C复制+Ctrl+V粘贴功能正常
- 风险与回滚: git revert 回滚单次 commit 即可还原所有改动。arboard 编译失败时回退到仅支持 OSC 52 终端剪贴板或暂时跳过剪贴板功能。


## Clarification History

- 动机与上下文: TUI 用户需要选择任意可见区域的文字并复制到系统剪贴板，这是 TUI 的基础交互能力，当前完全缺失。
- 目标与边界: 覆盖聊天历史/思考侧边栏/输入框全部 3 个区域。鼠标左键拖拽选择，Ctrl+C/Ctrl+Shift+C 复制，Ctrl+V 粘贴。退出改 Ctrl+D。不涉及后端 Bridge 协议。
- 设计与架构: 新增 SelectionState 数据结构存储选区坐标和内容。扩展 MouseHandler 处理 Drag 事件（从空操作变为选区计算）。渲染层（chat_view/sidebar）根据 SelectionState 对选中文本加反色高亮。添加 arboard crate 访问系统剪贴板。所有改动在 frontend/ 内完成。
- 实现路径: 1. Cargo.toml 添加 arboard 依赖; 2. 创建 selection.rs 模块定义 SelectionState; 3. 改 keyboard_handler 键盘映射(Ctrl+D退出/Ctrl+C复制/Ctrl+Shift+C复制/Ctrl+V粘贴); 4. 实现 mouse_handler Drag 事件->坐标->文本偏移映射; 5. chat_view + sidebar 渲染时根据选择状态高亮; 6. build+test+clippy 验证
- 验证与测试: cargo build 无错误, cargo test 全部通过, cargo clippy 无 warning, 手动拖拽选择+Ctrl+C复制+Ctrl+V粘贴功能正常
- 风险与回滚: git revert 回滚单次 commit 即可还原所有改动。arboard 编译失败时回退到仅支持 OSC 52 终端剪贴板或暂时跳过剪贴板功能。


## Motivation and Context

TUI 用户需要选择任意可见区域的文字并复制到系统剪贴板，这是 TUI 的基础交互能力，当前完全缺失。


## Goals and Boundaries

覆盖聊天历史/思考侧边栏/输入框全部 3 个区域。鼠标左键拖拽选择，Ctrl+C/Ctrl+Shift+C 复制，Ctrl+V 粘贴。退出改 Ctrl+D。不涉及后端 Bridge 协议。


## Design and Architecture

新增 SelectionState 数据结构存储选区坐标和内容。扩展 MouseHandler 处理 Drag 事件（从空操作变为选区计算）。渲染层（chat_view/sidebar）根据 SelectionState 对选中文本加反色高亮。添加 arboard crate 访问系统剪贴板。所有改动在 frontend/ 内完成。


## Implementation Path

1. Cargo.toml 添加 arboard 依赖; 2. 创建 selection.rs 模块定义 SelectionState; 3. 改 keyboard_handler 键盘映射(Ctrl+D退出/Ctrl+C复制/Ctrl+Shift+C复制/Ctrl+V粘贴); 4. 实现 mouse_handler Drag 事件->坐标->文本偏移映射; 5. chat_view + sidebar 渲染时根据选择状态高亮; 6. build+test+clippy 验证


## Verification and Testing

cargo build 无错误, cargo test 全部通过, cargo clippy 无 warning, 手动拖拽选择+Ctrl+C复制+Ctrl+V粘贴功能正常


## Risks and Rollback

git revert 回滚单次 commit 即可还原所有改动。arboard 编译失败时回退到仅支持 OSC 52 终端剪贴板或暂时跳过剪贴板功能。


## Affected Areas

待补充

## Pre-Change Validation

cargo test: 1 passed, 0 failed, 4 ignored | cargo clippy: 0 errors, 0 warnings (PATH排除Nix rustc)


## Post-Change Validation

cargo test: 101 passed (100 lib + 1 doctest) | cargo clippy: 0 errors 0 warnings | cargo fmt: clean


## Closure Summary

待补充

## References

- **Commits**: 待补充
- **Plan**: 待补充

## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
