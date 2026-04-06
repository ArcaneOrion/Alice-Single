# 历史文档：Agent 提示词集合（已过期）

> 状态：**历史材料，不再作为当前执行依据**
>
> 原因：本提示词集合绑定旧的 Phase 0-5 计划与旧文件所有权划分。经过 2026-04-05 审查，当前应改用短周期修复提示词：`exec/agent-prompts-short-cycle.md`。

# Agent 提示词集合

按波次排列，每个波次内的 agent 可同时启动。

---

## Wave 0：侦察（3 个终端并行）

---

### 终端 1 — Agent Alpha：Runtime Contract 侦察

```
你是 Agent Alpha，负责 Runtime & Bridge 层的 contract 侦察。

## 目标
分析当前代码中 runtime event、bridge protocol、legacy compatibility 的实际语义，输出一份 canonical contract spec。

## 你需要读取的文件
- backend/alice/application/dto/responses.py
- backend/alice/application/dto/requests.py
- backend/alice/application/runtime/models.py
- backend/alice/infrastructure/bridge/canonical_bridge.py
- backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py
- backend/alice/infrastructure/bridge/protocol/messages.py
- backend/alice/infrastructure/bridge/event_handlers/message_handler.py
- backend/alice/infrastructure/bridge/event_handlers/interrupt_handler.py
- backend/alice/infrastructure/bridge/stream_manager.py
- backend/alice/application/workflow/chat_workflow.py
- docs/protocols/bridge.md
- docs/reference/code-map-coupling.md

## 你需要产出的文件
写到 `exec/contracts/runtime-event-contract.md`，包含以下章节：

### 1. RuntimeEventType 最小稳定字段清单
列出所有 event type 枚举值，标注哪些是核心稳定的、哪些是 legacy 兼容的、哪些可以废弃。

### 2. StructuredRuntimeOutput payload 形状
每种 event type 对应的 payload 字段、类型、是否必填、语义说明。

### 3. Interrupt / Status / Error 语义定义
- interrupt 的触发来源、传播路径、最终处理点
- status 的状态机（有哪些状态、合法的状态转换）
- error 的分类与上报路径

### 4. Bridge 投影规则
- 内部 runtime event → legacy bridge message 的映射关系
- 哪些内部信息被丢弃、哪些被转换
- legacy serializer 当前承担的职责边界

### 5. Tool Call / Tool Result envelope
- tool_call 和 tool_result 在 event 流中的表示形式
- 当前是否有统一的 envelope 还是分散在多处

### 6. 发现的问题与建议
- 重复定义
- 语义模糊点
- 跨边界耦合风险

## 约束
- 只读代码，不改任何文件
- 产出前先创建 exec/contracts/ 目录
- 用中文写文档
- 每个结论必须标注代码证据（文件:行号）
- 如果发现与 exec/harness-decoupling-context.md 中描述不符的情况，明确指出
```

---

### 终端 2 — Agent Beta：Provider & Request Contract 侦察

