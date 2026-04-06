# Harness 解耦与插件化：背景与原因

## 目标
当前 Alice 的 harness/承载架构仍在早期，未来可能频繁调整。本文回答两个问题：

1. 为什么现在需要更强的解耦。
2. 为什么不能直接把整个系统做成全面插件化架构。

---

## 一、当前问题不是“缺少插件”，而是“变化会穿透整条链路”

从当前仓库真实主链看，变化最容易扩散的链路是：

- Rust TUI
- Bridge / legacy protocol
- application workflow
- provider / tool execution
- execution harness / container lifecycle

也就是说，当前最大的风险不是“功能不够可扩展”，而是：

> 某一层改动后，会同时牵动协议、前端状态、后端编排、日志与测试。

### 证据
- 主链与分层：`docs/architecture/overview.md:15-19`, `docs/architecture/overview.md:34-61`
- Bridge 协议与兼容边界：`docs/protocols/bridge.md:47-87`
- 高耦合面：`docs/reference/code-map-coupling.md:5-42`, `docs/reference/code-map-coupling.md:61-117`

---

## 二、为什么“解耦”现在是必要的

### 1. Bridge 兼容链是最脆弱的跨端耦合点
当前系统内部已经有 richer runtime event，但外部仍要投影回 legacy bridge message。

这意味着：
- 内部事件模型一变，serializer 要改。
- serializer 一变，前端 dispatcher 和状态流可能要改。
- 协议和日志校验也要跟着改。

### 证据
- 内部 runtime event：`backend/alice/application/dto/responses.py:41-55`
- canonical bridge model：`backend/alice/infrastructure/bridge/canonical_bridge.py:22-35`
- legacy compatibility serializer：`backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py:121-166`
- 前端 bridge message 与状态分发：`frontend/src/bridge/protocol/message.rs:28-55`, `frontend/src/core/dispatcher.rs:296-345`

### 2. Request Envelope / Runtime Context 已经在成为真正的内部契约
当前 provider 调用链已经不只是拼 prompt，而是在收敛统一请求载荷与运行时上下文。

这说明真正应该稳定的，是内部 canonical contract，而不是某个外部 transport 形态。

### 证据
- runtime models：`backend/alice/application/runtime/models.py:168-187`
- agent 入口挂载 runtime context / request envelope：`backend/alice/application/agent/agent.py:166-191`
- workflow 消费 request envelope：`backend/alice/application/workflow/chat_workflow.py:300-397`
- chat service 投影请求：`backend/alice/domain/llm/services/chat_service.py:301-368`

### 3. Execution harness 现在就是高耦合且重复实现的区域
项目当前已经明确存在三处容器初始化重复：
- `LifecycleService`
- `DockerExecutor`
- `ContainerManager`

这意味着运行承载还没有被收口为单一替换边界。以后若 sandbox/harness 形态变化，这里会成为爆炸点。

### 证据
- 项目约束：`CLAUDE.md:79-86`
- `backend/alice/application/services/lifecycle_service.py:132-161`
- `backend/alice/domain/execution/executors/docker_executor.py:278-297`
- `backend/alice/infrastructure/docker/container_manager.py:64-106`

---

## 三、为什么不能直接“全面插件化”

插件化只能解决“替换实现”，不能解决“核心语义仍在变化”。

如果下面这些内容还不稳定：
- runtime event 类型
- request envelope 字段
- tool/provider 调用约定
- interrupt / status 的统一语义

那么过早插件化只会把不稳定扩散成更多接口。

### 直接判断
当前更应该做的是：

> 先稳定内部 canonical contract，再把边缘适配点设计成可替换插件。

而不应该：

> 在 workflow、frontend state、EventBus、gateway 等核心且仍在变化的地方，提前建立插件系统。

---

## 四、哪些层最值得插件化，哪些最不值得

## 最值得插件化的层

### 1. Provider adapter
原因：外部 API 变化快，但内部能力语义可以稳定。

### 证据
- provider capability：`backend/alice/domain/llm/providers/base.py:261-295`
- stream service tool binding：`backend/alice/domain/llm/services/stream_service.py:149-191`

### 2. Tool / skill source
原因：天然多实现、多来源，且已有 registry/loader 雏形。

### 证据
- tool registry：`backend/alice/domain/execution/services/tool_registry.py:21-65`
- skill loader interface：`backend/alice/core/interfaces/skill_loader.py:39-65`

### 3. Execution harness / sandbox backend
原因：这是外部承载层，本来就应该被隔离。

### 4. 未来 remote transport / gateway adapter
原因：如果要扩展远程与多人，transport 接入层应该与 runtime 语义分开。

---

## 最不值得插件化的层

### 1. ChatWorkflow 核心编排语义
原因：这是系统的 canonical core，不应该在主语义未稳定前拆成插件。

### 证据
- `backend/alice/application/workflow/chat_workflow.py:242-397`

### 2. Frontend UI / state
原因：当前问题是协议与状态语义未完全收敛，不是前端缺插件点。

### 证据
- `frontend/src/app/state.rs:136-161`

### 3. EventBus / MessageQueue
原因：当前尚未成为真实主链，过早插件化只会制造第二套中心。

### 证据
- 项目约束：`CLAUDE.md:83-85`

### 4. Gateway interface
原因：当前仓库中真正稳定存在的边界还不是 gateway，而是 canonical event、request envelope、provider capability 与 legacy compatibility。

因此 gateway 现在更适合被当作未来演进方向，而不是立即固化为顶层插件接口。

---

## 五、关于 websocket / gateway 的结论

如果目标只是本地单用户 TUI：
- 继续使用当前直连 bridge/stdin 更合适。

如果目标包括远程接入与多人协作：
- websocket 是合适的传输方式。
- 但应该放在 gateway 层，而不是让客户端直接 websocket 连接 worker。

### 原因
因为多人/远程真正新增的是：
- session
- auth
- routing
- reconnect / replay
- backpressure
- presence

这些都属于接入层问题，不应该压进核心 runtime/workflow。

### 证据
- 当前本地子进程直连模型：`frontend/src/bridge/transport/stdio_transport.rs:126-142`
- 当前 CLI bridge 主循环：`backend/alice/cli/main.py:262-275`
- 当前中断仍是全局语义：`docs/protocols/bridge.md:130-134`

---

## 六、最终架构判断

当前 Alice 最需要的是：

- 稳定内核
- 收口边界
- 插件化叶子节点
- 延后插件化核心主链

换句话说：

> 先做“基于 canonical contract 的解耦”，再做“边缘适配点的插件化”。

这比“先设计一个完整插件平台”风险更低，也更符合当前项目阶段。
