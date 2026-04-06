# Contracts 交叉审查 README

> 目标：把 `exec/contracts/` 下三份 contract spec 的边界、依赖、矛盾与非目标统一收口，作为后续 Phase 0 / Phase 1 / Phase 2 / Phase 3 的交叉导航页。本文基于当前文档描述的**已落地实现**做审查，不把未来目标态当作现状。

---

## 1. 文档索引与摘要

### 1.1 Runtime Event / Bridge

- 文档：`exec/contracts/runtime-event-contract.md`
- 关注边界：runtime event、`RuntimeEventResponse`、`StructuredRuntimeOutput`、legacy bridge projection。
- 核心结论：
  1. 当前最小稳定 runtime event 集合是 `status_changed`、`reasoning_delta`、`content_delta`、`usage_updated`、`message_completed`、`error_raised`、`interrupt_ack`；`tool_call_argument_delta`、`tool_call_completed`、`tool_result` 暂不应承诺为外部稳定协议。见 `exec/contracts/runtime-event-contract.md:25-30`。
  2. `RuntimeEventResponse` 顶层 envelope 固定有 `response_type`、`event_type`、`payload`、`runtime_output`；`runtime_output` 类型上可空，但主链实际总是填写。见 `exec/contracts/runtime-event-contract.md:34-43`。
  3. `StructuredRuntimeOutput` 维护一份聚合快照，包含 `message_id`、`status`、`reasoning`、`content`、`tool_calls`、`tool_results`、`usage`、`metadata`。见 `exec/contracts/runtime-event-contract.md:45-57`。
  4. `tool_call` 形状存在跨层漂移：event payload 使用嵌套 `function: {name, arguments}`，而 `runtime_output.tool_calls` 使用拍平 `function_name` / `function_arguments`。见 `exec/contracts/runtime-event-contract.md:145-151`。
  5. interrupt 的内部终点是 `interrupt_ack + runtime_output.status=interrupted`，但 legacy 外部终点被压扁为 `status: done`。见 `exec/contracts/runtime-event-contract.md:171-175`。
  6. internal status 全集是 `ready / thinking / streaming / executing_tool / done / error / interrupted`，而 legacy status 只是压缩视图。见 `exec/contracts/runtime-event-contract.md:176-205`。
  7. `canonical_bridge.py` 现在已直接复用 application DTO 导出的 `RuntimeEventType`、`RuntimeEventResponse`、`StructuredRuntimeOutput` 等模型；README 中若仍把 bridge / dto 描述成“双份 canonical 定义并存”，应视为过时，当前剩余问题主要是 legacy projection 与局部 envelope 形状漂移，而不是 bridge 再维护第二套类型。证据：`backend/alice/infrastructure/bridge/canonical_bridge.py:1-19`。

### 1.2 Provider / Request Envelope

- 文档：`exec/contracts/provider-request-contract.md`
- 关注边界：`RequestEnvelope`、`RequestMetadata`、`ProviderCapability`、provider transport kwargs、tool binding。
- 核心结论：
  1. `RequestEnvelope` 当前最小字段集固定为 6 个：`system_prompt`、`messages`、`model_context`、`tools`、`request_metadata`、`tool_history`。见 `exec/contracts/provider-request-contract.md:5-22`。
  2. `request_metadata` 当前包含 `session_id`、`trace_id`、`request_id`、`task_id`、`span_id`、`enable_thinking`、`stream`、`extras`，且 `extras` 会被平铺回顶层。见 `exec/contracts/provider-request-contract.md:48-61`。
  3. capability 的唯一判断源已经收口到 `provider.capabilities`；环境变量只是构造该 dataclass 的上游输入。见 `exec/contracts/provider-request-contract.md:78-96`。
  4. 6 个 capability 字段里，当前真正被执行路径消费的只有 `supports_tool_calling`；其他字段仍属于“声明已存在、执行未落地”。见 `exec/contracts/provider-request-contract.md:97-105`。
  5. `RequestEnvelope` 不是 provider transport contract；当前 workflow 会把 `metadata` 与 `request_envelope` 一并放入本地 request kwargs，但 `OpenAIProvider` 在真正调用 SDK 前会显式过滤掉这两个字段，只把 transport 相关参数如 `tools`、`tool_choice` 等传给 `chat.completions.create()`。证据：`backend/alice/domain/llm/services/stream_service.py:155-191`、`backend/alice/domain/llm/providers/openai_provider.py:387-394`、`backend/alice/domain/llm/providers/openai_provider.py:432`。
  6. tool binding 的真实决策点当前仍落在 `StreamService.build_tool_kwargs()`；它负责 capability 校验、binding 日志与 request kwargs 拼装。`ChatWorkflow` 负责准备工具集合与 metadata / request_envelope 投影，但代码中已看不到第二套显式 capability gate，因此文档若继续写成“workflow + stream service 双 gate”应视为漂移。证据：`backend/alice/application/workflow/chat_workflow.py:338-353`、`backend/alice/domain/llm/services/stream_service.py:155-191`。
  7. 当前真正绑定给 provider 的 tools 来源是 `ToolRegistry.list_openai_tools()`，不是 `RequestEnvelope.tools`。见 `exec/contracts/provider-request-contract.md:181-187`。
  8. 该 spec 识别出的三处关键问题仍基本成立：`RequestEnvelope.tools` 与真实 bind 集合不一致、`request_metadata` 与 provider `metadata` 职责重叠、`tool_history` 字段存在但主链未闭环；但 transport 层已经不再直接接收 `metadata` / `request_envelope`。见 `exec/contracts/provider-request-contract.md:256-326`。

