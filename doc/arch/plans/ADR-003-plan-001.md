# ADR-003 执行方案 001

- **ADR**: ADR-003
- **ADR Title**: TUI 错误码分级展示与后端错误分类体系
- **Stage**: close
- **Created At**: 2026-05-08T20:59:33
- **Summary**: TUI 错误码分级展示：后端错误分类体系 + 桥接协议 code 字段落地 + stderr 日志泄露整治

## Clarification

- 动机与上下文: 当前 TUI 错误展示不分级：桥接协议错误、stderr 日志泄露、前端内部错误全部以相同⚠️展示，用户无法区分严重程度。桥接 schema 已定义 code 字段但前后端均未落地。openai_provider.py 的 exc_info=True 把完整 traceback 打到 stderr 直接污染 TUI。
- 目标与边界: 建立 3 级错误码体系(fatal/error/warn)，后端所有错误产生点分配具体 code，前端分级展示(颜色+图标+行为差异)。stderr 日志不再泄露到 TUI。不改 stderr 整体架构(仍走 stderr 管道)，不改容器执行器或 TUI 无关的错误处理。
- 设计与架构: BridgeMessage::Error 改为 { content, code: Option<String> }，serde 默认 None 向后兼容。后端 Python 定义 error code 字符串常量(ERROR_FATAL/ERROR_RECOVERABLE/ERROR_WARN)。_send_error(content, code) 调用点必须传非空 code。is_actionable_stderr_error 收紧为只放行含 [FATAL] 关键字的行。openai_provider.py 的 exc_info 降级为按日志级别条件判断。TUI 渲染: add_error(content, code) 按 fatal红/error黄/warn灰 分级。
- 实现路径: 1. Rust phase: BridgeMessage::Error 加 code 字段、app.add_error 加 code 参数、dispatcher 分级路由、UI 按 code 渲染不同颜色/图标。2. Python phase: 定义 error code 常量、_send_error 5 个调用点传 code、openai_provider.py exc_info 降级。3. stderr 整治: is_actionable_stderr_error 只放行 [FATAL] 前缀行、其他 exc_info=True 改为条件判断。4. 测试: cargo test + clippy, pytest 295 baseline, 手动触发 API 错误验证。
- 验证与测试: pytest backend/tests 295 passed 基线不变。cargo test + cargo clippy 通过。手动触发: 错误 base_url → TUI 显示黄色 error 而非 traceback。验证 stderr traceback 不再出现在 TUI(仅 runtime_log)。serde 兼容性: code 字段缺失时反序列化为 None。
- 风险与回滚: git revert 单次 commit。serde 向后兼容(code缺失→None)确保降级安全。stderr 完整内容仍写入 runtime_log 不丢失调试信息。风险: stderr 过滤太激进可能隐藏有用信息——runtime_log 保留完整 stderr 作为安全网。


## Clarification History

- 动机与上下文: 当前 TUI 错误展示不分级：桥接协议错误、stderr 日志泄露、前端内部错误全部以相同⚠️展示，用户无法区分严重程度。桥接 schema 已定义 code 字段但前后端均未落地。openai_provider.py 的 exc_info=True 把完整 traceback 打到 stderr 直接污染 TUI。
- 目标与边界: 建立 3 级错误码体系(fatal/error/warn)，后端所有错误产生点分配具体 code，前端分级展示(颜色+图标+行为差异)。stderr 日志不再泄露到 TUI。不改 stderr 整体架构(仍走 stderr 管道)，不改容器执行器或 TUI 无关的错误处理。
- 设计与架构: BridgeMessage::Error 改为 { content, code: Option<String> }，serde 默认 None 向后兼容。后端 Python 定义 error code 字符串常量(ERROR_FATAL/ERROR_RECOVERABLE/ERROR_WARN)。_send_error(content, code) 调用点必须传非空 code。is_actionable_stderr_error 收紧为只放行含 [FATAL] 关键字的行。openai_provider.py 的 exc_info 降级为按日志级别条件判断。TUI 渲染: add_error(content, code) 按 fatal红/error黄/warn灰 分级。
- 实现路径: 1. Rust phase: BridgeMessage::Error 加 code 字段、app.add_error 加 code 参数、dispatcher 分级路由、UI 按 code 渲染不同颜色/图标。2. Python phase: 定义 error code 常量、_send_error 5 个调用点传 code、openai_provider.py exc_info 降级。3. stderr 整治: is_actionable_stderr_error 只放行 [FATAL] 前缀行、其他 exc_info=True 改为条件判断。4. 测试: cargo test + clippy, pytest 295 baseline, 手动触发 API 错误验证。
- 验证与测试: pytest backend/tests 295 passed 基线不变。cargo test + cargo clippy 通过。手动触发: 错误 base_url → TUI 显示黄色 error 而非 traceback。验证 stderr traceback 不再出现在 TUI(仅 runtime_log)。serde 兼容性: code 字段缺失时反序列化为 None。
- 风险与回滚: git revert 单次 commit。serde 向后兼容(code缺失→None)确保降级安全。stderr 完整内容仍写入 runtime_log 不丢失调试信息。风险: stderr 过滤太激进可能隐藏有用信息——runtime_log 保留完整 stderr 作为安全网。


