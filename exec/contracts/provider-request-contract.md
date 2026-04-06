# Provider / Request Envelope Canonical Contract Spec

> 目标：基于当前代码的**实际行为**，定义 provider capability、request envelope、tool binding 的 canonical contract。本文只描述已落地实现，不推断未来设计。

## 1. RequestEnvelope 最小字段集

### 1.1 Canonical 字段列表

`RequestEnvelope` 当前定义了 6 个顶层字段，且 `to_dict()` 固定输出这 6 个键；从“序列化 contract”看，它们构成当前最小字段集。证据：`backend/alice/application/runtime/models.py:168`, `backend/alice/application/runtime/models.py:179`。

| 字段 | 类型 | 构造是否必填 | 当前语义是否必需 | 语义说明 | 主要填充层 |
|---|---|---:|---:|---|---|
| `system_prompt` | `str` | 否（有默认值） | 是 | provider 请求使用的基础 system prompt，序列化后投影到 `system.prompt` | Agent 初始填充，Workflow 迭代透传/重建 |
| `messages` | `list[dict[str, Any]]` | 否 | 是 | 当前轮发送给模型的非 system 消息序列 | Agent 初始填充，Workflow 每轮重写 |
| `model_context` | `dict[str, Any]` | 否 | 是 | 拼接进 system prompt 的模型可见上下文 | Agent 初始填充，Workflow 透传/裁剪 |
| `tools` | `dict[str, list[dict[str, Any]]]` | 否 | 否（当前不参与真实 binding） | 工具快照，偏“展示/上下文”而非实际 provider bind 输入 | Agent 初始填充，Workflow 仅透传 |
| `request_metadata` | `RequestMetadata` | 否 | 是 | trace/request/task/session/span 与流式/思考开关等链路元数据 | Agent 填充，Workflow 透传并派生 provider metadata |
| `tool_history` | `list[dict[str, Any]]` | 否 | 否（当前主链路基本为空） | 额外注入到模型可见上下文的工具历史摘要 | Agent 初始填充，Workflow 透传 |

### 1.2 字段定义与序列化形态

`RequestEnvelope` 定义如下：`system_prompt`、`messages`、`model_context`、`tools`、`request_metadata`、`tool_history`；`to_dict()` 将其分别投影为 `system.prompt`、`messages`、`model_context`、`tools`、`request_metadata`、`tool_history`。证据：`backend/alice/application/runtime/models.py:172`, `backend/alice/application/runtime/models.py:180`。

### 1.3 各字段的实际填充来源

#### Agent 层的初始填充

`AliceAgent.process()` 先构建 `RuntimeContext`，再基于它构建 `RequestEnvelope`，并放入 `WorkflowContext.request_envelope`。证据：`backend/alice/application/agent/agent.py:166`, `backend/alice/application/agent/agent.py:179`, `backend/alice/application/agent/agent.py:183`。

`RuntimeContextBuilder.build_request_envelope()` 的当前填充规则：

- `system_prompt = runtime_context.system_prompt`
- `messages = 历史非 system 消息 + current_question 对应的新 user message`
- `model_context = {local_time, memory_snapshot, skill_snapshot}`
- `tools = runtime_context.tools`
- `request_metadata = runtime_context.request_metadata`
- `tool_history = runtime_context.tool_history`

证据：`backend/alice/application/runtime/runtime_context_builder.py:60`, `backend/alice/application/runtime/runtime_context_builder.py:74`。

#### Workflow 层的迭代填充/重建

`ChatWorkflow.execute()` 每轮都会调用 `build_iteration_request_envelope()`：

- 若已有 `active_request_envelope`，则**复制其 `system_prompt/model_context/tools/request_metadata/tool_history`**，但把 `messages` 重写为 `chat_service.messages` 中的非 system 消息；证据：`backend/alice/application/workflow/chat_workflow.py:300`, `backend/alice/application/workflow/chat_workflow.py:302`。
- 若只有 `active_runtime_context`，则重新构造 `RequestEnvelope`，其中 `model_context` 仅包含 `local_time/memory_snapshot/skill_snapshot`，`messages` 同样来自当前 `chat_service.messages` 的非 system 消息；证据：`backend/alice/application/workflow/chat_workflow.py:310`, `backend/alice/application/workflow/chat_workflow.py:312`。

### 1.4 RequestMetadata 子字段

`request_metadata` 当前包含：