### 1.3 Execution Harness

- 文档：`exec/contracts/execution-harness-contract.md`
- 关注边界：sandbox readiness、container lifecycle、`ToolSchemaDefinition` / `ToolInvocation` / `ExecutionResult` / `ToolExecutionResult`、execution backend seam。
- 核心结论：
  1. 旧文档里“`LifecycleService`、`DockerExecutor`、`ContainerManager` 三套 owner 并存”的描述已经部分过时；当前代码已显式引入 `ExecutionBackend` seam，并让 `LifecycleService` 与 `DockerExecutor` 优先委托同一 backend。剩余问题更准确地说是“兼容入口仍在，但主执行语义已开始收口到 backend”。证据：`backend/alice/application/services/lifecycle_service.py:29-62`、`backend/alice/domain/execution/executors/base.py`、`backend/alice/domain/execution/executors/docker_executor.py`、`backend/alice/infrastructure/docker/container_manager.py`。
  2. `LifecycleService` 已不再强行覆盖调用方传入的 `docker_config.project_root`；若传入 backend 且其 `config` 是 `DockerConfig`，会优先沿用 backend config。见 `backend/alice/application/services/lifecycle_service.py:45-62`。
  3. 结构化工具执行主链仍是：provider tool call → `ToolInvocation` → `ExecutionService` → `DockerExecutor` → `ExecutionResult` → `ToolResultPayload / ToolExecutionResult` → tool message 回注模型。见 `exec/contracts/execution-harness-contract.md:24-75`。
  4. 当前 `ToolRegistry` 对模型暴露的 bindable tools 只有 `run_bash`、`run_python`。见 `exec/contracts/execution-harness-contract.md:97-116`。
  5. tool 相关 contract 仍分散在多层：`ToolSchemaDefinition`、`ToolInvocation`、`ExecutionResult`、`ToolResultPayload`、`ToolExecutionResult`，没有一套统一 envelope 贯穿全链。见 `exec/contracts/execution-harness-contract.md:117-163`。
  6. `ExecutionService.execute()` 仍保留 `ExecutionResult | str` 双返回制，导致执行边界类型语义分裂。证据：`backend/alice/domain/execution/services/execution_service.py:264-278`。
  7. interrupt contract 的核心风险仍在：runtime 可以接受中断，但当前实现不应被表述为“已可靠终止底层执行进程”；因此 `interrupt_ack` 只能代表会话流中断。见 `exec/contracts/execution-harness-contract.md:327-337` 及现有 workflow / gateway 语义。
  8. 收口方向已经明确：以单一 `SandboxProvider / ExecutionBackend` seam 统一 `ensure_ready / exec / status / interrupt / cleanup`。见 `exec/contracts/execution-harness-contract.md:167-245`。

---

## 2. 三份 spec 的交叉结论

