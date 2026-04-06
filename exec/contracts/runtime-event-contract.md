# Runtime Event / Bridge Canonical Contract Spec

> 范围：本文件基于当前代码的**实际行为**提炼 runtime event、bridge protocol、legacy compatibility 的 canonical contract；不是未来目标态设计稿。默认输出链路是 `cli/main.py -> agent -> chat_workflow -> response_to_dict() -> legacy_compatibility_serializer.py`，旧 `bridge/server.py` 路径仍存在但已不是默认主链。证据：`docs/protocols/bridge.md:7-18`，`backend/alice/cli/main.py:183-212`，`backend/alice/cli/main.py:280-301`，`backend/alice/application/dto/responses.py:281-288`。

## 1. RuntimeEventType 最小稳定字段清单

### 1.1 枚举总表

`RuntimeEventType` 与 `CanonicalEventType` 当前一一同名重复定义，值完全平行，这说明“内部 canonical event”还没有单一 source of truth。证据：`backend/alice/application/dto/responses.py:41-55`，`backend/alice/infrastructure/bridge/canonical_bridge.py:22-35`。

| event_type | 建议标签 | 当前语义 | legacy 投影 | 结论 | 证据 |
|---|---|---|---|---|---|
| `status_changed` | 核心稳定 | 表示 runtime 状态切换，当前主要用于进入 `thinking` | 投影为 legacy `status` | 应保留为核心状态事件 | `backend/alice/application/dto/responses.py:44-55`，`backend/alice/application/workflow/chat_workflow.py:344-355`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:125-128` |
| `reasoning_delta` | 核心稳定 | 推理/思考增量 | 投影为 legacy `thinking` | 应保留为核心流式事件 | `backend/alice/application/dto/responses.py:45`，`backend/alice/domain/llm/services/stream_service.py:772-777`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:128-130` |
| `content_delta` | 核心稳定 | 正文增量 | 投影为 legacy `content` | 应保留为核心流式事件 | `backend/alice/application/dto/responses.py:46`，`backend/alice/domain/llm/services/stream_service.py:765-770`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:130-132` |
| `tool_call_started` | 内部增强 + 部分 legacy 兼容 | 工具调用首次可见 | 仅投影为 legacy `status: executing_tool`，工具细节丢失 | 内部有价值，但对外只保留“正在执行工具” | `backend/alice/application/dto/responses.py:47`，`backend/alice/domain/llm/services/stream_service.py:743-755`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:139-140` |
| `tool_call_argument_delta` | 候选收敛/候选废弃 | 工具参数流式增量 | 不投影，直接被丢弃 | 若未来不做结构化工具轨迹前端消费，可并入其他事件 | `backend/alice/application/dto/responses.py:48`，`backend/alice/domain/llm/services/stream_service.py:756-763`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166` |
| `tool_call_completed` | 候选收敛/候选废弃 | 工具调用参数聚合完成 | 不投影，直接被丢弃 | 若只维护 legacy 前端，可与 `tool_call_started`/`message_completed` 收敛 | `backend/alice/application/dto/responses.py:49`，`backend/alice/domain/llm/services/stream_service.py:795-803`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166` |
| `tool_result` | 内部增强 | 工具执行结果 | 不投影，直接被丢弃 | 对 runtime 审计仍有价值，不建议立即删除 | `backend/alice/application/dto/responses.py:50`，`backend/alice/application/workflow/chat_workflow.py:720-747`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166` |
| `usage_updated` | 核心稳定 | token 使用量更新 | 投影为 legacy `tokens` | 应保留为核心计量事件 | `backend/alice/application/dto/responses.py:51`，`backend/alice/domain/llm/services/stream_service.py:730-741`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:132-138` |
| `message_completed` | 核心稳定 | 一轮模型消息完成，带最终汇总 | 投影为 legacy `status: done` | 应保留为一轮输出完成的终结事件 | `backend/alice/application/dto/responses.py:52`，`backend/alice/domain/llm/services/stream_service.py:816-824`，`backend/alice/application/workflow/chat_workflow.py:630-646`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:141-142` |
| `error_raised` | 核心稳定 | 结构化错误上报 | 投影为 legacy `error` | 应保留为错误主路径 | `backend/alice/application/dto/responses.py:53`，`backend/alice/application/workflow/chat_workflow.py:214-260`，`backend/alice/application/workflow/chat_workflow.py:422-432`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:143-147` |
| `interrupt_ack` | 核心稳定（但 legacy 被压扁） | 中断确认 | 投影为 legacy `status: done` | 内部必须保留；对外语义当前被折叠 | `backend/alice/application/dto/responses.py:54`，`backend/alice/domain/llm/services/stream_service.py:715-718`，`backend/alice/application/workflow/chat_workflow.py:517-540`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:148-149` |

### 1.2 最小稳定 contract

基于当前生产者、消费者与 serializer 映射，最小稳定 runtime contract 可收敛为：

- 必须稳定：`status_changed`、`reasoning_delta`、`content_delta`、`usage_updated`、`message_completed`、`error_raised`、`interrupt_ack`。这些事件要么直接驱动内部状态机，要么直接投影到 legacy wire。证据：`backend/alice/application/workflow/chat_workflow.py:344-355`，`backend/alice/application/workflow/chat_workflow.py:452-495`，`backend/alice/application/workflow/chat_workflow.py:517-540`，`backend/alice/application/workflow/chat_workflow.py:630-646`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:121-149`。
- 暂不应承诺为外部稳定：`tool_call_argument_delta`、`tool_call_completed`、`tool_result`。当前 legacy wire 完全不可见；它们的消费面局限在 workflow 内部聚合/审计层。证据：`backend/alice/application/workflow/chat_workflow.py:497-515`，`backend/alice/application/workflow/chat_workflow.py:720-747`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166`。

## 2. StructuredRuntimeOutput payload 形状

### 2.1 RuntimeEventResponse 顶层 envelope

`RuntimeEventResponse` 顶层字段为：

| 字段 | 类型 | 类型层必填 | 实际主链必填 | 语义 | 证据 |
|---|---|---|---|---|---|
| `response_type` | `ResponseType` | 是 | 是 | 固定为 `runtime_event` | `backend/alice/application/dto/responses.py:206-214` |
| `event_type` | `RuntimeEventType` | 是 | 是 | 事件种类 | `backend/alice/application/dto/responses.py:210-212` |
| `payload` | `dict[str, Any]` | 是 | 是 | 该事件的最小语义载荷 | `backend/alice/application/dto/responses.py:212` |
| `runtime_output` | `StructuredRuntimeOutput | None` | 否 | **当前 ChatWorkflow 总是填写** | 事件触发时的聚合快照 | `backend/alice/application/dto/responses.py:213`，`backend/alice/application/workflow/chat_workflow.py:188-212` |

### 2.2 StructuredRuntimeOutput 结构

| 字段 | 类型 | 必填性 | 语义 | 证据 |
|---|---|---|---|---|
| `message_id` | `str` | 主链必填 | 当前迭代消息 ID，格式 `{request_id}.iter{n}` | `backend/alice/application/dto/responses.py:101-120`，`backend/alice/application/workflow/chat_workflow.py:159-187` |
| `status` | `str` | 主链必填 | 该事件发生时的内部状态快照，不等于 legacy status | `backend/alice/application/dto/responses.py:102-120`，`backend/alice/application/workflow/chat_workflow.py:177-185` |
| `reasoning` | `str` | 主链必填 | 到当前事件为止的思考全文快照 | `backend/alice/application/dto/responses.py:103-120`，`backend/alice/application/workflow/chat_workflow.py:468-479` |
| `content` | `str` | 主链必填 | 到当前事件为止的正文全文快照 | `backend/alice/application/dto/responses.py:104-120`，`backend/alice/application/workflow/chat_workflow.py:482-495` |
| `tool_calls` | `list[StructuredToolCall]` | 主链必填 | 已归一化的工具调用聚合快照 | `backend/alice/application/dto/responses.py:105-120`，`backend/alice/application/workflow/chat_workflow.py:147-157` |
| `tool_results` | `list[StructuredToolResult]` | 主链必填 | 已执行完成的工具结果快照 | `backend/alice/application/dto/responses.py:106-120`，`backend/alice/application/workflow/chat_workflow.py:720-747` |
| `usage` | `dict[str, Any]` | 主链必填 | 当前累计 token 使用量 | `backend/alice/application/dto/responses.py:107-120`，`backend/alice/application/workflow/chat_workflow.py:452-465` |
| `metadata` | `dict[str, Any]` | 主链必填 | 运行时链路元数据：`iteration/trace_id/request_id/task_id/session_id/span_id` | `backend/alice/application/dto/responses.py:108-120`，`backend/alice/application/workflow/chat_workflow.py:169-186` |

### 2.3 每种 event_type 的 payload 形状

#### `status_changed`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `status` | `str` | 是 | 当前状态值；当前 workflow 只显式发出 `thinking` | `backend/alice/application/workflow/chat_workflow.py:344-355` |

#### `reasoning_delta`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `content` | `str` | 是 | 新增思考文本增量 | `backend/alice/domain/llm/services/stream_service.py:772-777`，`backend/alice/application/workflow/chat_workflow.py:467-480` |

#### `content_delta`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `content` | `str` | 是 | 新增正文文本增量 | `backend/alice/domain/llm/services/stream_service.py:765-770`，`backend/alice/application/workflow/chat_workflow.py:482-495` |

#### `tool_call_started`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `id` | `str` | 结构上有，值可为空 | tool call ID | `backend/alice/domain/llm/models/response.py:42-85`，`backend/alice/domain/llm/services/stream_service.py:750-755` |
| `type` | `str` | 结构上有 | 当前默认为 `function` | `backend/alice/domain/llm/models/response.py:45-50`，`backend/alice/domain/llm/models/response.py:77-85` |
| `index` | `int` | 是 | 同轮内 tool call 序号 | `backend/alice/domain/llm/models/response.py:45-50`，`backend/alice/domain/llm/models/response.py:77-85` |
| `function.name` | `str` | 结构上有，值可为空 | 工具名 | `backend/alice/domain/llm/models/response.py:55-85` |
| `function.arguments` | `str` | 结构上有，值可为空 | 当前已聚合到此刻的参数字符串 | `backend/alice/domain/llm/models/response.py:62-85` |

#### `tool_call_argument_delta`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `id`/`type`/`index`/`function.name`/`function.arguments` | 同上 | 结构上有 | 当前累计聚合态 | `backend/alice/domain/llm/services/stream_service.py:756-763`，`backend/alice/domain/llm/models/response.py:42-85` |
| `delta` | `str` | 是 | 本次新增参数片段 | `backend/alice/domain/llm/services/stream_service.py:756-763` |

#### `tool_call_completed`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `id` | `str` | 是 | 最终 tool call ID | `backend/alice/domain/llm/services/stream_service.py:795-803`，`backend/alice/domain/llm/models/response.py:77-85` |
| `type` | `str` | 是 | 工具调用类型 | 同上 |
| `index` | `int` | 是 | 工具调用序号 | 同上 |
| `function.name` | `str` | 是 | 最终工具名 | 同上 |
| `function.arguments` | `str` | 是 | 最终完整参数字符串 | 同上 |

#### `tool_result`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `tool_call_id` | `str` | 是 | 与 tool_call 对应的 ID；无 ID 时回退 `tool-call-{index}` | `backend/alice/application/workflow/chat_workflow.py:720-727` |
| `tool_type` | `str` | 是 | 工具类型 | `backend/alice/application/workflow/chat_workflow.py:721-727` |
| `content` | `str` | 是 | tool message content | `backend/alice/application/workflow/chat_workflow.py:721-727` |
| `status` | `str` | 是 | 执行结果状态 | `backend/alice/application/workflow/chat_workflow.py:721-727` |
| `metadata` | `dict[str, Any]` | 是（可空） | 执行元数据 | `backend/alice/application/workflow/chat_workflow.py:721-727` |

#### `usage_updated`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `usage.prompt_tokens` | `int` | 是 | 输入 token 数 | `backend/alice/domain/llm/services/stream_service.py:732-740` |
| `usage.completion_tokens` | `int` | 是 | 输出 token 数 | 同上 |
| `usage.total_tokens` | `int` | 是 | 总 token 数 | 同上 |

#### `message_completed`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `content` | `str` | 是 | 本轮最终正文 | `backend/alice/domain/llm/services/stream_service.py:816-824` |
| `reasoning` | `str` | 是 | 本轮最终思考 | 同上 |
| `usage` | `dict[str, Any]` | 是 | 本轮最终 usage | 同上 |
| `tool_calls` | `list[dict]` | 是 | 本轮最终工具调用列表，使用嵌套 `function` 形状 | `backend/alice/domain/llm/services/stream_service.py:816-824`，`backend/alice/domain/llm/models/response.py:77-85` |

#### `error_raised`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| `content` | `str` | 当前实现中是 | 错误说明 | `backend/alice/application/workflow/chat_workflow.py:214-260`，`backend/alice/application/workflow/chat_workflow.py:422-432`，`backend/alice/application/workflow/chat_workflow.py:703-714`，`backend/alice/application/workflow/chat_workflow.py:797-807` |
| `code` | `str` | 当前实现中是 | 错误码 | 同上 |

#### `interrupt_ack`

| 字段 | 类型 | 必填 | 语义 | 证据 |
|---|---|---|---|---|
| 无 | `payload={}` | 是 | 中断确认，语义由 `event_type` 与 `runtime_output.status=interrupted` 承担 | `backend/alice/domain/llm/services/stream_service.py:715-718`，`backend/alice/application/workflow/chat_workflow.py:517-540` |

### 2.4 结构不一致点

当前 `tool_call` 在 `payload` 与 `runtime_output.tool_calls` 之间**不是同一种 shape**：

- delta / completion / message_completed payload 使用嵌套结构：`function: {name, arguments}`。证据：`backend/alice/domain/llm/models/response.py:42-85`，`backend/alice/domain/llm/services/stream_service.py:752-763`，`backend/alice/domain/llm/services/stream_service.py:816-824`。
- `StructuredToolCall` / `StructuredRuntimeOutput.tool_calls` 使用拍平结构：`function_name`、`function_arguments`。证据：`backend/alice/application/dto/responses.py:57-75`，`backend/alice/application/workflow/chat_workflow.py:147-157`。

## 3. Interrupt / Status / Error 语义定义

### 3.1 interrupt：触发来源、传播路径、最终处理点

#### 默认主链（`cli/main.py`）

1. 前端/输入侧把 `__INTERRUPT__` 放进 stdin 队列；该信号常量定义在 bridge protocol。证据：`backend/alice/infrastructure/bridge/protocol/messages.py:101-102`，`docs/protocols/bridge.md:130-134`。
2. `TUIBridge._process_user_input()` 在处理前与处理中都会 drain `input_queue`；发现 `INTERRUPT_SIGNAL` 后调用 `agent.interrupt()`，并立刻发送 legacy `status: done`。证据：`backend/alice/cli/main.py:248-275`。
3. `agent.interrupt()` 会把 `_interrupted=True`、`_active_workflow_context.interrupted=True`，再向 workflow cleanup 与 execution_service 传播。证据：`backend/alice/application/agent/agent.py:313-354`。
4. `ChatWorkflow` 把 `should_stop=lambda: context.interrupted` 传给 `stream_service.stream_runtime()`；stream service 每个 chunk 前检查该标志，命中则产出 `interrupt_ack` 并 return。证据：`backend/alice/application/workflow/chat_workflow.py:441-446`，`backend/alice/domain/llm/services/stream_service.py:715-718`。
5. `ChatWorkflow` 收到 `interrupt_ack` 后再发一个 `RuntimeEventResponse(event_type=INTERRUPT_ACK, status=interrupted)` 并结束。证据：`backend/alice/application/workflow/chat_workflow.py:517-540`。
6. 但默认 legacy wire 上，这个内部 `interrupt_ack` 最终仍会被 serializer 投影成 `status: done`，因此前端看不到单独的 `interrupted` 顶层状态。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:148-149`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:108-118`。

#### 旧 bridge 路径（`message_handler.py` / `interrupt_handler.py`）

1. `InterruptHandler.check_interrupt()` 调用 transport 的 `drain_pending_interrupts()`。证据：`backend/alice/infrastructure/bridge/event_handlers/interrupt_handler.py:53-67`。
2. 命中后同样调用 `agent.interrupt()`，然后直接发送 legacy `status: done`。证据：`backend/alice/infrastructure/bridge/event_handlers/interrupt_handler.py:81-87`。
3. `MessageHandler.handle_input()` 每转发一条 response 前都会检查一次 interrupt；若发现中断就停止继续转发。证据：`backend/alice/infrastructure/bridge/event_handlers/message_handler.py:110-135`。

#### 结论

- interrupt 的**内部终点**是 `RuntimeEventType.INTERRUPT_ACK` + `runtime_output.status=interrupted`。证据：`backend/alice/application/workflow/chat_workflow.py:367-377`，`backend/alice/application/workflow/chat_workflow.py:529-539`，`backend/alice/application/workflow/chat_workflow.py:760-770`。
- interrupt 的**legacy 终点**是 `status: done`，不是单独的 `interrupt` 输出消息。证据：`backend/alice/cli/main.py:258-260`，`backend/alice/cli/main.py:268-270`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:148-149`。

