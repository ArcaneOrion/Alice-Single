# ADR-004 执行方案 001

- **ADR**: ADR-004
- **ADR Title**: ChatMessage reasoning_content 兼容：修复 thinking mode 多轮对话消息回传缺失
- **Stage**: close
- **Created At**: 2026-05-18T20:05:42
- **Summary**: ChatMessage 增加 reasoning_content 字段，修复 thinking mode 多轮对话消息回传缺失

## Clarification

- 动机与上下文: GLM thinking mode 要求多轮对话中 assistant 消息回传 reasoning_content 字段。当前代码在提取 thinking 方面完整（StreamChunk/ChatResponse 均能提取 6 种字段名），但在回传时全部丢弃——ChatMessage 无此字段，to_dict() 不输出，from_dict() 不读入。第二轮对话起 GLM API 返回 400。
- 目标与边界: 做：ChatMessage 增加 reasoning_content 字段及序列化/反序列化；ChatService.add_assistant_message() 增加 reasoning_content 参数；ChatWorkflow/ChatService 向 assistant 消息传递 thinking；FunctionCallingOrchestrator 传递 thinking。不做：不改桥接协议；不改 RoundEntry 记忆持久化；不改 OpenAI SDK 调用层；不增加 supports_thinking gate 逻辑。
- 设计与架构: 最小侵入设计：reasoning_content 作为 optional 字段挂到 ChatMessage，只在值为非空字符串时才序列化到 API dict。OpenAI 等模型忽略多余字段无副作用；GLM thinking mode 收到完整 reasoning_content 不再报 400；不需要 capability 分支决定是否发送。
- 实现路径: 1. ChatMessage 增加 reasoning_content: str | None = None，to_dict() 有值时输出，from_dict() 读入；2. ChatMessage.assistant() 增加 reasoning_content 参数；3. ChatService.add_assistant_message() 增加 reasoning_content 参数；4. ChatWorkflow 无工具调用时传递 full_thinking；5. ChatWorkflow 有工具调用时传递 full_thinking 给 orchestrator；6. FunctionCallingOrchestrator 接受并传递 reasoning_content；7. ChatService.chat()/stream_chat() 传递 thinking
- 验证与测试: 修改前：构造包含 thinking 的多轮对话，确认 to_dict() 不含 reasoning_content；修改后：确认 to_dict() 有值时含、无值时不含；from_dict() 往返一致；运行现有 pytest 确认无回归
- 风险与回滚: reasoning_content=None 是默认值，设为 None 时行为与改动前完全一致。如出问题只需清空传入值即可


## Clarification History

- 动机与上下文: GLM thinking mode 要求多轮对话中 assistant 消息回传 reasoning_content 字段。当前代码在提取 thinking 方面完整（StreamChunk/ChatResponse 均能提取 6 种字段名），但在回传时全部丢弃——ChatMessage 无此字段，to_dict() 不输出，from_dict() 不读入。第二轮对话起 GLM API 返回 400。
- 目标与边界: 做：ChatMessage 增加 reasoning_content 字段及序列化/反序列化；ChatService.add_assistant_message() 增加 reasoning_content 参数；ChatWorkflow/ChatService 向 assistant 消息传递 thinking；FunctionCallingOrchestrator 传递 thinking。不做：不改桥接协议；不改 RoundEntry 记忆持久化；不改 OpenAI SDK 调用层；不增加 supports_thinking gate 逻辑。
- 设计与架构: 最小侵入设计：reasoning_content 作为 optional 字段挂到 ChatMessage，只在值为非空字符串时才序列化到 API dict。OpenAI 等模型忽略多余字段无副作用；GLM thinking mode 收到完整 reasoning_content 不再报 400；不需要 capability 分支决定是否发送。
- 实现路径: 1. ChatMessage 增加 reasoning_content: str | None = None，to_dict() 有值时输出，from_dict() 读入；2. ChatMessage.assistant() 增加 reasoning_content 参数；3. ChatService.add_assistant_message() 增加 reasoning_content 参数；4. ChatWorkflow 无工具调用时传递 full_thinking；5. ChatWorkflow 有工具调用时传递 full_thinking 给 orchestrator；6. FunctionCallingOrchestrator 接受并传递 reasoning_content；7. ChatService.chat()/stream_chat() 传递 thinking
- 验证与测试: 修改前：构造包含 thinking 的多轮对话，确认 to_dict() 不含 reasoning_content；修改后：确认 to_dict() 有值时含、无值时不含；from_dict() 往返一致；运行现有 pytest 确认无回归
- 风险与回滚: reasoning_content=None 是默认值，设为 None 时行为与改动前完全一致。如出问题只需清空传入值即可