从第一性原理看，这三份文档描述的是同一条链路上的三个边界：

1. **请求边界**：`RequestEnvelope`、provider capability、provider kwargs。
2. **运行时输出边界**：`RuntimeEventResponse`、`StructuredRuntimeOutput`、legacy projection。
3. **执行边界**：tool schema、tool invocation、sandbox lifecycle、tool result。

把三份 spec 串起来后，当前系统的真实闭环应当是：

`RequestEnvelope / RequestMetadata`
→ provider transport kwargs
→ provider stream chunk
→ runtime event / runtime_output
→ tool call 聚合
→ execution backend
→ tool result
→ assistant/tool message 回注
→ 下一轮请求重建。

当前的问题不是单份 spec 不清楚，而是**跨这三条边界还没有形成一个真正单一的端到端 contract**。

---

## 3. Compatibility Boundary 清单

下面列的是当前应该被视为**兼容边界**的接口、载荷和枚举。凡落在该清单内的对象，改动前都应先判断：改的是内部实现，还是用户/前端/未来 gateway 依赖的语义边界。

### 3.1 高谨慎等级

#### A. `RuntimeEventType` 最小稳定集合

- 边界对象：`status_changed`、`reasoning_delta`、`content_delta`、`usage_updated`、`message_completed`、`error_raised`、`interrupt_ack`
- 原因：这些事件要么直接驱动 workflow 状态机，要么直接投影到 legacy wire。见 `exec/contracts/runtime-event-contract.md:25-30`。
- 风险：一旦字段名、事件名或 payload 形状变化，bridge compatibility、日志审计和后续 gateway 投影都会漂移。

#### B. `RuntimeEventResponse` 顶层 envelope

- 边界对象：`response_type`、`event_type`、`payload`、`runtime_output`
- 原因：这是 runtime 输出的主承载体，既是内部 canonical response，也是 serializer 输入。见 `exec/contracts/runtime-event-contract.md:34-43`。
- 风险：顶层 envelope 变化会直接冲击 `response_to_dict()` 与 serializer 投影路径。

#### C. `StructuredRuntimeOutput` 最小字段集

- 边界对象：`message_id`、`status`、`reasoning`、`content`、`tool_calls`、`tool_results`、`usage`、`metadata`
- 原因：这是所有 event 的聚合快照；未来 richer 前端或 gateway 也最可能依赖它。见 `exec/contracts/runtime-event-contract.md:45-57`。
- 风险：字段删改会让运行态快照失去可比性，也会冲击跨文档对齐。

#### D. `RequestEnvelope` 最小字段集

- 边界对象：`system_prompt`、`messages`、`model_context`、`tools`、`request_metadata`、`tool_history`
- 原因：该对象已是 agent → workflow → chat service 的稳定请求承载体。见 `exec/contracts/provider-request-contract.md:5-22`。
- 风险：字段改名、删改或语义重定义会影响请求重建与 observability。

#### E. `ProviderCapability.supports_tool_calling`

- 边界对象：`provider.capabilities.supports_tool_calling`
- 原因：这是当前唯一本轮真正被执行路径消费的 capability gate，且实际代码里的显式校验点集中在 `StreamService.build_tool_kwargs()`。见 `exec/contracts/provider-request-contract.md:78-105` 与 `backend/alice/domain/llm/services/stream_service.py:155-191`。
- 风险：若重新在 workflow、provider 私有逻辑或 model-name heuristic 引入第二套判断，会再次产生分叉。

#### F. `ToolSchemaDefinition` → provider tool schema 映射

- 边界对象：`ToolRegistry.list_openai_tools()` 返回的可绑定 schema
- 原因：这是模型可调用工具集合的唯一有效来源。见 `exec/contracts/provider-request-contract.md:181-187`、`exec/contracts/execution-harness-contract.md:103-115`。
- 风险：如果 `RequestEnvelope.tools` 和真实 bind source 继续并行演化，会造成模型上下文与真实能力不一致。

#### G. execution backend 最小 seam

- 边界对象：`ensure_ready / exec / status / interrupt / cleanup`
- 原因：execution-harness spec 已把它定义为未来收口目标，也是三处 owner 重复职责的真正兼容边界。见 `exec/contracts/execution-harness-contract.md:171-245`。
- 风险：若继续在 `LifecycleService`、`DockerExecutor`、`ContainerManager` 各自扩语义，后续插件化与替换会继续失控。