### 3.2 status：状态机与合法状态转换

#### 内部状态枚举

应用层 `StatusType` 定义为：`ready / thinking / streaming / executing_tool / done / error / interrupted`。证据：`backend/alice/application/dto/responses.py:29-39`。

#### workflow 内部状态机

| 当前状态 | 下一状态 | 触发点 | 证据 |
|---|---|---|---|
| `ready` | `thinking` | Agent 开始处理请求；ChatWorkflow 首个 runtime event 也是 `status_changed(thinking)` | `backend/alice/application/agent/agent.py:157-159`，`backend/alice/application/workflow/chat_workflow.py:344-355` |
| `thinking` | `streaming` | 收到 `usage_updated` / `reasoning_delta` / `content_delta` 时，runtime_output.status 设为 `streaming` | `backend/alice/application/workflow/chat_workflow.py:452-495` |
| `streaming` | `executing_tool` | 收到 `tool_call_started` / `tool_call_argument_delta` / `tool_call_completed` 时，runtime_output.status 设为 `executing_tool` | `backend/alice/application/workflow/chat_workflow.py:497-515` |
| `executing_tool` | `executing_tool` | 发送 `tool_result` 时仍保持 `executing_tool` | `backend/alice/application/workflow/chat_workflow.py:737-747` |
| `executing_tool` | `thinking` | 下一轮迭代开始时重新发 `status_changed(thinking)` | `backend/alice/application/workflow/chat_workflow.py:326-355`，`backend/alice/application/workflow/chat_workflow.py:773-786` |
| `streaming` / `thinking` | `done` | 无工具时发 `message_completed` | `backend/alice/application/workflow/chat_workflow.py:615-646` |
| 任意处理中状态 | `error` | workflow 依赖缺失、chat error、tool error、max iteration | `backend/alice/application/workflow/chat_workflow.py:214-260`，`backend/alice/application/workflow/chat_workflow.py:404-433`，`backend/alice/application/workflow/chat_workflow.py:648-714`，`backend/alice/application/workflow/chat_workflow.py:787-807` |
| 任意处理中状态 | `interrupted` | `context.interrupted` 或 stream 返回 `interrupt_ack` | `backend/alice/application/workflow/chat_workflow.py:356-378`，`backend/alice/application/workflow/chat_workflow.py:517-540`，`backend/alice/application/workflow/chat_workflow.py:749-771` |