- `session_id: str`
- `trace_id: str`
- `request_id: str`
- `task_id: str`
- `span_id: str`
- `enable_thinking: bool`
- `stream: bool`
- `extras: dict[str, Any]`

其 `to_dict()` 会把 `extras` 平铺回顶层。证据：`backend/alice/application/runtime/models.py:9`, `backend/alice/application/runtime/models.py:49`。

## 2. ProviderCapability 语义定义

### 2.1 当前字段与声明语义

`ProviderCapability` 是 `@dataclass(frozen=True)`，包含 6 个字段：

- `supports_tool_calling: bool = True`
- `supports_streaming: bool = True`
- `supports_usage_in_stream: bool = True`
- `supports_thinking: bool = False`
- `supports_tool_call_delta: bool = True`
- `supports_extra_headers: bool = True`

类注释明确要求“每个能力都必须显式声明，不允许通过 model-name 猜测”。证据：`backend/alice/domain/llm/providers/base.py:261`, `backend/alice/domain/llm/providers/base.py:263`。

### 2.2 唯一判断来源

当前运行时的能力判断**唯一来源是 provider 实例上的 frozen dataclass**：

- `BaseLLMProvider.__init__()` 将 `capabilities` 保存到 `self._capabilities`；若未传入，则回退到 `ProviderCapability()` 默认值。证据：`backend/alice/domain/llm/providers/base.py:282`, `backend/alice/domain/llm/providers/base.py:290`。
- `OpenAIProvider` 通过 `OpenAIConfig.capabilities` 把 capability 注入父类。证据：`backend/alice/domain/llm/providers/openai_provider.py:175`, `backend/alice/domain/llm/providers/openai_provider.py:202`。

### 2.3 环境变量覆盖的真实地位

环境变量并不是第二套判断逻辑；它只是**上游构造 dataclass 的覆盖入口**：

- `cli/main.py` 读取 `PROVIDER_SUPPORTS_TOOL_CALLING=false/0/no` 时，会构造 `ProviderCapability(supports_tool_calling=False)`；证据：`backend/alice/cli/main.py:137`, `backend/alice/cli/main.py:140`。
- 该 capability 随 `OrchestrationService.create_from_config()` 传给 `OpenAIConfig.capabilities`，最终注入 provider；证据：`backend/alice/cli/main.py:143`, `backend/alice/application/services/orchestration_service.py:84`, `backend/alice/application/services/orchestration_service.py:109`。

因此，**canonical 结论**是：

- 判断源头：`provider.capabilities`
- 环境变量：仅影响 `provider.capabilities` 的构造值，不直接参与后续判定

### 2.4 当前真正被消费的 capability 字段

在当前代码里，**只有 `supports_tool_calling` 被实际读取**：

- `stream_service._supports_structured_tool_calling()` 只读取 `provider.capabilities.supports_tool_calling`；证据：`backend/alice/domain/llm/services/stream_service.py:149`。
- `ChatWorkflow` 的预检查与 `build_tool_kwargs()` 的 binding 检查都依赖这个函数；证据：`backend/alice/application/workflow/chat_workflow.py:245`, `backend/alice/domain/llm/services/stream_service.py:168`。

其余 5 个字段在当前 backend 代码中未检索到消费点，属于**声明已存在、执行未落地**。证据：`backend/alice/domain/llm/providers/base.py:268`, `backend/alice/domain/llm/providers/base.py:272`。

### 2.5 是否存在绕过 capability 的其他判断

在当前主链路里，**没有发现通过 model-name 或 provider 私有分支绕过 capability 再决定是否 bind tools 的代码**：

- `ChatWorkflow` 用 `supports_structured_tool_calling(provider)` 做预检查；证据：`backend/alice/application/workflow/chat_workflow.py:243`, `backend/alice/application/workflow/chat_workflow.py:245`。
- `build_tool_kwargs()` 再次使用同一判断；证据：`backend/alice/domain/llm/services/stream_service.py:155`, `backend/alice/domain/llm/services/stream_service.py:168`。
- `OpenAIProvider._make_chat_request()` 对 `tools/tool_choice` 没有私有 if/else 判断，而是把除 `request_envelope` 外的 kwargs 原样透传。证据：`backend/alice/domain/llm/providers/openai_provider.py:387`, `backend/alice/domain/llm/providers/openai_provider.py:394`。

## 3. Provider 消费/忽略字段矩阵

### 3.1 RequestEnvelope 顶层字段矩阵