### 3.2 中谨慎等级

#### H. `RequestMetadata` 字段集

- 边界对象：`session_id`、`trace_id`、`request_id`、`task_id`、`span_id`、`enable_thinking`、`stream`、`extras`
- 原因：这是请求链路 correlation 的共同来源。见 `exec/contracts/provider-request-contract.md:48-61`。
- 风险：目前 provider `metadata` 和 runtime `metadata` 还是两份投影，若字段漂移会造成链路断裂。

#### I. legacy status 归一化规则

- 边界对象：`thinking/streaming -> thinking`、`executing_tool -> executing_tool`、`done/interrupted/error -> done`
- 原因：这套映射已经是外部旧协议的兼容承诺。见 `exec/contracts/runtime-event-contract.md:195-205`。
- 风险：若随意改变，现有前端和旧 bridge 协议会误解状态。

#### J. `ExecutionStatus` 五态枚举

- 边界对象：`success / failure / timeout / interrupted / blocked`
- 原因：这是底层执行结果当前最完整的状态枚举。见 `exec/contracts/execution-harness-contract.md:127-139`。
- 风险：runtime `tool_result.status` 还未显式对齐它，若枚举继续扩散，会让工具失败语义失控。

#### K. `ToolInvocation` / `ToolExecutionResult` / `ToolResultPayload`

- 原因：虽然现在还不是单一全链 canonical envelope，但已经承载真实执行语义。见 `exec/contracts/execution-harness-contract.md:119-163`。
- 风险：改动时需要同步检查 provider tool call shape、workflow tool_result payload、回注 message content。

### 3.3 低谨慎等级

#### L. `RequestEnvelope.tools`

- 原因：它当前更像工具快照，而不是绑定输入。见 `exec/contracts/provider-request-contract.md:258-265`。
- 风险：不是不能改，而是必须先重命名或重新界定语义，再改其字段。

#### M. `tool_history`

- 原因：字段存在，但主链未闭环。见 `exec/contracts/provider-request-contract.md:295-307`。
- 风险：它不能被当作稳定主边界使用；更适合作为待裁撤或待收口对象。

#### N. legacy serializer 明确丢弃的 event

- 对象：`tool_call_argument_delta`、`tool_call_completed`、`tool_result`
- 原因：当前外部 wire 看不到它们。见 `exec/contracts/runtime-event-contract.md:246-248`。
- 风险：这些对象对内部审计仍有意义，但对外兼容边界的重要性较低。

---

## 4. 非目标清单

以下内容直接来自 `exec/harness-decoupling-plan.md` 的“明确不做”与总原则，属于当前阶段**不插件化、不平台化、不提前抽象**的范围。见 `exec/harness-decoupling-plan.md:32-38`、`exec/harness-decoupling-plan.md:198-207`。

1. 不把 `ChatWorkflow` 做成插件系统。
2. 不把 frontend state / dispatcher 做成插件架构。
3. 不围绕 `EventBus` 或 `MessageQueue` 提前做平台化。
4. 不把 legacy wire 当未来主协议继续扩展。
5. 不为了“可能未来会需要”而先设计整套通用 gateway/plugin framework。

补充理解：

- 当前阶段应先稳内核，再开插件点；先稳定 runtime event、request envelope、provider capability、tool schema/tool result，再开放 provider adapter、tool source、execution harness adapter、remote transport/gateway adapter。见 `exec/harness-decoupling-plan.md:13-27`。
- 因此，README 里的 compatibility boundary 应服务于“收口核心 contract”，而不是把核心编排层本身做成可插拔框架。

---

## 5. 交叉审查发现的矛盾与统一建议

下面按“字段 / 概念 / 状态机 / 时序 / 错误语义”分类列出。

### 5.1 字段层矛盾

#### 问题 1：`tools` 同名但三种语义并存