```
你是 Agent Beta，负责 Provider & Request Envelope 层的 contract 侦察。

## 目标
分析当前代码中 provider capability、request envelope、tool binding 的实际语义，输出一份 canonical contract spec。

## 你需要读取的文件
- backend/alice/domain/llm/providers/base.py
- backend/alice/domain/llm/providers/openai_provider.py
- backend/alice/domain/llm/services/chat_service.py
- backend/alice/domain/llm/services/stream_service.py
- backend/alice/domain/llm/adapters/langchain_tool_calling_adapter.py
- backend/alice/domain/llm/models/message.py
- backend/alice/domain/llm/models/stream_chunk.py
- backend/alice/domain/llm/models/response.py
- backend/alice/application/agent/agent.py
- backend/alice/application/agent/react_loop.py
- backend/alice/application/runtime/models.py（重点看 RequestEnvelope）
- backend/alice/application/workflow/chat_workflow.py（重点看 request construction 与 tool binding 段）
- backend/alice/domain/execution/models/tool_calling.py

## 你需要产出的文件
写到 `exec/contracts/provider-request-contract.md`，包含以下章节：

### 1. RequestEnvelope 最小字段集
列出所有字段、类型、是否必填、语义说明。标注哪些字段由 agent 层填充、哪些由 workflow 层填充。

### 2. ProviderCapability 语义定义
- 当前 ProviderCapability 的所有字段与语义
- 唯一判断来源（frozen dataclass 还是环境变量覆盖？）
- 是否存在其他地方绕过 capability 做判断的代码

### 3. Provider 消费/忽略字段矩阵
RequestEnvelope 中的每个字段，标注：
- provider 是否消费
- provider 是否允许消费
- 应该由谁填充

### 4. Tool Binding 规则
- tool binding 发生在哪一层（workflow? stream_service? chat_service?）
- 判断是否 bind tools 的逻辑链路
- 是否存在 provider 私有分支（不通过 capability 的硬编码判断）

### 5. Provider 调用链路
从 agent.py → workflow → chat_service → stream_service → provider 的完整调用链路，标注每一层的职责。

### 6. 发现的问题与建议
- capability 绕过
- 字段职责模糊
- provider 间不一致的行为

## 约束
- 只读代码，不改任何文件
- 产出前先创建 exec/contracts/ 目录（如已存在则跳过）
- 用中文写文档
- 每个结论必须标注代码证据（文件:行号）
- 重点关注 MEMORY.md 中提到的 Phase 4 已完成的 ProviderCapability 改动
```

---

### 终端 3 — Agent Gamma：Execution Harness 侦察

```
你是 Agent Gamma，负责 Execution Harness 层的 contract 侦察。

## 目标
分析当前代码中 Docker 执行、容器生命周期、tool registry 的实际实现，输出一份 contract spec，重点盘清三处容器初始化重复的职责交叉。

## 你需要读取的文件
- backend/alice/application/services/lifecycle_service.py
- backend/alice/domain/execution/executors/docker_executor.py
- backend/alice/domain/execution/executors/base.py
- backend/alice/infrastructure/docker/container_manager.py
- backend/alice/infrastructure/docker/image_builder.py
- backend/alice/infrastructure/docker/client.py
- backend/alice/infrastructure/docker/config.py
- backend/alice/domain/execution/services/tool_registry.py
- backend/alice/domain/execution/services/execution_service.py
- backend/alice/domain/execution/models/tool_calling.py
- backend/alice/domain/execution/models/execution_result.py
- backend/alice/domain/execution/models/command.py
- backend/alice/core/interfaces/command_executor.py

## 你需要产出的文件
写到 `exec/contracts/execution-harness-contract.md`，包含以下章节：

### 1. 三处初始化重复的职责交叉矩阵
对 LifecycleService、DockerExecutor、ContainerManager 列出：

| 职责 | LifecycleService | DockerExecutor | ContainerManager |
|------|------------------|----------------|------------------|
| 容器创建 | ? | ? | ? |
| 镜像构建 | ? | ? | ? |
| 健康检查 | ? | ? | ? |
| ensure_running | ? | ? | ? |
| 容器清理 | ? | ? | ? |
| 命令执行 | ? | ? | ? |

标注每个格子的具体方法名和行号。

### 2. 调用链路图
从 workflow/agent 发起执行 → 到容器内实际运行命令的完整链路，标注每一层的进出接口。

### 3. Tool Schema / Tool Result 统一出口
- tool_registry 如何注册和查找 tool
- tool_calling.py 中的 schema 定义
- execution_result.py 中的结果定义
- 是否有统一的 envelope 还是分散表示

### 4. Sandbox Provider Seam 最小接口设计建议
基于职责分析，建议统一后的 execution backend 应该暴露哪些方法：
- 最小方法集
- 每个方法的输入/输出类型
- 哪些职责应该内聚到 backend 内部

### 5. 发现的问题与建议
- 职责交叉的具体风险
- 不一致的错误处理
- 资源泄漏风险

## 约束
- 只读代码，不改任何文件
- 产出前先创建 exec/contracts/ 目录（如已存在则跳过）
- 用中文写文档
- 每个结论必须标注代码证据（文件:行号）
```

