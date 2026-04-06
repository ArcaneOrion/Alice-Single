# 历史文档：并行执行计划（已过期）

> 状态：**历史材料，不再作为当前执行依据**
>
> 原因：本计划基于旧的 Phase 0-5 执行叙事与旧 handoff 前提；经过 2026-04-05 审查，已确认其中部分“已完成”状态、边界划分和依赖关系与当前代码树不完全一致。当前请改用：
> - `exec/audit-baseline-current-tree.md`
> - `exec/short-cycle-repair-plan.md`
> - `exec/ownership-matrix.md`
> - `exec/agent-prompts-short-cycle.md`

# 并行执行计划：按架构边界拆分 Agent 任务

## 核心约束

1. **文件所有权不重叠** — 同一波次中，两个 agent 不能同时写同一个文件
2. **依赖顺序** — 下游 agent 必须等上游产出稳定后再开始
3. **每个 agent 上下文最小化** — 只读自己负责的文件区域 + 上游产出的 contract spec

---

## 文件归属分析

通过扫描 Phase 0-5 涉及的文件，识别出三条独立的架构流：

| 架构流 | 文件范围 | 对应 Phase |
|--------|----------|------------|
| **A: Runtime & Bridge** | `dto/`, `runtime/`, `infrastructure/bridge/`, `workflow/chat_workflow.py` | Phase 0a + 1 |
| **B: Provider & LLM** | `domain/llm/`, `application/agent/`, `workflow/chat_workflow.py` | Phase 0b + 2 |
| **C: Execution Harness** | `domain/execution/executors/`, `infrastructure/docker/`, `application/services/lifecycle_service.py` | Phase 0c + 3 |
| **D: Plugin Points** | `core/registry/`, `core/interfaces/`, `cli/main.py`, `orchestration_service.py` | Phase 4 |
| **E: Gateway** | 新增文件为主 | Phase 5 |

### 冲突文件

`chat_workflow.py` 同时被 Stream A（Phase 1: event emission）和 Stream B（Phase 2: request construction）触及。
`stream_service.py` 在 `domain/llm/` 中，但 Phase 1 也涉及。

**解决方式**：Stream A 拥有 `chat_workflow.py` 和 bridge 侧文件；Stream B 拥有 `domain/llm/**` 和 `agent/`。Phase 2 对 `chat_workflow.py` 的修改排在 Phase 1 之后。

---

## 执行波次

### Wave 0：Phase 0 — 定义不动点（3 个 agent 并行，只读分析）

所有 agent 只读代码、输出 contract spec 文档，不改代码。可完全并行。

#### Agent Alpha — Runtime Contract 侦察

```
读取范围：
  - backend/alice/application/dto/responses.py
  - backend/alice/application/runtime/models.py
  - backend/alice/infrastructure/bridge/canonical_bridge.py
  - backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py
  - backend/alice/infrastructure/bridge/protocol/messages.py
  - backend/alice/application/workflow/chat_workflow.py

产出：
  exec/contracts/runtime-event-contract.md
  - RuntimeEventType 最小稳定字段清单
  - StructuredRuntimeOutput payload 形状
  - interrupt / status / error 语义定义
  - legacy serializer 角色定位（仅 compatibility adapter）
```

#### Agent Beta — Provider & Request Contract 侦察

```
读取范围：
  - backend/alice/domain/llm/providers/base.py
  - backend/alice/domain/llm/providers/openai_provider.py
  - backend/alice/domain/llm/services/chat_service.py
  - backend/alice/domain/llm/services/stream_service.py
  - backend/alice/application/agent/agent.py
  - backend/alice/application/runtime/models.py (RequestEnvelope)

产出：
  exec/contracts/provider-request-contract.md
  - RequestEnvelope 最小字段集
  - ProviderCapability 唯一语义来源
  - provider 允许消费 / 必须忽略的字段
  - tool binding 依赖 capability 的判断规则
```

#### Agent Gamma — Execution Harness 侦察

