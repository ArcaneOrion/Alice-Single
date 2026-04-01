# Bridge 协议与状态流

本页描述 Rust frontend 与 Python backend 之间的 Bridge contract，以及这条链路在当前代码里的真实分层边界。

## 先记住当前默认运行链路

当前默认用户交互链路不是旧的 `backend/alice/infrastructure/bridge/server.py` 主循环，而是：

- `backend/alice/cli/main.py`
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/application/dto/responses.py`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`

也就是说，**当前主链路已经先在 application 层生成 canonical/structured runtime 响应，再按需要投影到冻结的 legacy wire JSON**。

旧的 `backend/alice/infrastructure/bridge/server.py`、`event_handlers/message_handler.py`、`stream_manager.py` 仍然是历史兼容资产和局部复用点，但不是本轮 backend-only 变更的默认运行入口。

## 为什么它高风险

Bridge 是双端契约。

只要你改了下面任一内容，就不能只改单边：
- 消息类型
- 字段名
- 字段语义
- 状态值
- 中断信号
- JSON Lines 编码/解码方式

## 线级 contract

权威 schema 在：

- `protocols/bridge_schema.json`

这是 Rust frontend 仍然消费的**冻结外部协议**。如果 JSON tag、字段名或枚举值变化，schema 必须同步更新。

当前 legacy wire 仍以 JSON Lines 输出以下顶层类型为主：
- `status`
- `thinking`
- `content`
- `tokens`
- `error`
- `interrupt`

## 当前分层：内部 typed event，外部 legacy wire

### 内部 canonical / structured 层
后端内部以 application DTO 表达运行时状态和工具生命周期，关键定义在：

- `backend/alice/application/dto/responses.py`

这里已经有：
- `RuntimeEventType`
- `RuntimeEventResponse`
- `StructuredRuntimeOutput`
- `StructuredToolCall`
- `StructuredToolResult`

这层允许后端表达更细的内部事件，例如：
- `status_changed`
- `reasoning_delta`
- `content_delta`
- `tool_call_started`
- `tool_call_argument_delta`
- `tool_call_completed`
- `tool_result`
- `usage_updated`
- `message_completed`
- `error_raised`
- `interrupt_ack`

### 外部 legacy compatibility 层
对 Rust frontend 的对外输出仍通过：

- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`

这里负责把内部事件投影成旧协议。例如：
- `streaming` / `thinking` -> legacy `status: thinking`
- `tool_call_started` -> legacy `status: executing_tool`
- `message_completed` / `interrupted` / `error` -> legacy `status: done`
- 不被旧协议支持的内部事件（如 `tool_result`）不会伪造新的顶层消息类型，而是被丢弃或留在内部结构化层处理

这条边界是本轮 backend-only 演进的核心约束：

> **后端内部可以继续 typed event 化，但只要 frontend 还没迁移，wire contract 就必须保持 legacy 兼容。**

## 协议实现分布

### Rust 侧
- `frontend/src/bridge/protocol/message.rs`
- `frontend/src/bridge/protocol/codec.rs`
- `frontend/src/bridge/transport/stdio_transport.rs`
- `frontend/src/bridge/client.rs`

### Python 侧
#### 当前默认输出链路
- `backend/alice/cli/main.py`
- `backend/alice/application/dto/responses.py`
- `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- `backend/alice/infrastructure/bridge/protocol/messages.py`（复用中断信号与旧协议消息定义）

#### 旧 bridge 路径 / 历史兼容资产
- `backend/alice/infrastructure/bridge/server.py`
- `backend/alice/infrastructure/bridge/event_handlers/message_handler.py`
- `backend/alice/infrastructure/bridge/stream_manager.py`

## 状态流相关联动

Bridge 不只是协议文件本身，状态流还会继续影响：

- `frontend/src/app/state.rs`
- `frontend/src/core/dispatcher.rs`
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/workflow/chat_workflow.py`
- `backend/alice/application/dto/responses.py`

## 当前消息方向

### Python -> Rust
通过 stdout 发送 JSON Lines 消息，当前对 frontend 仍以 legacy 兼容形状输出，常见类型包括：
- `status`
- `thinking`
- `content`
- `tokens`
- `error`
- `interrupt`

### Rust -> Python
通过 stdin 发送：
- 用户输入文本
- 中断信号 `__INTERRUPT__`

## backend-only 改动与 frontend 联动边界

### 只改后端且通常不需要前端同步的情况
满足以下条件时，可以先做 backend-only 变更：
- 只新增或调整内部 `RuntimeEventType` / `StructuredRuntimeOutput` 字段
- 只修改 application 层内部状态机
- 只修改 legacy serializer 的内部投影逻辑，但**最终输出 wire shape 不变**
- 只补充日志、审计、测试覆盖

这类改动的最小验证集通常是：

```bash
python -m pytest backend/tests/integration/test_agent.py
python -m pytest backend/tests/integration/test_bridge.py
python -m pytest backend/tests/integration/test_logging_e2e.py
```

### 必须联动 frontend / schema 的情况
出现以下任一情况，就不能只改后端：
- 新增 legacy 顶层消息类型
- 修改 `status/thinking/content/tokens/error/interrupt` 任一字段结构
- 修改 legacy `status` 枚举值
- 修改 `INTERRUPT_SIGNAL`
- 修改 `protocols/bridge_schema.json`
- 修改 Rust codec / transport / dispatcher 对消息的消费方式

这类改动至少要一起验证：

```bash
python -m pytest backend/tests/integration/test_bridge.py
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 修改检查清单
- 改内部 runtime event 时，先确认是否会穿透到 legacy wire。
- 改 legacy serializer 时，确认 `protocols/bridge_schema.json` 和 Rust frontend 是否仍兼容。
- 改状态枚举时，同步检查协议层和前端状态机。
- 改中断语义时，同时检查客户端发送、服务端处理和运行中断路径。
- 改序列化格式时，检查 codec、transport、schema 和错误处理。
- 改协议后，至少补或更新对应 integration tests。

## 推荐验证

### backend-only 协议/运行时回归
```bash
python -m pytest backend/tests/integration/test_agent.py
python -m pytest backend/tests/integration/test_bridge.py
python -m pytest backend/tests/integration/test_logging_e2e.py
```

### 变更外部 wire contract 时
```bash
python -m pytest backend/tests/integration/test_bridge.py
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 进一步阅读
- [架构总览](../architecture/overview.md)
- [测试指南](../testing/guide.md)
- [Structured Logging](../operations/logging/README.md)
- [代码地图与高耦合区域](../reference/code-map.md)