---

## Wave 0 汇合：主 Agent 审查

Wave 0 三个 agent 全部完成后，回到主终端执行：

```
三个侦察 agent 已完成 contract spec 产出：
- exec/contracts/runtime-event-contract.md
- exec/contracts/provider-request-contract.md
- exec/contracts/execution-harness-contract.md

请做以下交叉审查：

1. 读取三份 contract spec
2. 检查三份 spec 之间是否有矛盾（例如 tool call envelope 在 runtime spec 和 provider spec 中的描述是否一致）
3. 检查是否存在遗漏的跨边界依赖
4. 生成 exec/contracts/README.md，包含：
   - 三份 spec 的索引与摘要
   - compatibility boundary 清单（哪些接口是兼容边界、变更需谨慎）
   - 非目标清单（当前不插件化的层，从 exec/harness-decoupling-plan.md "明确不做" 章节提取）
   - 交叉审查中发现的问题与解决建议
5. 如有矛盾，指出矛盾并给出统一建议

用中文写文档。
```

---

## Wave 1：代码改动（2 个终端并行）

---

### 终端 1 — Agent Alpha：Phase 1 收口 canonical runtime contract

```
你是 Agent Alpha，负责执行 Phase 1：收口 canonical runtime contract。

## 背景
请先读取以下文档理解上下文：
- exec/harness-decoupling-plan.md（Phase 1 章节）
- exec/contracts/runtime-event-contract.md（你在 Wave 0 产出的 spec）
- exec/contracts/README.md（交叉审查结论）

## 你拥有的文件（只允许修改这些）
- backend/alice/application/dto/responses.py
- backend/alice/application/dto/requests.py
- backend/alice/application/dto/__init__.py
- backend/alice/infrastructure/bridge/canonical_bridge.py
- backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py
- backend/alice/infrastructure/bridge/protocol/messages.py
- backend/alice/infrastructure/bridge/protocol/codec.py
- backend/alice/infrastructure/bridge/event_handlers/message_handler.py
- backend/alice/infrastructure/bridge/event_handlers/interrupt_handler.py
- backend/alice/infrastructure/bridge/stream_manager.py
- backend/alice/infrastructure/bridge/server.py
- backend/alice/application/workflow/chat_workflow.py（仅 event emission 相关代码）

## 不允许修改的文件
- backend/alice/domain/llm/**（属于 Agent Beta）
- backend/alice/domain/execution/**（属于 Agent Gamma）
- backend/alice/infrastructure/docker/**（属于 Agent Gamma）
- backend/alice/application/agent/**（属于 Agent Beta）

## 任务
1. 收敛 RuntimeEventType 与 payload 形状到 contract spec 定义
   - 确保 event type 枚举值与 spec 一致
   - payload 字段名、类型、必填性与 spec 一致
2. 清理 bridge/runtime 重复语义
   - 如果 bridge 层和 dto 层有重复的 event 类型定义，统一到 dto 层
3. 统一 interrupt / status / message_completed / error 内部语义
   - 按 spec 中定义的状态机修正
4. 确保 legacy serializer 只做投影，不扩展新能力
   - 如果 serializer 中有超出 "compatibility adapter" 角色的逻辑，迁出
5. 为 tool call / tool result 形成最小标准 envelope
   - 按 spec 统一表示形式

## 工作方式
- 改代码前先对要改的点写测试或找到现有测试
- 改完后运行相同测试确认不退化
- 每个改动点提交一个 commit，commit message 说明改了什么

## 验收
改完后运行：
```bash
python -m pytest backend/tests/ -v
```
报告测试结果。如果有测试失败，分析原因并修复。

## 完成后
在 exec/progress.md 追加记录：
```
## Wave 1 - Agent Alpha - Phase 1
- 状态：完成
- 日期：[当前日期]
- 改动文件列表
- 测试结果摘要
- 遗留问题（如有）
```

用中文写文档和 commit message。
```

---

### 终端 2 — Agent Gamma：Phase 3 收口 execution harness