#### legacy status 归一化

legacy status 不是内部状态机的镜像，而是压缩视图：

- `thinking` / `streaming` -> legacy `thinking`
- `executing_tool` -> legacy `executing_tool`
- `ready` -> legacy `ready`
- `done` / `interrupted` / `error` -> legacy `done`

证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:108-118`。

#### 额外的状态重复定义

- bridge protocol 自己还定义了一套较旧的 `StatusType = ready/thinking/executing_tool/done`，不含 `streaming/error/interrupted`。证据：`backend/alice/infrastructure/bridge/protocol/messages.py:25-31`。
- `AgentStatus.state` 又复用 application `StatusType`，但 Agent 自身只显式写入 `READY/THINKING/DONE`，处理结束后又回到 `READY`。证据：`backend/alice/application/dto/responses.py:263-279`，`backend/alice/application/agent/agent.py:97`，`backend/alice/application/agent/agent.py:157-159`，`backend/alice/application/agent/agent.py:290-292`，`backend/alice/application/agent/agent.py:419`。

### 3.3 error：分类与上报路径

#### error 分类

| 类别 | 当前 code | 上报方式 | 证据 |
|---|---|---|---|
| 依赖缺失 | `NO_SERVICE` / `NO_STREAM_SERVICE` / `NO_ORCHESTRATOR` | `RuntimeEventType.ERROR_RAISED` | `backend/alice/application/workflow/chat_workflow.py:214-240`，`backend/alice/application/workflow/chat_workflow.py:648-662` |
| 能力 gate | `TOOL_CALLING_UNSUPPORTED` | `RuntimeEventType.ERROR_RAISED` | `backend/alice/application/workflow/chat_workflow.py:245-261` |
| 请求/流式异常 | `CHAT_ERROR` | `RuntimeEventType.ERROR_RAISED` | `backend/alice/application/workflow/chat_workflow.py:404-433` |
| 工具编排异常 | `TOOL_ERROR` | `RuntimeEventType.ERROR_RAISED` | `backend/alice/application/workflow/chat_workflow.py:684-714` |
| 迭代保护 | `MAX_ITERATIONS` | `RuntimeEventType.ERROR_RAISED` | `backend/alice/application/workflow/chat_workflow.py:787-807` |
| Agent 外围异常 | `PROCESSING_ERROR` / `NO_WORKFLOW_CHAIN` | 直接 `ErrorResponse` | `backend/alice/application/agent/agent.py:236-288` |
| bridge 处理异常 | 无固定结构化 code | 直接 legacy `error` | `backend/alice/cli/main.py:276-278`，`backend/alice/infrastructure/bridge/event_handlers/message_handler.py:147-165` |

#### error 上报路径

1. workflow 内部错误优先走 `RuntimeEventResponse(ERROR_RAISED, payload={content, code})`。证据：`backend/alice/application/workflow/chat_workflow.py:214-260`，`backend/alice/application/workflow/chat_workflow.py:422-432`，`backend/alice/application/workflow/chat_workflow.py:703-714`。
2. `response_to_dict()` 统一委托给 compatibility serializer。证据：`backend/alice/application/dto/responses.py:281-288`。
3. serializer 将 `ERROR_RAISED` 投影成 legacy `{"type":"error","content":...,"code":...}`。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:101-105`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:143-147`。
4. 因此当前 canonical 错误主路径不是 `status: done`，而是 legacy `error` 顶层消息。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:143-147`。

