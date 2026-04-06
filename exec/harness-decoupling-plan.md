# 历史/长期方向文档：Harness 解耦与插件化改动计划

> 状态：**保留为长期方向，不作为当前短周期执行计划**
>
> 说明：本文档的架构方向仍有参考价值，但当前执行请优先使用 `exec/short-cycle-repair-plan.md`。本轮先修复测试基线、execution harness seam、入口装配与 workflow/provider 契约漂移，再考虑继续推进长期 Phase 叙事。

# Harness 解耦与插件化：改动计划

## 计划目标
在不打断当前本地 TUI 主链的前提下，逐步实现：

1. 内部 contract 稳定。
2. 易变边界收口。
3. 边缘能力可替换。
4. 为远程接入与多人协作预留 gateway 演进路径。

---

## 总原则

### 原则 1：先稳内核，再开插件点
先稳定：
- canonical runtime event
- request envelope
- provider capability
- tool schema / tool result

再开放：
- provider adapter
- tool / skill source
- execution harness adapter
- remote transport / gateway adapter

### 原则 2：保留本地主链，新增远程侧边界
- 本地 TUI 继续直连。
- 远程与多人能力通过 gateway over websocket 演进。

### 原则 3：不在核心编排层过早抽象
暂不把以下层做成插件系统：
- `ChatWorkflow`
- frontend state / dispatcher
- `EventBus`
- legacy wire 本身

---

## Phase 0：定义不动点

## 目标
把当前阶段的“稳定核心”写清楚，避免之后边做边漂移。

## 输出物
- 一份 canonical contract 清单
- 一份 compatibility boundary 清单
- 一份非目标清单（当前不插件化的层）

## 要做的事
1. 明确 `RuntimeEventType` 与 `StructuredRuntimeOutput` 的最小稳定字段。
2. 明确 `RequestEnvelope` 最小字段集。
3. 明确 `ProviderCapability` 的唯一语义来源。
4. 明确 tool schema / tool result 的统一出口。
5. 明确 legacy serializer 只是 compatibility adapter，不再作为未来能力中心。

## 主要落点
- `backend/alice/application/dto/responses.py`
- `backend/alice/application/runtime/models.py`
- `backend/alice/domain/llm/providers/base.py`
- `backend/alice/domain/execution/services/tool_registry.py`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`

## 验收标准
- 团队可以明确回答“哪些 contract 允许变，哪些不允许随意变”。
- 后续 provider / bridge / gateway 讨论都以这套 contract 为基准。

---

## Phase 1：收口 canonical runtime contract

## 目标
把内部事件与请求语义收敛成真正可依赖的 canonical core。

## 要做的事
1. 收敛 runtime event 类型与 payload 形状。
2. 清理重复表达的 bridge/runtime 语义，避免多套近似模型继续分叉。
3. 统一 interrupt、status、message completed、error 的内部语义。
4. 为 tool call / tool result 形成最小标准 envelope。

## 主要落点
- `backend/alice/application/dto/responses.py`
- `backend/alice/infrastructure/bridge/canonical_bridge.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/stream_service.py`

## 验收标准
- workflow、provider、logging、bridge compatibility 都围绕同一套 event 语义工作。
- 新能力优先加在 canonical event，而不是直接扩 legacy 顶层消息类型。

---

## Phase 2：收口 Request Envelope 与 Provider Contract

## 目标
把“模型调用约定”从 workflow 细节中抽出来，形成稳定 provider seam。

## 要做的事
1. 固定 `RequestEnvelope` 的字段与构建责任边界。
2. 固定 provider 允许消费哪些字段，哪些字段必须忽略。
3. 固定 `supports_tool_calling` 等 capability 的唯一判断来源。
4. 保证 tool binding 逻辑只依赖 capability，而不是 provider 私有分支。

## 主要落点
- `backend/alice/application/runtime/models.py`
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/domain/llm/services/chat_service.py`
- `backend/alice/domain/llm/services/stream_service.py`
- `backend/alice/domain/llm/providers/base.py`
- `backend/alice/domain/llm/providers/openai_provider.py`

## 验收标准
- 新增 provider 时，不需要改动 workflow 主语义。
- provider 差异被压缩在 adapter/capability 层。

---

## Phase 3：把 execution harness 收口为单一替换边界