```
你是 Agent Gamma，负责执行 Phase 3：收口 execution harness。

## 背景
请先读取以下文档理解上下文：
- exec/harness-decoupling-plan.md（Phase 3 章节）
- exec/contracts/execution-harness-contract.md（你在 Wave 0 产出的 spec）
- exec/contracts/README.md（交叉审查结论）

## 你拥有的文件（只允许修改这些）
- backend/alice/application/services/lifecycle_service.py
- backend/alice/domain/execution/executors/docker_executor.py
- backend/alice/domain/execution/executors/base.py
- backend/alice/domain/execution/executors/__init__.py
- backend/alice/domain/execution/services/execution_service.py
- backend/alice/domain/execution/models/execution_result.py
- backend/alice/domain/execution/models/command.py
- backend/alice/infrastructure/docker/container_manager.py
- backend/alice/infrastructure/docker/image_builder.py
- backend/alice/infrastructure/docker/client.py
- backend/alice/infrastructure/docker/config.py
- backend/alice/infrastructure/docker/__init__.py

## 不允许修改的文件
- backend/alice/application/dto/**（属于 Agent Alpha）
- backend/alice/infrastructure/bridge/**（属于 Agent Alpha）
- backend/alice/domain/llm/**（属于 Agent Beta）
- backend/alice/application/workflow/**（属于 Agent Alpha/Beta）
- backend/alice/application/agent/**（属于 Agent Beta）
- backend/alice/core/**（属于 Agent Delta，Phase 4）

## 任务
1. 盘点 LifecycleService、DockerExecutor、ContainerManager 的职责交叉
   - 对照 spec 中的职责矩阵，确认实际代码
2. 设计单一 execution backend / sandbox provider seam
   - 按 spec 建议的最小接口，收口为一个统一的 ExecutionBackend
3. 收口生命周期初始化
   - 容器创建、镜像构建、健康检查、ensure_running 只有一条路径
4. 收口命令执行
   - application/domain 不再各自持有承载初始化逻辑
5. 保持对外接口兼容
   - orchestration_service 和 workflow 调用 execution 的方式不能破坏性变更
   - 如需调整调用方式，在 exec/handoff/gamma-to-delta.md 记录，留给 Phase 4

## 工作方式
- 改代码前先对要改的点写测试或找到现有测试
- 改完后运行相同测试确认不退化
- 每个改动点提交一个 commit，commit message 说明改了什么

## 验收
改完后运行：
```bash
python -m pytest backend/tests/ -v
```
以及手动验证：
```bash
docker ps -a --filter name=alice-sandbox-instance
```
报告测试结果。

## 完成后
在 exec/progress.md 追加记录：
```
## Wave 1 - Agent Gamma - Phase 3
- 状态：完成
- 日期：[当前日期]
- 改动文件列表
- 测试结果摘要
- 对外接口变更说明（如有）
- 遗留问题（如有）
```

用中文写文档和 commit message。
```

---

## Wave 2：代码改动（1 个终端）

---

### 终端 1 — Agent Beta：Phase 2 收口 Request Envelope & Provider Contract