## 4. Bridge 投影规则

### 4.1 内部 runtime event -> legacy bridge message

| 内部 event | legacy 输出 | 字段转换 | 丢失信息 | 证据 |
|---|---|---|---|---|
| `status_changed` | `{"type":"status","content":normalized_status}` | `payload.status` 经 `_normalize_legacy_status()` | `runtime_output` 全部丢失 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:121-128`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:108-118` |
| `reasoning_delta` | `{"type":"thinking","content":payload.content}` | 直接转发 | `runtime_output`、链路元数据丢失 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:128-130` |
| `content_delta` | `{"type":"content","content":payload.content}` | 直接转发 | 同上 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:130-132` |
| `usage_updated` | `{"type":"tokens",...}` | `usage.total_tokens/prompt_tokens/completion_tokens` 拍平 | 其他 usage/metadata 字段丢失 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:132-138` |
| `tool_call_started` | `{"type":"status","content":"executing_tool"}` | 工具详情不出线，只保留忙碌状态 | 整个 tool_call payload 与 runtime_output.tool_calls 丢失 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:139-140` |
| `message_completed` | `{"type":"status","content":"done"}` | 最终完成态被压成状态消息 | 最终 `content/reasoning/usage/tool_calls/runtime_output` 全丢失；正文需依赖先前 delta 事件拼装 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:141-142` |
| `error_raised` | `{"type":"error","content":...,"code":...}` | 直接转 error | `runtime_output.status=error` 与 metadata 丢失 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:143-147` |
| `interrupt_ack` | `{"type":"status","content":"done"}` | `interrupted` 被折叠成 `done` | 中断确认与中断态丢失 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:148-149`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:108-118` |
| `tool_call_argument_delta` | 不输出 | 直接 drop | 整个 payload 与 runtime_output 快照都不可见 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166` |
| `tool_call_completed` | 不输出 | 直接 drop | 同上 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166` |
| `tool_result` | 不输出 | 直接 drop | 同上 | `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166` |