| RequestEnvelope 字段 | provider 是否直接消费 | provider 是否间接消费 | provider 是否允许消费 | 应由谁填充 | 实际说明 |
|---|---:|---:|---:|---|---|
| `system_prompt` | 否 | 是 | 应由 ChatService 消费，不应由 provider 直接解包 | Agent 初始，Workflow 透传 | `ChatService` 先把它转成 system message，再交给 provider；证据：`backend/alice/domain/llm/services/chat_service.py:332`, `backend/alice/domain/llm/services/chat_service.py:347` |
| `messages` | 否 | 是 | 应由 ChatService 消费，不应由 provider 直接解包 | Workflow 每轮重写 | `ChatService` 直接把 envelope.messages 还原成 `ChatMessage` 列表；证据：`backend/alice/domain/llm/services/chat_service.py:349`, `backend/alice/domain/llm/services/chat_service.py:352` |
| `model_context` | 否 | 是 | 应由 ChatService 消费，不应由 provider 直接解包 | Agent 初始，Workflow 透传/裁剪 | `ChatService` 把它拼进 system prompt；证据：`backend/alice/domain/llm/services/chat_service.py:339`, `backend/alice/domain/llm/services/chat_service.py:345` |
| `tools` | 否 | 否 | 当前不应由 provider 直接消费 | Agent 初始，Workflow 仅透传 | 实际 tool binding 完全不读 envelope.tools；证据：`backend/alice/application/workflow/chat_workflow.py:243`, `backend/alice/domain/llm/services/stream_service.py:180` |
| `request_metadata` | 否（业务请求） | 是（观测上下文） | 允许作为 observability 输入，不是模型消息输入 | Agent 填充，Workflow 派生/透传 | `request_envelope.request_metadata` 被日志抽取逻辑读取；证据：`backend/alice/domain/llm/providers/base.py:162`, `backend/alice/domain/llm/providers/base.py:169` |
| `tool_history` | 否 | 是 | 应由 ChatService 消费，不应由 provider 直接解包 | Agent 初始，Workflow 透传 | `ChatService` 把它注入 runtime_context，再拼到 system prompt；证据：`backend/alice/domain/llm/services/chat_service.py:341`, `backend/alice/domain/llm/services/chat_service.py:343` |

### 3.2 额外说明：provider 真正收到的 kwargs

`OpenAIProvider` 会把除 `request_envelope` 以外的 kwargs 全部透传给 SDK，所以当前 provider 实际会收到：

- `tools`
- `tool_choice`
- `metadata`
- 以及其他未来扩展字段

证据：`backend/alice/domain/llm/providers/openai_provider.py:387`, `backend/alice/domain/llm/providers/openai_provider.py:394`。

这意味着：

- `request_envelope` 是**本地 contract / observability contract**；
- `tools/tool_choice/metadata` 才是**provider transport contract**。

### 3.3 `request_metadata` 与 `metadata` 的关系

Workflow 会基于 `iteration_request_envelope.request_metadata` 派生一份 `provider_request_metadata`，再作为 `metadata` 传给 `build_tool_kwargs()`。证据：`backend/alice/application/workflow/chat_workflow.py:286`, `backend/alice/application/workflow/chat_workflow.py:391`。

因此当前链路里，链路元数据存在两份投影：

1. `request_envelope.request_metadata`：给本地日志/上下文抽取用；证据：`backend/alice/domain/llm/providers/base.py:162`。
2. `kwargs["metadata"]`：会被 provider 透传到 OpenAI SDK；证据：`backend/alice/domain/llm/services/stream_service.py:162`, `backend/alice/domain/llm/providers/openai_provider.py:387`。

## 4. Tool Binding 规则

### 4.1 Tool binding 发生在哪一层

实际 tool binding 不在 `ChatService`，也不在 provider 私有层，而在 **Workflow + StreamService helper**：

1. `ChatWorkflow` 先从 `ToolRegistry` 取可绑定工具 schema；证据：`backend/alice/application/workflow/chat_workflow.py:243`。
2. `ChatWorkflow` 调用 `build_tool_kwargs()` 决定是否把 `tools/tool_choice` 放入 provider kwargs；证据：`backend/alice/application/workflow/chat_workflow.py:392`。
3. `StreamService.stream_runtime()` 把这些 kwargs 原样传给 `provider.stream_chat()`；证据：`backend/alice/domain/llm/services/stream_service.py:697`, `backend/alice/domain/llm/services/stream_service.py:715`。
4. `OpenAIProvider._make_chat_request()` 最终把 `tools/tool_choice` 透传到 OpenAI SDK；证据：`backend/alice/domain/llm/providers/openai_provider.py:379`, `backend/alice/domain/llm/providers/openai_provider.py:394`。