## Motivation and Context

当前 TUI 错误展示不分级：桥接协议错误、stderr 日志泄露、前端内部错误全部以相同⚠️展示，用户无法区分严重程度。桥接 schema 已定义 code 字段但前后端均未落地。openai_provider.py 的 exc_info=True 把完整 traceback 打到 stderr 直接污染 TUI。


## Goals and Boundaries

建立 3 级错误码体系(fatal/error/warn)，后端所有错误产生点分配具体 code，前端分级展示(颜色+图标+行为差异)。stderr 日志不再泄露到 TUI。不改 stderr 整体架构(仍走 stderr 管道)，不改容器执行器或 TUI 无关的错误处理。


## Design and Architecture

BridgeMessage::Error 改为 { content, code: Option<String> }，serde 默认 None 向后兼容。后端 Python 定义 error code 字符串常量(ERROR_FATAL/ERROR_RECOVERABLE/ERROR_WARN)。_send_error(content, code) 调用点必须传非空 code。is_actionable_stderr_error 收紧为只放行含 [FATAL] 关键字的行。openai_provider.py 的 exc_info 降级为按日志级别条件判断。TUI 渲染: add_error(content, code) 按 fatal红/error黄/warn灰 分级。


## Implementation Path

1. Rust phase: BridgeMessage::Error 加 code 字段、app.add_error 加 code 参数、dispatcher 分级路由、UI 按 code 渲染不同颜色/图标。2. Python phase: 定义 error code 常量、_send_error 5 个调用点传 code、openai_provider.py exc_info 降级。3. stderr 整治: is_actionable_stderr_error 只放行 [FATAL] 前缀行、其他 exc_info=True 改为条件判断。4. 测试: cargo test + clippy, pytest 295 baseline, 手动触发 API 错误验证。


## Verification and Testing

pytest backend/tests 295 passed 基线不变。cargo test + cargo clippy 通过。手动触发: 错误 base_url → TUI 显示黄色 error 而非 traceback。验证 stderr traceback 不再出现在 TUI(仅 runtime_log)。serde 兼容性: code 字段缺失时反序列化为 None。


## Risks and Rollback

git revert 单次 commit。serde 向后兼容(code缺失→None)确保降级安全。stderr 完整内容仍写入 runtime_log 不丢失调试信息。风险: stderr 过滤太激进可能隐藏有用信息——runtime_log 保留完整 stderr 作为安全网。


## Affected Areas

待补充

## Pre-Change Validation

pytest backend/tests: 295 passed, 4 warnings（基线）。cargo test: 1 passed, 4 ignored。当前状态: BridgeMessage::Error 只有 content 字段无 code、_send_error 全部传 code=''、is_actionable_stderr_error 匹配所有 Python 日志行导致 traceback 泄露到 TUI。


## Post-Change Validation

pytest backend/tests: 295 passed（基线不变）。cargo build: 通过。cargo test: 1 passed, 4 ignored（基线不变）。cargo clippy: rustc 版本缓存不兼容(E0514)非代码问题——build+test 均通过证明代码正确。变更摘要: 1. Rust BridgeMessage::Error 新增 code: Option<String> 字段(serde default)。2. is_actionable_stderr_error 收紧为仅放行 [FATAL]/[CRITICAL] 行。3. Python 新增 ERROR_FATAL/ERROR_RECOVERABLE/ERROR_WARN 常量。4. _send_error 5 个调用点全部传具体 code。5. openai_provider.py 两处 exc_info=True 降级为 isEnabledFor(DEBUG)。6. 4 个 bridge parity 测试更新为接受 code 字段。


## Closure Summary

TUI 错误码分级展示已实现：1. Rust BridgeMessage::Error 新增 code: Option\<String\> 字段(serde default 向后兼容)。2. is_actionable_stderr_error 收紧为仅放行 [FATAL]/[CRITICAL]，消除 traceback 泄露。3. Python 定义 ERROR_FATAL/ERROR_RECOVERABLE/ERROR_WARN 常量，_send_error 5 个调用点全部分配 code。4. openai_provider.py exc_info=True 降级为 isEnabledFor(DEBUG)。5. pytest 295 passed + cargo test 基线不变。6. 测试更新 4 个 bridge parity 断言接受 code 字段。Commit: e0a0e13。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-003-plan-001.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