- `RequestEnvelope.tools` 是工具快照，不是真实 binding source。见 `exec/contracts/provider-request-contract.md:15-18`、`exec/contracts/provider-request-contract.md:258-265`。
- provider kwargs 里的 `tools` 才是真实绑定给模型的 schema。见 `exec/contracts/provider-request-contract.md:127-141`。
- execution harness 侧真正可执行的是 `ToolSchemaDefinition` / `ToolInvocation`。见 `exec/contracts/execution-harness-contract.md:117-125`。

**矛盾本质**：同名字段覆盖了“上下文快照”“provider bind 输入”“执行入口”三种不同 contract。

**统一建议**：

- 把 `RequestEnvelope.tools` 明确重命名或标注为 `tool_context_snapshot`。
- 把真实绑定集合单列为 `bindable_tools`，并明确其唯一来源是 `ToolRegistry.list_openai_tools()`。
- 文档层先统一 wording：

```text
RequestEnvelope.tools MUST be treated as tool context snapshot only and MUST NOT be used as the provider binding source.
Provider bindable tools MUST be derived from ToolRegistry.list_openai_tools() in the same iteration.
```

#### 问题 2：`tool_call` / `tool_result` 形状跨层漂移

- runtime event payload 使用嵌套 `function: {name, arguments}`。见 `exec/contracts/runtime-event-contract.md:147-151`。
- `runtime_output.tool_calls` 使用拍平 `function_name` / `function_arguments`。见 `exec/contracts/runtime-event-contract.md:149-151`。
- execution harness 又回到 `ToolInvocation` / `ToolResultPayload` 的另一套表示。见 `exec/contracts/execution-harness-contract.md:119-125`。

**矛盾本质**：同一条工具调用，在 provider、runtime、execution 三层至少要经历两次形状变换。

**统一建议**：

- 统一一套 canonical `ToolCallEnvelope`，推荐跨三层都使用嵌套 `function` 形状，因为 provider payload 已经是这个结构。
- 统一一套 canonical `ToolResultEnvelope`，不要把结构化结果再埋进 JSON string `content`。
- 文档层先统一 wording：

```text
A ToolCallEnvelope MUST use one canonical shape across provider, runtime events, and execution orchestration.
A ToolResultEnvelope MUST expose structured fields directly and MUST NOT rely on undocumented embedded JSON string payloads.
```

#### 问题 3：元数据存在三份投影，但没有单一来源规则

- `request_envelope.request_metadata` 是本地 observability 输入。见 `exec/contracts/provider-request-contract.md:143-151`。
- provider transport 的 `metadata` 来自 workflow 派生。见 `exec/contracts/provider-request-contract.md:143-151`。
- `runtime_output.metadata` 维护 iteration + correlation ids。见 `exec/contracts/runtime-event-contract.md:45-57`。

**矛盾本质**：三边都在持有 metadata，但没有明说谁是 source of truth、谁是 projection。

**统一建议**：

- 明确 `RequestMetadata` 是唯一来源。
- provider transport metadata 和 runtime metadata 都只能是投影，不得自造新字段。
- 文档层先统一 wording：

```text
RequestMetadata MUST be the single source of truth for correlation identifiers.
Provider transport metadata and runtime event metadata MUST be deterministic projections of RequestMetadata.
```

#### 问题 4：`tool_result.status` 未与 `ExecutionStatus` 对齐

- execution harness 明确定义了 `success / failure / timeout / interrupted / blocked`。见 `exec/contracts/execution-harness-contract.md:127-139`。
- runtime `tool_result.status` 仍只是 `str`，没有枚举约束。见 `exec/contracts/runtime-event-contract.md:105-113`。

**统一建议**：

- `tool_result.status` 应直接复用 `ExecutionStatus` 枚举，不再生成第二套 vocabulary。

---

### 5.2 概念层矛盾

#### 问题 5：“canonical” 被多处重复使用，但没有真正单一 source of truth

- runtime-event 文档明确指出 `RuntimeEventType` / `CanonicalEventType` 与多组 `Structured*` / `Canonical*` 是重复定义。见 `exec/contracts/runtime-event-contract.md:7-10`、`exec/contracts/runtime-event-contract.md:301-305`。
- execution-harness 也明确承认当前“只有局部统一，没有全链统一”。见 `exec/contracts/execution-harness-contract.md:141-163`。
- provider-request 则明确区分了本地 contract 和 transport contract。见 `exec/contracts/provider-request-contract.md:138-151`。