### 4.2 判断是否 bind tools 的逻辑链路

当前链路是双重 gate：

#### 第一道：Workflow 预检查

如果 `tools` 非空且 provider 不支持 structured tool calling，则工作流直接报错返回。证据：`backend/alice/application/workflow/chat_workflow.py:243`, `backend/alice/application/workflow/chat_workflow.py:245`。

#### 第二道：build_tool_kwargs()

`build_tool_kwargs()` 的逻辑是：

- 无 tools：只返回 `metadata/request_envelope`
- 有 tools 但 capability 不支持：记录 `binding.capability_mismatch` 并抛 `ValueError`
- 有 tools 且 capability 支持：写入 `tools` 与 `tool_choice="auto"`

证据：`backend/alice/domain/llm/services/stream_service.py:155`, `backend/alice/domain/llm/services/stream_service.py:166`, `backend/alice/domain/llm/services/stream_service.py:180`。

### 4.3 tool schema 的来源

当前实际绑定给 provider 的 schema 来源是 `ToolRegistry.list_openai_tools()`，而不是 `RequestEnvelope.tools`：

- `ToolRegistry.list_openai_tools()` 只返回 `_tools` 中定义的 OpenAI function schema；证据：`backend/alice/domain/execution/services/tool_registry.py:21`, `backend/alice/domain/execution/services/tool_registry.py:64`。
- 当前 `_tools` 只有 `run_bash` 与 `run_python` 两个真正可绑定 schema；证据：`backend/alice/domain/execution/services/tool_registry.py:22`, `backend/alice/domain/execution/services/tool_registry.py:39`。

### 4.4 是否存在 provider 私有分支

在当前主链路中，**未发现 provider 私有的“硬编码 bind / 不 bind tools”分支**：

- `OpenAIProvider` 不检查 model name；证据：`backend/alice/domain/llm/providers/base.py:263`。
- `OpenAIProvider` 不检查 provider type；只透传 kwargs；证据：`backend/alice/domain/llm/providers/openai_provider.py:387`, `backend/alice/domain/llm/providers/openai_provider.py:394`。

## 5. Provider 调用链路

### 5.1 Agent → RuntimeContext / RequestEnvelope

`AliceAgent.process()` 的职责：

- 生成并回写 request correlation ids；证据：`backend/alice/application/agent/agent.py:28`, `backend/alice/application/agent/agent.py:44`
- 读取当前消息历史；证据：`backend/alice/application/agent/agent.py:162`, `backend/alice/application/agent/agent.py:164`
- 构建 `RuntimeContext`；证据：`backend/alice/application/agent/agent.py:166`
- 构建 `RequestEnvelope`；证据：`backend/alice/application/agent/agent.py:179`
- 把两者塞进 `WorkflowContext` 并交给 workflow chain；证据：`backend/alice/application/agent/agent.py:183`, `backend/alice/application/agent/agent.py:195`

### 5.2 Workflow：请求构造、能力 gate、tool orchestration

`ChatWorkflow.execute()` 的职责：

- 把当前用户输入加入持久消息历史；证据：`backend/alice/application/workflow/chat_workflow.py:242`
- 从 `ToolRegistry` 拉取可绑定 OpenAI tools；证据：`backend/alice/application/workflow/chat_workflow.py:243`
- 做 capability 预检查；证据：`backend/alice/application/workflow/chat_workflow.py:245`
- 为本轮重建 `RequestEnvelope`；证据：`backend/alice/application/workflow/chat_workflow.py:300`, `backend/alice/application/workflow/chat_workflow.py:381`
- 让 `ChatService` 基于 envelope 构造真正发送给模型的 messages；证据：`backend/alice/application/workflow/chat_workflow.py:387`
- 组装 provider kwargs（含 tools/tool_choice/metadata/request_envelope）；证据：`backend/alice/application/workflow/chat_workflow.py:391`, `backend/alice/application/workflow/chat_workflow.py:392`
- 调用 `StreamService.stream_runtime()` 获取流式 canonical runtime 事件；证据：`backend/alice/application/workflow/chat_workflow.py:441`, `backend/alice/application/workflow/chat_workflow.py:442`
- 若检测到 tool calls，则调用 `FunctionCallingOrchestrator` 执行并把 assistant/tool message 回灌到 `ChatService`；证据：`backend/alice/application/workflow/chat_workflow.py:675`, `backend/alice/application/workflow/chat_workflow.py:716`。