### 4.2 当前默认桥接链路

- 默认主链通过 `response_to_dict()` -> `serialize_application_response()` -> `serialize_runtime_event_response()` -> `serialize_canonical_event()` 投影到 legacy JSON。证据：`backend/alice/cli/main.py:280-301`，`backend/alice/application/dto/responses.py:281-288`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:168-235`。
- 旧 `MessageHandler` 路径也复用同一序列化函数，所以 wire 语义与默认 CLI 主链保持一致。证据：`backend/alice/infrastructure/bridge/event_handlers/message_handler.py:47-52`，`backend/alice/infrastructure/bridge/event_handlers/message_handler.py:128-135`。

### 4.3 legacy serializer 的职责边界

`legacy_compatibility_serializer.py` 当前承担的职责边界是：

1. **兼容边界**：把 `ApplicationResponse` / `RuntimeEventResponse` / `CanonicalBridgeEvent` 投影成冻结 legacy wire shape。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:121-235`。
2. **状态压缩**：把内部 richer status 归一化到 legacy 的 `ready/thinking/executing_tool/done`。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:108-118`。
3. **显式丢弃 unsupported event**：对不可表达的 canonical event 返回 `None`，不扩展 wire 协议。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166`。
4. **兼容性日志**：记录 `bridge.compatibility_serializer_used` 与 `bridge.event_dropped_by_legacy_projection`。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:31-77`。

它**不负责**：读取 stdin、检测中断、驱动 Agent、维护前端状态。那些职责分别在 `cli/main.py`、`message_handler.py`、`interrupt_handler.py`。证据：`backend/alice/cli/main.py:183-301`，`backend/alice/infrastructure/bridge/event_handlers/message_handler.py:68-167`，`backend/alice/infrastructure/bridge/event_handlers/interrupt_handler.py:53-103`。

## 5. Tool Call / Tool Result envelope

### 5.1 tool_call 在 event 流中的表示

当前至少存在三种 related shape：

| 位置 | 形状 | 说明 | 证据 |
|---|---|---|---|
| `stream_service` delta/completed/message_completed payload | `{id,type,index,function:{name,arguments}}` | domain 层归一化输出，嵌套 `function` | `backend/alice/domain/llm/models/response.py:42-85`，`backend/alice/domain/llm/services/stream_service.py:752-763`，`backend/alice/domain/llm/services/stream_service.py:800-823` |
| `StructuredToolCall` / `StructuredRuntimeOutput.tool_calls` | `{index,id,type,function_name,function_arguments}` | application 层拍平结构 | `backend/alice/application/dto/responses.py:57-75`，`backend/alice/application/workflow/chat_workflow.py:147-157` |
| `CanonicalToolCall` | `{index,id,type,function_name,function_arguments}` | infrastructure 再复制一份拍平结构 | `backend/alice/infrastructure/bridge/canonical_bridge.py:38-56` |

### 5.2 tool_result 在 event 流中的表示

`tool_result` 只有 workflow 在工具执行结束后产生，其 payload 与 `StructuredToolResult` 基本一致：

- payload：`{tool_call_id, tool_type, content, status, metadata}`。证据：`backend/alice/application/workflow/chat_workflow.py:720-727`。
- runtime_output 快照：`tool_results: list[StructuredToolResult]`。证据：`backend/alice/application/dto/responses.py:77-95`，`backend/alice/application/workflow/chat_workflow.py:728-747`。
- 该事件不会被 legacy wire 投影。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166`。