## 目标
解决当前最明显的承载耦合：Docker 初始化与执行链重复实现。

## 要做的事
1. 盘点 `LifecycleService`、`DockerExecutor`、`ContainerManager` 的职责交叉。
2. 收敛成单一 execution backend / sandbox provider seam。
3. 把生命周期初始化、健康检查、ensure running 等责任收口。
4. 让 application/domain 不再各自持有一套承载初始化逻辑。

## 主要落点
- `backend/alice/application/services/lifecycle_service.py`
- `backend/alice/domain/execution/executors/docker_executor.py`
- `backend/alice/infrastructure/docker/container_manager.py`

## 验收标准
- 切换或试验新的 sandbox/harness 时，只需要替换单一 adapter/provider。
- 不再出现三处重复初始化链路。

---

## Phase 4：只开放叶子插件点

## 目标
把真正值得替换的边界开放为插件/注册点，但不动核心工作流主语义。

## 优先开放顺序
1. provider adapter
2. tool / skill source
3. execution harness backend
4. transport adapter（条件成熟后）

## 要做的事
1. 让 composition root 通过 registry/factory 选择实现，而不是直接硬编码具体类。
2. 优先开放 provider 与 tool/skill 的注册边界。
3. 把 harness backend 的替换收敛到统一入口。

## 主要落点
- `backend/alice/application/services/orchestration_service.py`
- `backend/alice/cli/main.py`
- `backend/alice/core/registry/`
- `backend/alice/domain/execution/services/tool_registry.py`
- `backend/alice/core/interfaces/skill_loader.py`

## 验收标准
- 更换具体实现时，主要改 composition root，而不是改 workflow 内核。
- 抽象真正成为可替换装配边界，而不是名义接口。

---

## Phase 5：新增 remote gateway，而不是替换本地主链

## 目标
在不破坏当前 TUI 的情况下，为未来远程与多人能力建立独立接入层。

## 要做的事
1. 新增 gateway 层，负责远程客户端接入。
2. gateway 基于 websocket 承载双向消息与流式事件。
3. 引入 session、auth、routing、reconnect/replay、backpressure。
4. gateway 消费 canonical event，并向远程客户端投影专用协议。
5. 本地 TUI 暂时继续沿用现有 bridge compatibility path。

## 最小能力集合
- `session_id`
- `request_id`
- 鉴权与授权
- 中断目标路由
- 慢消费者处理
- reconnect / replay
- presence（若要多人协作）

## 验收标准
- 远程客户端接入不需要改 workflow 核心语义。
- 本地单用户体验不被 gateway 改造拖慢。

---

## 明确不做

当前阶段明确不做这些事：

1. 不把 `ChatWorkflow` 做成插件系统。
2. 不把 frontend state / dispatcher 做成插件架构。
3. 不围绕 `EventBus` 或 `MessageQueue` 提前做平台化。
4. 不把 legacy wire 当未来主协议继续扩展。
5. 不为了“可能有一天会需要”而先设计一整套通用 gateway/plugin framework。

---

## 推荐执行顺序

### 顺序
1. Phase 0：定义不动点
2. Phase 1：收口 canonical runtime contract
3. Phase 2：收口 Request Envelope / Provider Contract
4. Phase 3：收口 execution harness
5. Phase 4：开放叶子插件点
6. Phase 5：新增 remote gateway

### 原因
这个顺序的核心是：
- 先降低语义漂移
- 再降低实现耦合
- 最后扩外部接入能力

这样风险最低，也最符合当前项目“核心还在调整中”的现实。

---

## 每阶段的验证方式

### 文档验证
- 相关 contract 是否有唯一权威定义。
- 相关边界是否在 `docs/` 或 `exec/` 中有清晰说明。

### 代码验证
- 新增实现是否主要落在 adapter/registry/composition root。
- workflow 核心是否保持稳定。

### 测试验证
优先围绕以下方向补验证：
- canonical runtime event
- provider capability gate
- tool binding / tool result
- bridge compatibility projection
- execution harness lifecycle
- future gateway session routing（引入后）

---

## 最终目标

最终不是为了把 Alice 做成“什么都能插”的平台，而是为了做到：

- 内核稳定
- 边界清晰
- 试验成本低
- 架构调整不会穿透全栈
- 将来扩展远程与多人时，不必重写主工作流