### 5.3 ChatService：把 envelope 变成 provider messages

`ChatService.build_request_messages()` 的职责：

- 若传入 `request_envelope`，优先走 envelope 路径；证据：`backend/alice/domain/llm/services/chat_service.py:301`, `backend/alice/domain/llm/services/chat_service.py:307`
- 读取 `system.prompt` 作为 base system prompt；证据：`backend/alice/domain/llm/services/chat_service.py:332`, `backend/alice/domain/llm/services/chat_service.py:337`
- 读取 `model_context` 与 `tool_history`，拼出模型可见上下文；证据：`backend/alice/domain/llm/services/chat_service.py:339`, `backend/alice/domain/llm/services/chat_service.py:343`, `backend/alice/domain/llm/services/chat_service.py:345`
- 把 envelope.messages 还原为 `ChatMessage` 列表；证据：`backend/alice/domain/llm/services/chat_service.py:349`, `backend/alice/domain/llm/services/chat_service.py:351`

### 5.4 StreamService：provider stream → runtime 事件

`StreamService.stream_runtime()` 的职责：

- 调用 `provider.stream_chat(messages, **kwargs)`；证据：`backend/alice/domain/llm/services/stream_service.py:715`
- 把 chunk usage 转成 `usage_updated`；证据：`backend/alice/domain/llm/services/stream_service.py:730`, `backend/alice/domain/llm/services/stream_service.py:733`
- 把 tool call delta 聚合为 `tool_call_started / tool_call_argument_delta / tool_call_completed`；证据：`backend/alice/domain/llm/services/stream_service.py:743`, `backend/alice/domain/llm/services/stream_service.py:752`, `backend/alice/domain/llm/services/stream_service.py:800`
- 最终输出 `message_completed`；证据：`backend/alice/domain/llm/services/stream_service.py:816`

### 5.5 Provider：transport 执行

`BaseLLMProvider.stream_chat()` 的职责：

- 把消息统一转成内部 `ChatMessage`
- 记录 prompt built 日志
- 调用子类 `_make_chat_request(stream=True, **kwargs)`
- 再交给 `_extract_stream_chunks()`

证据：`backend/alice/domain/llm/providers/base.py:435`, `backend/alice/domain/llm/providers/base.py:461`。

`OpenAIProvider._make_chat_request()` 的职责：

- 把 messages 转成 OpenAI API messages；证据：`backend/alice/domain/llm/providers/openai_provider.py:373`, `backend/alice/domain/llm/providers/openai_provider.py:380`
- 注入 `model/messages/stream/extra_headers`；证据：`backend/alice/domain/llm/providers/openai_provider.py:379`, `backend/alice/domain/llm/providers/openai_provider.py:385`
- 除 `request_envelope` 外，将其余 kwargs 全部并入 API params；证据：`backend/alice/domain/llm/providers/openai_provider.py:387`, `backend/alice/domain/llm/providers/openai_provider.py:394`
- 调用 `client.chat.completions.with_raw_response.create(**params)`；证据：`backend/alice/domain/llm/providers/openai_provider.py:431`, `backend/alice/domain/llm/providers/openai_provider.py:432`

## 6. 发现的问题与建议

### 6.1 `RequestEnvelope.tools` 与真实 bind 集合不一致

**问题**：`RequestEnvelope.tools` 来自 `tool_registry.snapshot_dict()`，包含 `builtin_system_tools / skills / terminal_commands / code_execution` 四类快照；但真正绑定给 provider 的只有 `list_openai_tools()` 返回的 `run_bash/run_python` 两个 function schema。证据：`backend/alice/application/runtime/runtime_context_builder.py:124`, `backend/alice/domain/execution/services/tool_registry.py:86`, `backend/alice/domain/execution/services/tool_registry.py:118`, `backend/alice/application/workflow/chat_workflow.py:243`, `backend/alice/domain/execution/services/tool_registry.py:64`。

**影响**：模型可见上下文中的“工具快照”与 provider 真正可调用的工具集合不是同一个 contract。

**建议**：把 `RequestEnvelope.tools` 明确标注为“context snapshot”，另增一个独立字段（如 `bindable_tools`），或直接让 binding 以 envelope 内字段为唯一来源，避免双轨语义。

### 6.2 capability 判断已收口，但 gate 重复