### 5.3 当前是否有统一 envelope

结论：**没有统一 envelope**，而是分散在多处并存在形状漂移：

1. `domain.llm.models.response.normalize_tool_call()` 输出嵌套 `function`。证据：`backend/alice/domain/llm/models/response.py:42-85`。
2. `ChatWorkflow.normalize_tool_call_payload()` 再把嵌套结构改写为内部聚合态。证据：`backend/alice/application/workflow/chat_workflow.py:135-146`。
3. `StructuredToolCall` 与 `CanonicalToolCall` 继续重复拍平定义。证据：`backend/alice/application/dto/responses.py:57-75`，`backend/alice/infrastructure/bridge/canonical_bridge.py:38-56`。
4. `tool_result` 完全是另一套 result envelope。证据：`backend/alice/application/dto/responses.py:77-95`，`backend/alice/application/workflow/chat_workflow.py:720-747`。

### 5.4 额外发现：tool_call 聚合依赖日志副作用

`stream_service.stream_runtime()` 本身没有显式调用 `_merge_tool_call_state()`，而是通过 `_log_stream_chunk(..., tool_call_state=...)` 的副作用来更新 `tool_call_state`；随后 `tool_call_started` / `tool_call_argument_delta` / `tool_call_completed` 都依赖这个状态。也就是说，**当前 tool_call envelope 的正确性与日志函数耦合**。证据：`backend/alice/domain/llm/services/stream_service.py:271-325`，`backend/alice/domain/llm/services/stream_service.py:714-763`，`backend/alice/domain/llm/services/stream_service.py:795-803`，`backend/alice/domain/llm/services/stream_service.py:85-110`。