```
你是 Agent Beta，负责执行 Phase 2：收口 Request Envelope & Provider Contract。

## 前置条件
Phase 1（Agent Alpha）已完成并 merge。请先确认：
1. git log 中有 Phase 1 的 commit
2. 读取 exec/progress.md 确认 Alpha 已完成

## 背景
请先读取以下文档理解上下文：
- exec/harness-decoupling-plan.md（Phase 2 章节）
- exec/contracts/provider-request-contract.md（你在 Wave 0 产出的 spec）
- exec/contracts/README.md（交叉审查结论）
- exec/progress.md（Phase 1 的改动记录，了解 event 类型变更）

## 你拥有的文件（只允许修改这些）
- backend/alice/application/runtime/models.py
- backend/alice/application/runtime/runtime_context_builder.py
- backend/alice/application/agent/agent.py
- backend/alice/application/agent/react_loop.py
- backend/alice/domain/llm/providers/base.py
- backend/alice/domain/llm/providers/openai_provider.py
- backend/alice/domain/llm/services/chat_service.py
- backend/alice/domain/llm/services/stream_service.py
- backend/alice/domain/llm/adapters/langchain_tool_calling_adapter.py
- backend/alice/domain/llm/models/message.py
- backend/alice/domain/llm/models/stream_chunk.py
- backend/alice/domain/llm/models/response.py
- backend/alice/domain/llm/parsers/stream_parser.py
- backend/alice/application/workflow/chat_workflow.py（仅 request construction 与 tool binding 相关代码）

## 不允许修改的文件
- backend/alice/application/dto/**（Phase 1 已稳定）
- backend/alice/infrastructure/bridge/**（Phase 1 已稳定）
- backend/alice/domain/execution/**（Phase 3 已稳定或属于 Gamma）
- backend/alice/infrastructure/docker/**（Phase 3 已稳定或属于 Gamma）
- backend/alice/core/**（属于 Agent Delta，Phase 4）

## 任务
1. 固定 RequestEnvelope 字段与构建责任边界
   - 按 spec 明确哪些字段由 agent 层填充、哪些由 workflow 层填充
   - 移除或标记 deprecated 的字段
2. 固定 provider 允许消费 / 必须忽略的字段
   - provider 实现中如果读取了不该读的字段，修正
3. 固定 supports_tool_calling 等 capability 唯一判断来源
   - 确保只通过 ProviderCapability frozen dataclass 判断
   - 消除任何绕过 capability 的硬编码判断
4. tool binding 逻辑只依赖 capability
   - 消除 provider 私有分支
   - tool binding 决策点收口到一处

## 工作方式
- 改代码前先对要改的点写测试或找到现有测试
- 改完后运行相同测试确认不退化
- 每个改动点提交一个 commit，commit message 说明改了什么

## 验收
改完后运行：
```bash
python -m pytest backend/tests/ -v
```
报告测试结果。

## 完成后
在 exec/progress.md 追加记录：
```
## Wave 2 - Agent Beta - Phase 2
- 状态：完成
- 日期：[当前日期]
- 改动文件列表
- 测试结果摘要
- 遗留问题（如有）
```

用中文写文档和 commit message。
```

---

## Wave 3：代码改动（1 个终端）

---

### 终端 1 — Agent Delta：Phase 4 开放叶子插件点

```
你是 Agent Delta，负责执行 Phase 4：开放叶子插件点。

## 前置条件
Phase 1、2、3 均已完成并 merge。请先确认：
1. 读取 exec/progress.md 确认所有前置 phase 已完成
2. 读取三份 contract spec 了解已稳定的接口

## 背景
请先读取以下文档理解上下文：
- exec/harness-decoupling-plan.md（Phase 4 章节）
- exec/contracts/README.md
- exec/contracts/runtime-event-contract.md
- exec/contracts/provider-request-contract.md
- exec/contracts/execution-harness-contract.md
- exec/progress.md

如有 handoff 文件（exec/handoff/），也需读取。

## 你拥有的文件（只允许修改这些）
- backend/alice/application/services/orchestration_service.py
- backend/alice/cli/main.py
- backend/alice/core/registry/__init__.py
- backend/alice/core/registry/memory_registry.py
- backend/alice/core/registry/skill_registry.py
- backend/alice/core/registry/command_registry.py
- backend/alice/core/registry/llm_registry.py
- backend/alice/core/interfaces/__init__.py
- backend/alice/core/interfaces/command_executor.py
- backend/alice/core/interfaces/llm_provider.py
- backend/alice/core/interfaces/memory_store.py
- backend/alice/core/interfaces/skill_loader.py
- backend/alice/domain/execution/services/tool_registry.py

## 任务
1. composition root 通过 registry/factory 选择实现
   - orchestration_service 和 cli/main.py 中的硬编码具体类 → 通过 registry 获取
2. 开放 provider adapter 注册边界
   - llm_registry 提供注册/获取 provider 的统一方式
   - 新增 provider 时只需注册，不改 workflow
3. 开放 tool/skill source 注册边界
   - tool_registry 和 skill_registry 提供统一的注册接口
4. harness backend 替换收敛到统一入口
   - command_executor interface 成为真正的替换边界
   - 对接 Phase 3 收口后的 execution backend

## 工作方式
- 改代码前先对要改的点写测试或找到现有测试
- 改完后运行相同测试确认不退化
- 保持改动最小化，不做过度抽象
- 每个改动点提交一个 commit

## 验收
```bash
python -m pytest backend/tests/ -v
```
额外验证：
- 确认更换具体实现时，主要改 composition root，不改 workflow
- 确认抽象真正成为可替换装配边界

## 完成后
在 exec/progress.md 追加记录：
```
## Wave 3 - Agent Delta - Phase 4
- 状态：完成
- 日期：[当前日期]
- 改动文件列表
- 新增的注册/工厂接口清单
- 测试结果摘要
- 遗留问题（如有）
```

用中文写文档和 commit message。
```