**问题**：当前没有发现 capability 绕过；但 `ChatWorkflow` 与 `build_tool_kwargs()` 各做了一次相同 gate。证据：`backend/alice/application/workflow/chat_workflow.py:245`, `backend/alice/domain/llm/services/stream_service.py:168`。

**影响**：行为一致时只是重复；一旦未来两处文案、错误码、判断条件发生漂移，会形成新的隐式 contract 分叉。

**建议**：保留一个 canonical gate，另一处仅做断言或删去。

### 6.3 `ProviderCapability` 大部分字段仍是“声明未执行”

**问题**：6 个 capability 字段里，当前只有 `supports_tool_calling` 被消费；其余 `supports_streaming / supports_usage_in_stream / supports_thinking / supports_tool_call_delta / supports_extra_headers` 未见执行点。证据：`backend/alice/domain/llm/providers/base.py:267`, `backend/alice/domain/llm/providers/base.py:272`, `backend/alice/domain/llm/services/stream_service.py:149`。

**影响**：dataclass 看起来像完整 contract，实际上只有 1 个字段生效，容易让调用方误判 provider 差异已被统一建模。

**建议**：要么补齐消费点，要么把未落地字段降级为文档说明，避免“伪 contract”。

### 6.4 `request_metadata` 与 provider `metadata` 职责重叠

**问题**：同一组链路元数据既存在于 `request_envelope.request_metadata`，又被 workflow 重新投影成 `kwargs["metadata"]` 传给 provider。证据：`backend/alice/application/workflow/chat_workflow.py:286`, `backend/alice/application/workflow/chat_workflow.py:391`, `backend/alice/domain/llm/providers/base.py:162`, `backend/alice/domain/llm/providers/openai_provider.py:387`。

**影响**：一个是本地 envelope contract，一个是 transport contract；二者未显式区分“日志用途”与“API 参数用途”。

**建议**：明确分层：

- `request_metadata` 仅用于本地 observability
- `metadata` 仅用于 provider transport

并在 workflow 中由单一函数完成投影，避免重复语义漂移。

### 6.5 `tool_history` 字段当前基本失活

**问题**：`RuntimeContextBuilder.build()` 支持接收 `tool_history`，但 `AliceAgent.process()` 调用时未传入，因此初始 envelope 的 `tool_history` 默认为空。证据：`backend/alice/application/runtime/runtime_context_builder.py:37`, `backend/alice/application/runtime/runtime_context_builder.py:57`, `backend/alice/application/agent/agent.py:166`。

工具执行完成后，workflow 会把 assistant/tool messages 写回 `ChatService` 消息历史，但不会更新 `RequestEnvelope.tool_history`。证据：`backend/alice/application/workflow/chat_workflow.py:716`, `backend/alice/application/workflow/chat_workflow.py:717`。

**影响**：当前“工具历史”主要靠真实消息历史承载，而不是 envelope.tool_history 字段；该字段名义存在、实际弱使用。

**建议**：二选一：

- 要么删掉 `tool_history`，统一靠消息历史表达；
- 要么把它定义成真正的 canonical tool-result summary，并在每轮工具执行后更新。

### 6.6 Provider kwargs 透传过宽，跨 provider contract 易漂移

**问题**：`OpenAIProvider` 只排除了 `request_envelope`，其余 kwargs 全部透传。证据：`backend/alice/domain/llm/providers/openai_provider.py:387`, `backend/alice/domain/llm/providers/openai_provider.py:394`。

**影响**：当前只有 OpenAIProvider 时问题不明显；一旦引入第二个 provider，不同 provider 对 `metadata`、未知 kwargs、header 相关参数的处理很容易不一致。

**建议**：在 provider 边界引入显式 allowlist，把 transport contract 收敛为固定字段集，而不是“除 request_envelope 外全部透传”。

## 结论

当前代码已经把“是否支持 structured tool calling”的唯一判断源收口到 `provider.capabilities.supports_tool_calling`，Phase 4 的核心目标已经落地。证据：`backend/alice/domain/llm/providers/base.py:261`, `backend/alice/domain/llm/services/stream_service.py:149`, `backend/alice/cli/main.py:139`。

但当前 canonical contract 仍有三个关键不一致：

1. `RequestEnvelope.tools` ≠ 实际 bind tools
2. `request_metadata` 与 `metadata` 职责重叠
3. `tool_history` 字段存在但主链路未形成闭环

如果后续要继续 Phase 5，我建议优先收敛这三处，再谈多 provider 一致性。