## 6. 发现的问题与建议

### 6.1 重复定义

1. `RuntimeEventType` 与 `CanonicalEventType` 完全平行重复。建议收敛为单一事件枚举定义，serializer 与 workflow 都引用同一套 source。证据：`backend/alice/application/dto/responses.py:41-55`，`backend/alice/infrastructure/bridge/canonical_bridge.py:22-35`。
2. `StructuredRuntimeOutput` / `CanonicalRuntimeOutput`、`StructuredToolCall` / `CanonicalToolCall`、`StructuredToolResult` / `CanonicalToolResult` 也是重复定义。建议统一一套内部 contract model，再在最外层做 transport projection。证据：`backend/alice/application/dto/responses.py:57-120`，`backend/alice/infrastructure/bridge/canonical_bridge.py:38-119`。
3. `StatusType` 在 application DTO 与 bridge protocol 各有一套，且取值集合不一致。建议明确“内部状态全集”与“legacy 状态子集”的主从关系。证据：`backend/alice/application/dto/responses.py:29-39`，`backend/alice/infrastructure/bridge/protocol/messages.py:25-31`。

### 6.2 语义模糊点

1. 当前 legacy wire 不会正常输出顶层 `interrupt` 消息；中断确认被压成 `status: done`。若文档仍把 `interrupt` 写成常见后端输出，会误导联调。证据：`backend/alice/infrastructure/bridge/protocol/messages.py:77-80`，`backend/alice/cli/main.py:248-270`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:148-149`。
2. `error` 的 canonical 主路径是 legacy `error` 顶层消息，而不是 `status: done`。建议文档明确区分“状态归一化规则”和“错误投影规则”。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:108-118`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:143-147`。
3. `tool_call` payload 与 `runtime_output.tool_calls` 形状不一致，增加跨层转换成本。建议统一 nested 或 flattened 其一。证据：`backend/alice/domain/llm/models/response.py:42-85`，`backend/alice/application/dto/responses.py:57-75`。
4. `RuntimeEventResponse.runtime_output` 在类型上可空，但主链 `ChatWorkflow` 实际总是填写；建议将“类型可空”与“生产者保证非空”区别写清。证据：`backend/alice/application/dto/responses.py:206-214`，`backend/alice/application/workflow/chat_workflow.py:188-212`。

### 6.3 跨边界耦合风险

1. `application/dto/responses.py` 直接 import infrastructure serializer，说明 application 层已经反向依赖 bridge 兼容层；这会把 transport 兼容语义带回 DTO 定义层。建议反转依赖方向，让应用层只产出 canonical response，不知道 legacy serializer。证据：`backend/alice/application/dto/responses.py:11-13`，`backend/alice/application/dto/responses.py:281-288`。
2. `stream_service.stream_runtime()` 依赖 `_log_stream_chunk()` 的副作用维护 `tool_call_state`，把“日志”与“协议正确性”耦死。建议将状态合并显式放回主逻辑。证据：`backend/alice/domain/llm/services/stream_service.py:271-325`，`backend/alice/domain/llm/services/stream_service.py:714-763`。
3. legacy serializer 会丢弃 `tool_call_argument_delta` / `tool_call_completed` / `tool_result` / `runtime_output`，因此只改后端内部结构时虽然不破 wire，但很容易造成“内部 contract 以为已稳定、前端却完全不可见”的错觉。建议把“内部稳定”与“wire 稳定”分开审计。证据：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166`。