**矛盾本质**：每层都有自己的“canonical”，系统层面并不存在唯一 canonical model。

**统一建议**：

- 为每类跨边界对象只保留一个 source-of-truth model：`Request`、`RuntimeEvent`、`ToolCall`、`ToolResult`、`ExecutionStatus`。
- 其他形状都显式命名为 projection / transport adapter。

#### 问题 6：`interrupt` 概念混用了“停止流式输出”和“终止执行进程”

- runtime-event 把 `interrupt_ack` 定义为内部终点。见 `exec/contracts/runtime-event-contract.md:171-175`。
- execution-harness 指出当前无法终止运行中的同步 `docker exec`。见 `exec/contracts/execution-harness-contract.md:327-337`。

**矛盾本质**：runtime 可以确认“对话流停止”，但 execution backend 不能确认“进程已停止”。

**统一建议**：

- `interrupt_ack` 只能表示 runtime 已接受中断、不会继续产生该轮 model event。
- 若要表达后端进程真的被取消，必须另有 backend cancellation 状态或事件。
- 文档层先统一 wording：

```text
interrupt_ack MUST mean interruption accepted for conversation flow only.
It MUST NOT imply that an in-flight execution backend process has been terminated.
```

#### 问题 7：`tool_history` 与“消息历史中的 tool 结果”没有主从关系

- provider-request 说明 `tool_history` 当前基本失活。见 `exec/contracts/provider-request-contract.md:295-307`。
- execution-harness 和 runtime-event 都表明实际工具结果是通过 assistant/tool message 回灌并进入下一轮。见 `exec/contracts/execution-harness-contract.md:72-75`、`exec/contracts/runtime-event-contract.md:278-294`。

**统一建议**：

- 二选一：
  - 要么删掉 `tool_history`，把工具历史完全交给消息历史承载；
  - 要么把它升级为唯一 canonical tool-result summary，并保证每轮执行后更新。
- 在未决定前，不应把 `tool_history` 当成高谨慎兼容边界。

---

### 5.3 状态机与时序矛盾

#### 问题 8：runtime 声称可进入 `interrupted` 终态，但 execution backend 不能保证命令停下

- runtime 内部状态全集包含 `interrupted`。见 `exec/contracts/runtime-event-contract.md:178-194`。
- execution harness 当前不能 kill 正在运行的 subprocess。见 `exec/contracts/execution-harness-contract.md:327-337`。

**统一建议**：

- 把“会话流状态机”和“执行状态机”分开建模。
- `runtime_output.status="interrupted"` 只表示 conversation flow 被中断，不表示 execution backend 已取消。

#### 问题 9：provider capability 与 runtime event surface 之间没有协商 contract

- provider-request 明说当前只有 `supports_tool_calling` 真正被消费。见 `exec/contracts/provider-request-contract.md:97-105`。
- runtime-event 却定义了 `reasoning_delta`、`usage_updated`、`tool_call_argument_delta` 等事件面。见 `exec/contracts/runtime-event-contract.md:11-23`。

**统一建议**：

- capability 和 request flags 必须共同决定 event surface。
- 例如：
  - `supports_usage_in_stream=false` 时，`usage_updated` 不应出现；
  - `supports_thinking=false` 时，`reasoning_delta` 不应出现；
  - `supports_tool_call_delta=false` 时，`tool_call_argument_delta` 不应出现。

#### 问题 10：`message_completed` 只是“一轮模型消息完成”，不是“整个请求完成”

- runtime-event 已将其定义为“一轮模型消息完成”。见 `exec/contracts/runtime-event-contract.md:20-23`、`exec/contracts/runtime-event-contract.md:123-131`。
- execution-harness 和 provider-request 都说明后面还可能进入工具执行、工具结果回注和下一轮推理。见 `exec/contracts/provider-request-contract.md:207-219`、`exec/contracts/execution-harness-contract.md:44-75`。

**统一建议**：

- 文档必须明确：`message_completed` ≠ workflow completed。
- 若后续需要表达整轮请求真正结束，应使用单独 terminal event，例如 `turn_completed` 或 `workflow_completed`。

#### 问题 11：sandbox readiness 的 owner 分裂，导致“能启动”不等于“能执行”