## Motivation and Context

GLM thinking mode 要求多轮对话中 assistant 消息回传 reasoning_content 字段。当前代码在提取 thinking 方面完整（StreamChunk/ChatResponse 均能提取 6 种字段名），但在回传时全部丢弃——ChatMessage 无此字段，to_dict() 不输出，from_dict() 不读入。第二轮对话起 GLM API 返回 400。


## Goals and Boundaries

做：ChatMessage 增加 reasoning_content 字段及序列化/反序列化；ChatService.add_assistant_message() 增加 reasoning_content 参数；ChatWorkflow/ChatService 向 assistant 消息传递 thinking；FunctionCallingOrchestrator 传递 thinking。不做：不改桥接协议；不改 RoundEntry 记忆持久化；不改 OpenAI SDK 调用层；不增加 supports_thinking gate 逻辑。


## Design and Architecture

最小侵入设计：reasoning_content 作为 optional 字段挂到 ChatMessage，只在值为非空字符串时才序列化到 API dict。OpenAI 等模型忽略多余字段无副作用；GLM thinking mode 收到完整 reasoning_content 不再报 400；不需要 capability 分支决定是否发送。


## Implementation Path

1. ChatMessage 增加 reasoning_content: str | None = None，to_dict() 有值时输出，from_dict() 读入；2. ChatMessage.assistant() 增加 reasoning_content 参数；3. ChatService.add_assistant_message() 增加 reasoning_content 参数；4. ChatWorkflow 无工具调用时传递 full_thinking；5. ChatWorkflow 有工具调用时传递 full_thinking 给 orchestrator；6. FunctionCallingOrchestrator 接受并传递 reasoning_content；7. ChatService.chat()/stream_chat() 传递 thinking


## Verification and Testing

修改前：构造包含 thinking 的多轮对话，确认 to_dict() 不含 reasoning_content；修改后：确认 to_dict() 有值时含、无值时不含；from_dict() 往返一致；运行现有 pytest 确认无回归


## Risks and Rollback

reasoning_content=None 是默认值，设为 None 时行为与改动前完全一致。如出问题只需清空传入值即可


## Affected Areas

待补充

## Pre-Change Validation

Spec-004 已就绪，覆盖数据形状（ChatMessage reasoning_content 字段）、序列化规则、行为规则。变更范围：message.py, chat_service.py, chat_workflow.py, function_calling_orchestrator.py


## Post-Change Validation

修改后验证：308 项测试全部通过（含 13 项新增 reasoning_content 测试）。ChatMessage.to_dict() 有值时含 reasoning_content，无值时不含；from_dict() 往返一致；add_assistant_message() 传递 reasoning_content；多轮对话历史序列化包含 reasoning_content。


## Closure Summary

ChatMessage 增加 reasoning_content 可选字段，修复 thinking mode 多轮对话 400 错误。变更文件：message.py, chat_service.py, chat_workflow.py, function_calling_orchestrator.py。新增测试：test_reasoning_content.py (13 项)。全量 308 项测试通过，0 失败。


## References

- **Commits**: 待从 git 自动采集
- **Plan**: doc/arch/plans/ADR-004-plan-001.md


## Checkpoints

- [ ] 澄清完成
- [ ] 前置验证完成
- [ ] 实施完成
- [ ] 后置验证完成
- [ ] ADR 回填完成