```
读取范围：
  - backend/alice/application/services/lifecycle_service.py
  - backend/alice/domain/execution/executors/docker_executor.py
  - backend/alice/infrastructure/docker/container_manager.py
  - backend/alice/domain/execution/services/tool_registry.py
  - backend/alice/domain/execution/services/execution_service.py
  - backend/alice/core/interfaces/command_executor.py

产出：
  exec/contracts/execution-harness-contract.md
  - 三处初始化重复的具体职责交叉矩阵
  - tool schema / tool result 统一出口定义
  - sandbox provider seam 最小接口
```

#### Wave 0 汇合检查点

三份 contract spec 产出后，主 agent 做一次交叉审查：
- 三份 spec 之间有无矛盾
- 是否存在遗漏的跨边界依赖
- 确认 compatibility boundary 清单和非目标清单

产出：`exec/contracts/README.md`（合并索引 + 非目标清单）

---

### Wave 1：Phase 1 + Phase 3 并行（2 个 agent，零文件重叠）

#### Agent Alpha — Phase 1: 收口 canonical runtime contract

```
拥有文件（可写）：
  - backend/alice/application/dto/responses.py
  - backend/alice/infrastructure/bridge/canonical_bridge.py
  - backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py
  - backend/alice/infrastructure/bridge/protocol/messages.py
  - backend/alice/infrastructure/bridge/event_handlers/
  - backend/alice/infrastructure/bridge/stream_manager.py
  - backend/alice/application/workflow/chat_workflow.py  ← event emission 侧

输入依赖：
  - exec/contracts/runtime-event-contract.md

任务：
  1. 收敛 RuntimeEventType 与 payload 形状到 contract spec 定义
  2. 清理 bridge/runtime 重复语义
  3. 统一 interrupt / status / message_completed / error 内部语义
  4. 确保 legacy serializer 只做投影，不扩展新能力
  5. 为 tool call / tool result 形成最小标准 envelope

验收：
  - python -m pytest backend/tests/ -k "bridge or runtime or event"
  - workflow/provider/logging/bridge 围绕同一套 event 语义
```

#### Agent Gamma — Phase 3: 收口 execution harness

```
拥有文件（可写）：
  - backend/alice/application/services/lifecycle_service.py
  - backend/alice/domain/execution/executors/docker_executor.py
  - backend/alice/infrastructure/docker/container_manager.py
  - backend/alice/infrastructure/docker/image_builder.py
  - backend/alice/infrastructure/docker/client.py
  - backend/alice/infrastructure/docker/config.py
  - backend/alice/domain/execution/executors/base.py

输入依赖：
  - exec/contracts/execution-harness-contract.md

任务：
  1. 合并三处容器初始化逻辑到单一 execution backend seam
  2. 收口生命周期初始化、健康检查、ensure_running
  3. application/domain 不再各自持有承载初始化逻辑
  4. 定义 sandbox provider interface，让切换 harness 只替换一处

验收：
  - python -m pytest backend/tests/ -k "docker or execution or lifecycle"
  - docker ps -a --filter name=alice-sandbox-instance 行为不变
  - 只有一条初始化路径
```

---

### Wave 2：Phase 2（1 个 agent，依赖 Wave 1 Alpha 完成）

#### Agent Beta — Phase 2: 收口 Request Envelope & Provider Contract

```
拥有文件（可写）：
  - backend/alice/application/runtime/models.py
  - backend/alice/application/agent/agent.py
  - backend/alice/domain/llm/providers/base.py
  - backend/alice/domain/llm/providers/openai_provider.py
  - backend/alice/domain/llm/services/chat_service.py
  - backend/alice/domain/llm/services/stream_service.py
  - backend/alice/domain/llm/adapters/langchain_tool_calling_adapter.py
  - backend/alice/application/workflow/chat_workflow.py  ← request construction 侧

输入依赖：
  - exec/contracts/provider-request-contract.md
  - Wave 1 Alpha 产出的稳定 event 类型（已 merge）

任务：
  1. 固定 RequestEnvelope 字段与构建责任边界
  2. 固定 provider 允许消费 / 必须忽略的字段
  3. 固定 supports_tool_calling 等 capability 唯一判断来源
  4. tool binding 逻辑只依赖 capability，消除 provider 私有分支

验收：
  - python -m pytest backend/tests/ -k "provider or stream or chat"
  - 新增 provider 时不需要改 workflow 主语义
```