- 启动期 owner 是 `LifecycleService`。见 `exec/contracts/execution-harness-contract.md:89-94`。
- 执行期 owner 是 `DockerExecutor`。见 `exec/contracts/execution-harness-contract.md:89-94`。
- 但 provider/request/runtime 文档都默认 tool 已可执行。见 `exec/contracts/provider-request-contract.md:152-187`、`exec/contracts/runtime-event-contract.md:266-298`。

**统一建议**：

- 可绑定工具暴露给 provider 之前，execution backend 必须已 ready；否则要么禁用 bindable tools，要么在 provider 调用前直接失败。

---

### 5.4 错误语义矛盾

#### 问题 12：runtime 期望结构化错误，execution backend 仍混用异常、结果对象、字符串

- runtime-event 的错误主路径是 `error_raised(payload={content, code})`。见 `exec/contracts/runtime-event-contract.md:211-230`。
- execution-harness 当前混用 `RuntimeError`、`ContainerManagerError`、`ImageBuildError`、`DockerClientError`、`ExecutionResult` 与裸字符串。见 `exec/contracts/execution-harness-contract.md:303-325`。

**统一建议**：

- execution backend 内部可以保留异常，但跨入 workflow/runtime 前必须统一折叠成一个结构化错误模型。
- runtime 层不应直接消费裸异常或 legacy string。

#### 问题 13：tool calling capability gate 有两处，未来易发生错误码漂移

- `ChatWorkflow` 做一次预检查。见 `exec/contracts/provider-request-contract.md:167-170`。
- `build_tool_kwargs()` 又做一次检查。见 `exec/contracts/provider-request-contract.md:171-179`。

**统一建议**：

- 每轮 capability validation 只能有一个 canonical gate；另一处最多做 assertion，不应再产生另一套用户可见错误契约。

#### 问题 14：失败工具调用何时升级为 `error_raised` 没有明确规则

- runtime 有 `tool_result.status`。见 `exec/contracts/runtime-event-contract.md:105-113`。
- runtime 同时也有 `error_raised.code`。见 `exec/contracts/runtime-event-contract.md:132-138`。
- execution-harness 又有更底层的 `ExecutionStatus`。见 `exec/contracts/execution-harness-contract.md:127-139`。

**统一建议**：

- 先约定：工具执行失败首先表现为 `tool_result.status != success`。
- 只有当 workflow 无法继续时，才升级为 `error_raised`。
- 该升级规则应明确写成 escalation matrix。

---

## 6. 遗漏的跨边界依赖

这部分不是“已有矛盾”，而是三份 spec 合起来仍未集中说明的缺口。

### 6.1 `RequestMetadata -> Provider metadata -> RuntimeEvent metadata -> ToolResult metadata` 的完整传播链缺失

- provider 文档写了 request metadata 与 provider `metadata`。见 `exec/contracts/provider-request-contract.md:143-151`。
- runtime 文档写了 `runtime_output.metadata`。见 `exec/contracts/runtime-event-contract.md:45-57`。
- execution harness 文档写了 `ExecutionResult.metadata` / `ToolResultPayload`。见 `exec/contracts/execution-harness-contract.md:129-139`、`exec/contracts/execution-harness-contract.md:143-163`。

**缺口**：没有一份文档把这条 correlation chain 端到端写完整。

### 6.2 request flags 与 event surface 的依赖缺失

- `enable_thinking`、`stream` 在 `RequestMetadata` 里存在。见 `exec/contracts/provider-request-contract.md:48-61`。
- 但 runtime 文档没有正式写清：这些 flags 如何约束 `reasoning_delta`、`content_delta`、`usage_updated` 等 event surface。见 `exec/contracts/runtime-event-contract.md:58-143`。

### 6.3 tool 生命周期缺少完整映射表

三份 spec 分别描述了 tool schema、tool call、execution result、tool result、tool message 回注，但没有一张统一映射表把这些对象串起来。

**建议**：后续补一张固定矩阵：

`ToolSchemaDefinition -> ProviderToolCall -> ToolInvocation -> ExecutionResult -> ToolResultEnvelope -> ModelToolMessage`

### 6.4 interrupt contract 缺少 execution backend cancel handle

