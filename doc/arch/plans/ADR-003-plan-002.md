# ADR-003 执行方案 002

- **ADR**: ADR-003
- **ADR Title**: TUI 错误码分级展示与后端错误分类体系
- **Stage**: close
- **Created At**: 2026-05-08T21:54:05
- **Summary**: 修复 is_actionable_stderr_error 未过滤 exc_info 产生的 traceback 续行

## Clarification

- 动机与上下文: is_actionable_stderr_error 对 Python log 行做时间戳模式过滤，但 exc_info=True 产生的 traceback 是多行输出——第一行 [ERROR] 被正确过滤，续行（Traceback 头、帧行、代码上下文、^^^ 指针）不以时间戳开头，被当作非日志内容放行到 TUI，污染界面。
- 目标与边界: 仅修改 is_actionable_stderr_error 过滤逻辑。不改 Python 日志配置、不改桥接协议、不改 _send_error 调用。
- 设计与架构: 在现有时间戳过滤之后新增两条规则：1. 以空白字符开头的行（traceback 帧行、代码上下文、^^^ 指针）不放行；2. 以 Traceback 开头的行不放行。仍写入 runtime_log，调试信息不丢失。
- 实现路径: 编辑 frontend/src/core/dispatcher.rs 的 is_actionable_stderr_error 函数，在时间戳过滤块之后、末尾 return true 之前插入两条 early-return false。新增 test_is_actionable_stderr_error 测试覆盖 FATAL/CRITICAL 放行、ERROR 过滤、traceback 行过滤、非日志 stderr 放行。
- 验证与测试: cargo test 全部通过（含新增测试）。cargo build 通过。
- 风险与回滚: 删除新增的两条件分支和测试，恢复原函数体。


## Clarification History

- 动机与上下文: is_actionable_stderr_error 对 Python log 行做时间戳模式过滤，但 exc_info=True 产生的 traceback 是多行输出——第一行 [ERROR] 被正确过滤，续行（Traceback 头、帧行、代码上下文、^^^ 指针）不以时间戳开头，被当作非日志内容放行到 TUI，污染界面。
- 目标与边界: 仅修改 is_actionable_stderr_error 过滤逻辑。不改 Python 日志配置、不改桥接协议、不改 _send_error 调用。
- 设计与架构: 在现有时间戳过滤之后新增两条规则：1. 以空白字符开头的行（traceback 帧行、代码上下文、^^^ 指针）不放行；2. 以 Traceback 开头的行不放行。仍写入 runtime_log，调试信息不丢失。
- 实现路径: 编辑 frontend/src/core/dispatcher.rs 的 is_actionable_stderr_error 函数，在时间戳过滤块之后、末尾 return true 之前插入两条 early-return false。新增 test_is_actionable_stderr_error 测试覆盖 FATAL/CRITICAL 放行、ERROR 过滤、traceback 行过滤、非日志 stderr 放行。
- 验证与测试: cargo test 全部通过（含新增测试）。cargo build 通过。
- 风险与回滚: 删除新增的两条件分支和测试，恢复原函数体。


## Motivation and Context

is_actionable_stderr_error 对 Python log 行做时间戳模式过滤，但 exc_info=True 产生的 traceback 是多行输出——第一行 [ERROR] 被正确过滤，续行（Traceback 头、帧行、代码上下文、^^^ 指针）不以时间戳开头，被当作非日志内容放行到 TUI，污染界面。


## Goals and Boundaries

仅修改 is_actionable_stderr_error 过滤逻辑。不改 Python 日志配置、不改桥接协议、不改 _send_error 调用。


## Design and Architecture

在现有时间戳过滤之后新增两条规则：1. 以空白字符开头的行（traceback 帧行、代码上下文、^^^ 指针）不放行；2. 以 Traceback 开头的行不放行。仍写入 runtime_log，调试信息不丢失。


## Implementation Path

编辑 frontend/src/core/dispatcher.rs 的 is_actionable_stderr_error 函数，在时间戳过滤块之后、末尾 return true 之前插入两条 early-return false。新增 test_is_actionable_stderr_error 测试覆盖 FATAL/CRITICAL 放行、ERROR 过滤、traceback 行过滤、非日志 stderr 放行。


## Verification and Testing

cargo test 全部通过（含新增测试）。cargo build 通过。


## Risks and Rollback

删除新增的两条件分支和测试，恢复原函数体。


## Affected Areas

待补充

## Pre-Change Validation

修改前状态：is_actionable_stderr_error 仅基于时间戳模式过滤 Python log 行，非时间戳开头的 stderr 行一律放行。修改后状态：新增两条规则过滤 traceback 续行——以空白字符开头的行和以 Traceback 开头的行。cargo build 通过，cargo test 109 passed 含新增测试。


## Post-Change Validation

cargo build: 通过。cargo test: 109 passed, 0 failed（含新增 test_is_actionable_stderr_error 测试覆盖 11 个断言）。python -m pytest backend/tests: 295 passed（基线不变）。变更摘要：is_actionable_stderr_error 新增两条过滤规则——以空白字符开头的行和以 Traceback 开头的行不放行到 TUI。


## Closure Summary

is_actionable_stderr_error 新增 traceback 续行过滤：以空白字符开头的行和以 Traceback 开头的行不再放行到 TUI。cargo test 109 passed，pytest 295 passed。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-003-plan-002.md


## Risks and Rollback

待补充

## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
