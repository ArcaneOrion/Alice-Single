# Bridge 协议与状态流

本页描述 Rust frontend 与 Python backend 之间的 Bridge contract，以及修改这条链路时必须同步检查的文件。

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

这是消息形状的最终约束文件；如果 JSON tag、字段名或枚举值变化，schema 必须同步更新。

## 协议实现分布

### Rust 侧
- `frontend/src/bridge/protocol/message.rs`
- `frontend/src/bridge/protocol/codec.rs`
- `frontend/src/bridge/transport/stdio_transport.rs`
- `frontend/src/bridge/client.rs`

### Python 侧
- `backend/alice/infrastructure/bridge/protocol/messages.py`
- `backend/alice/infrastructure/bridge/server.py`
- `backend/alice/infrastructure/bridge/stream_manager.py`

## 状态流相关联动
Bridge 不只是协议文件本身，状态流还会继续影响：

- `frontend/src/app/state.rs`
- `frontend/src/core/dispatcher.rs`
- `backend/alice/application/agent/agent.py`
- `backend/alice/application/agent/react_loop.py`

## 当前消息方向

### Python -> Rust
通过 stdout 发送 JSON Lines 消息，常见类型包括：
- `status`
- `thinking`
- `content`
- `tokens`
- `error`

### Rust -> Python
通过 stdin 发送：
- 用户输入文本
- 中断信号

## 修改检查清单
- 改消息结构时，同步更新 Rust、Python、schema。
- 改状态枚举时，同步更新协议层和前端状态机。
- 改中断语义时，同时检查客户端发送、服务端处理和运行中断路径。
- 改序列化格式时，检查 codec、transport、schema 和错误处理。
- 改协议后，至少补或更新对应 integration tests。

## 推荐验证
与 Bridge 相关的改动，至少运行：

```bash
pytest -m integration
python -m pytest backend/tests/integration/test_bridge.py
cd frontend && cargo test
```

## 进一步阅读
- [架构总览](../architecture/overview.md)
- [代码地图与高耦合区域](../reference/code-map.md)