---

### Wave 3：Phase 4（1-2 个 agent，依赖 Wave 1-2 完成）

#### Agent Delta — Phase 4: 开放叶子插件点

```
拥有文件（可写）：
  - backend/alice/application/services/orchestration_service.py
  - backend/alice/cli/main.py
  - backend/alice/core/registry/*.py
  - backend/alice/core/interfaces/*.py
  - backend/alice/domain/execution/services/tool_registry.py

输入依赖：
  - Wave 1-2 产出的稳定 contract
  - Wave 1 Gamma 产出的 sandbox provider interface

任务：
  1. composition root 通过 registry/factory 选择实现
  2. 开放 provider adapter 注册边界
  3. 开放 tool/skill source 注册边界
  4. harness backend 替换收敛到统一入口

验收：
  - python -m pytest backend/tests/
  - 更换实现主要改 composition root，不改 workflow
```

---

### Wave 4：Phase 5（1 个 agent，依赖 Wave 3 完成）

#### Agent Epsilon — Phase 5: 新增 remote gateway

```
新增文件（主要）：
  - backend/alice/infrastructure/gateway/  （新目录）
  - 可能新增 frontend/src/bridge/transport/websocket_transport.rs

输入依赖：
  - 全部已稳定的 canonical contract
  - Phase 4 的 transport adapter 注册边界

任务：
  1. 新增 gateway 层，websocket 承载双向消息与流式事件
  2. 引入 session_id, request_id, auth, routing
  3. reconnect / replay / backpressure
  4. 本地 TUI 继续沿用现有 bridge compatibility path

验收：
  - 本地 TUI 功能不退化
  - 远程客户端接入不改 workflow 核心语义
```

---

## 并行度总览

```
时间轴 →

Wave 0:  [Alpha 侦察] [Beta 侦察] [Gamma 侦察]   ← 3 并行
            ↓              ↓             ↓
         ── 汇合审查 ──────────────────────
            ↓                             ↓
Wave 1:  [Alpha: Phase 1]          [Gamma: Phase 3]  ← 2 并行
            ↓
Wave 2:  [Beta: Phase 2]                              ← 1 串行
            ↓              ↓
Wave 3:  [Delta: Phase 4]                             ← 1 串行
            ↓
Wave 4:  [Epsilon: Phase 5]                           ← 1 串行
```

最大并行度 = 3（Wave 0），稳态并行度 = 2（Wave 1）。

---

## 实操：多终端执行方式

每个终端窗口启动一个 claude code 实例，prompt 模板：

```
你是 Agent [Alpha/Beta/Gamma/...]，负责 [具体职责]。

你的文件所有权范围：
[列出可写文件]

你的输入依赖：
[列出需要先读取的 contract spec]

你的任务：
[从上面对应 agent 的任务清单复制]

你的验收标准：
[从上面对应 agent 的验收标准复制]

约束：
- 只修改你拥有的文件，不要修改其他文件
- 产出物写到 exec/ 目录下对应位置
- 完成后运行验收测试并报告结果
```

---

## Wave 间的同步机制

1. **Wave 0 → Wave 1**：三份 contract spec 都就绪 + 主 agent 审查通过后，开始 Wave 1
2. **Wave 1 → Wave 2**：Alpha 的 Phase 1 代码 merge 到 main 后，Beta 开始 Phase 2
3. **Wave 2 → Wave 3**：Phase 2 merge 后，Delta 开始 Phase 4
4. **同步标志**：每个 agent 完成后在 `exec/progress.md` 追加完成记录

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| chat_workflow.py 被两个 phase 修改 | Phase 1 只改 event emission 侧，Phase 2 只改 request construction 侧；Phase 2 在 Phase 1 merge 后才开始 |
| Wave 0 侦察结论不一致 | 主 agent 在汇合点做交叉审查 |
| 测试覆盖不足导致 merge 后回归 | 每个 wave 完成后跑全量 `python -m pytest backend/tests/` |
| agent 上下文溢出 | 每个 agent 只读自己区域的文件，contract spec 作为跨边界知识的唯一传递媒介 |