---

## Wave 4：代码改动（1 个终端）

---

### 终端 1 — Agent Epsilon：Phase 5 新增 remote gateway

```
你是 Agent Epsilon，负责执行 Phase 5：新增 remote gateway。

## 前置条件
Phase 1-4 均已完成并 merge。请先确认：
1. 读取 exec/progress.md 确认所有前置 phase 已完成
2. 读取所有 contract spec 和 progress 记录

## 背景
请先读取以下文档理解上下文：
- exec/harness-decoupling-plan.md（Phase 5 章节）
- exec/harness-decoupling-context.md（第五节：关于 websocket/gateway 的结论）
- exec/contracts/README.md
- exec/contracts/runtime-event-contract.md
- docs/protocols/bridge.md

## 你的文件范围
主要是新增文件：
- backend/alice/infrastructure/gateway/（新目录，自由创建）
- 可能需要在 backend/alice/cli/main.py 添加 gateway 启动入口（与 Delta 协调）

只读参考（不修改）：
- backend/alice/infrastructure/bridge/（理解现有 bridge 模式）
- frontend/src/bridge/transport/stdio_transport.rs（理解现有 transport）

## 任务
1. 设计并实现 gateway 层
   - websocket 承载双向消息与流式事件
   - 消费 canonical runtime event，向远程客户端投影协议
2. 最小能力集合
   - session_id
   - request_id
   - 鉴权与授权（最小实现，如 token）
   - 中断目标路由
   - 慢消费者处理（backpressure）
   - reconnect / replay
3. 不破坏本地 TUI
   - 本地 TUI 继续沿用现有 bridge compatibility path
   - gateway 是独立的接入层

## 工作方式
- 先设计接口，写到 exec/design/gateway-interface.md
- 等确认设计合理后再实现
- 用最小实现验证，不做完整产品化
- 每个功能点提交一个 commit

## 验收
```bash
python -m pytest backend/tests/ -v
```
额外验证：
- 本地 TUI 功能不退化（cd frontend && cargo run --release 可正常启动）
- gateway 可独立启动并接受 websocket 连接
- 远程客户端接入不改 workflow 核心语义

## 完成后
在 exec/progress.md 追加记录：
```
## Wave 4 - Agent Epsilon - Phase 5
- 状态：完成
- 日期：[当前日期]
- 新增文件列表
- gateway 接口文档位置
- 测试结果摘要
- 遗留问题（如有）
```

用中文写文档和 commit message。
```

---

## 速查：终端分配

| 波次 | 终端数 | 终端 1 | 终端 2 | 终端 3 |
|------|--------|--------|--------|--------|
| Wave 0 | 3 | Alpha 侦察 | Beta 侦察 | Gamma 侦察 |
| 汇合 | 1 | 主 agent 审查 | - | - |
| Wave 1 | 2 | Alpha Phase 1 | Gamma Phase 3 | - |
| Wave 2 | 1 | Beta Phase 2 | - | - |
| Wave 3 | 1 | Delta Phase 4 | - | - |
| Wave 4 | 1 | Epsilon Phase 5 | - | - |
