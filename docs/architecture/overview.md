# 架构总览

本页是 Alice-Single 的架构入口，目标是先告诉你系统怎么分层、依赖应该如何流动、哪些改动最容易跨边界扩散。

更细的文件级导航请继续看 [代码地图与高耦合区域](../reference/code-map.md)。

## 系统概览
Alice-Single 由四个核心部分组成：

- `frontend/`: Rust TUI，负责交互、渲染、输入和与后端的桥接。
- `backend/alice/`: Python 引擎，负责 workflow、ReAct、领域能力与基础设施适配。
- `protocols/`: 共享协议与 schema，尤其是 Bridge contract。
- `Dockerfile.sandbox`: 沙盒执行环境定义。

核心通信链路：

```text
Rust TUI <-> Bridge transport/protocol <-> Python workflow/agent <-> domain services/tools
```

## 分层边界

### Frontend
- `app/`: 应用状态、消息历史、状态对象。
- `bridge/`: Python 子进程管理、协议、传输。
- `core/`: dispatcher、事件、输入处理。
- `ui/`: 组件与渲染。
- `util/`: 辅助工具，例如 runtime logging。

约束：
- 不要把业务逻辑和传输细节继续堆进 `frontend/src/main.rs`。
- 状态流改动通常不只影响 UI，也会影响 `app` 和 `core/dispatcher`。

### Backend
- `application/`: workflow orchestration、use case、DTO。
- `domain/`: memory、llm、execution、skills 等核心业务能力。
- `infrastructure/`: bridge、docker、cache、logging 等适配器。
- `core/`: config、DI、interfaces、event bus、registry、共享框架能力。

约束：
- 不要为了方便跨层直连。
- 新增能力优先扩展现有包，而不是创建新的顶层“杂项目录”。

## 依赖方向
默认依赖方向应保持为：

```text
frontend -> bridge -> application -> domain
                                -> infrastructure
                                -> core

domain -> core
infrastructure -> core
application -> domain/core/infrastructure
```

简单判断规则：
- 业务规则进入 `domain/`
- 编排和请求流程进入 `application/`
- 外部系统、IO、协议适配进入 `infrastructure/`
- 可复用框架能力进入 `core/`

## 高风险改动面

### Bridge contract
只要消息结构、字段名、状态枚举或中断语义发生变化，就要同时检查：

- `frontend/src/bridge/protocol/`
- `frontend/src/bridge/transport/`
- `frontend/src/bridge/client.rs`
- `backend/alice/infrastructure/bridge/protocol/`
- `backend/alice/infrastructure/bridge/transport/`
- `backend/alice/infrastructure/bridge/server.py`
- `protocols/bridge_schema.json`

### Frontend 状态流
只要前端收到的消息或状态流发生变化，就要同时检查：

- `frontend/src/app/state.rs`
- `frontend/src/core/dispatcher.rs`
- `frontend/src/bridge/protocol/message.rs`

### 结构化日志
日志 schema、字段命名、路由和验证是横切关注点。相关改动前先看：

- [Logging 专题首页](../operations/logging/README.md)

## 启动与运行入口
- 用户侧启动和环境说明仍可参考根目录 `README.md`。
- 贡献者视角的最小验证，请看 [测试指南](../testing/guide.md)。

## 与旧文档的关系
本页是 `docs/` 中的统一架构入口。

架构说明以本页及其串联出的 `docs/` 专题导航为准，不再保留根目录平行架构文档入口。