### 6.4 与 `exec/harness-decoupling-context.md` 不符之处

1. 该文把 `backend/alice/cli/main.py:262-275` 当作“CLI bridge 主循环”证据，但真实主循环在 `183-212`；`262-275` 只是 `_process_user_input()` 内部处理与发送响应片段。证据：`exec/harness-decoupling-context.md:171-175`，`backend/alice/cli/main.py:183-212`，`backend/alice/cli/main.py:262-275`。
2. 该文把“先稳定内部 canonical contract”当作方向判断是对的，但**当前现实并未真正收口到单一 canonical source**，因为 application DTO 与 infrastructure canonical bridge 仍重复定义同一批概念。证据：`exec/harness-decoupling-context.md:87-95`，`backend/alice/application/dto/responses.py:41-120`，`backend/alice/infrastructure/bridge/canonical_bridge.py:22-119`。

### 6.5 建议的最小收口顺序

1. 先统一 event / tool_call / tool_result / runtime_output 的单一定义源。证据：`backend/alice/application/dto/responses.py:41-120`，`backend/alice/infrastructure/bridge/canonical_bridge.py:22-119`。
2. 再把 serializer 明确定义为“唯一 legacy projection adapter”，不要再让 application DTO 反向依赖它。证据：`backend/alice/application/dto/responses.py:11-13`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:192-235`。
3. 最后才考虑前端迁移到 richer runtime event；在那之前，继续把 legacy wire 当冻结外部协议。证据：`docs/protocols/bridge.md:37-46`，`docs/protocols/bridge.md:85-88`，`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:160-166`。