- runtime 有 interrupt ack。见 `exec/contracts/runtime-event-contract.md:154-175`。
- execution backend 无运行中命令句柄。见 `exec/contracts/execution-harness-contract.md:327-337`。

**缺口**：用户看到了“中断已确认”，但系统没有可验证的 backend cancel contract。

### 6.5 sandbox readiness 与 tool exposure 的前置依赖没有集中写清

- provider/request 文档负责暴露 bindable tools。见 `exec/contracts/provider-request-contract.md:152-187`。
- execution-harness 文档说明 backend readiness 可能直到执行时才失败。见 `exec/contracts/execution-harness-contract.md:271-301`。

**缺口**：缺少“何时允许把工具暴露给模型”的统一前置条件说明。

### 6.6 `tool_result.content` 内嵌 JSON schema 未被正式声明

- runtime 文档只把它定义成 `content: str`。见 `exec/contracts/runtime-event-contract.md:105-113`。
- execution-harness 文档则说明实际模型回注是 `ToolResultPayload` 经过 `json.dumps()` 的字符串。见 `exec/contracts/execution-harness-contract.md:150-152`。

**缺口**：这是一条真实存在的跨边界依赖，但当前没有明确 schema 版本与字段保证。

---

## 7. 统一建议：建议先收口的 7 件事

按优先级排序：

1. **把 interrupt 语义拆成两层**：conversation interrupt 与 backend cancellation 分离。
2. **给 `tools` 拆名**：区分 `tool_context_snapshot` 与 `bindable_tools`。
3. **统一 `ToolCallEnvelope` / `ToolResultEnvelope`**：至少先在文档层统一一种 canonical shape。
4. **确立 `RequestMetadata` 为唯一 correlation source**。
5. **把 capability 与 event surface 正式绑定**：避免 runtime event 超前于 provider capability contract。
6. **统一 execution 错误折叠模型**：runtime 层只吃结构化错误，不吃异常/字符串。
7. **决定 `tool_history` 的去留**：删掉或升级，避免长期半死不活。

---

## 8. 建议的跨文档导航顺序

如果后续要继续推进 harness decoupling，我建议阅读顺序固定为：

1. `exec/harness-decoupling-plan.md`
   - 先看总原则、Phase 0、Phase 1、Phase 2、Phase 3、明确不做。见 `exec/harness-decoupling-plan.md:13-27`、`exec/harness-decoupling-plan.md:41-68`、`exec/harness-decoupling-plan.md:71-117`、`exec/harness-decoupling-plan.md:120-139`、`exec/harness-decoupling-plan.md:198-207`。
2. `exec/contracts/runtime-event-contract.md`
   - 先锁定 runtime output 和 bridge projection 边界。
3. `exec/contracts/provider-request-contract.md`
   - 再锁定请求、capability、tool binding 边界。
4. `exec/contracts/execution-harness-contract.md`
   - 最后锁定 execution backend seam 和 tool result 边界。

原因很简单：

- 先稳输出 contract，避免前端/bridge 语义漂移；
- 再稳输入 contract，避免 provider seam 漂移；
- 最后收 execution harness，避免在底层把接口再分裂一次。

---

## 9. 结论

这三份 spec 单独看都已经把本层问题讲清了一大半；真正缺的是**跨三层的统一闭环**。

当前最核心的结论有四条：

1. `RequestEnvelope`、`RuntimeEventResponse`、execution backend seam 已经分别形成了局部稳定边界，但三者之间还没有单一端到端 contract。
2. `tools`、`tool_call`、`tool_result`、`metadata`、`interrupt` 是当前跨文档最容易产生误解的几个对象。
3. compatibility boundary 应优先保护：`RuntimeEventType` 最小稳定集合、`RuntimeEventResponse` envelope、`StructuredRuntimeOutput`、`RequestEnvelope` 最小字段集、`supports_tool_calling`、bindable tool schema、execution backend 最小 seam。
4. 当前阶段的重点仍然应该是**先稳内核，再开插件点**，而不是把 `ChatWorkflow`、frontend state、`EventBus`、legacy wire 提前做成插件平台。见 `exec/harness-decoupling-plan.md:13-38`、`exec/harness-decoupling-plan.md:198-207`。
