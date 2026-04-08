# 测试指南

本页是贡献者视角的测试入口，聚焦“去哪里找测试、先跑什么、什么改动需要补哪类测试”。

更完整的历史说明仍可参考 `backend/tests/README.md`。

## 测试目录
- `backend/tests/unit/`: 单元测试
- `backend/tests/integration/`: 集成测试
- `backend/tests/performance/`: 性能测试
- `backend/tests/fixtures/`: 共享 fixtures

## 常用命令

### 跑后端全量测试
```bash
python -m pytest backend/tests
```

### 常用筛选
```bash
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### 常用静态检查
```bash
python -m ruff check backend/alice backend/tests
python -m mypy backend/alice
```

### 前端验证
```bash
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 配置 / CLI 装配最小验证集

当你改的是 `.alice/config.json`、`Settings`、`ConfigLoader`、`bootstrap.py`、`OrchestrationService` 配置透传或 prompt 路径解析时，优先跑这组最小回归。

本组回归默认守住两个前提：
- **`.alice/config.json` 是唯一运行时配置源**。
- **CLI 启动会在首次 `load_config()` 前幂等补齐 `.alice/` 运行时目录**，最小包含 `.alice/config.json`、`.alice/prompt/*.xml`、`.alice/prompt/prompt.xml`、`.alice/memory/*`；其中仓库 `prompts/01_identity.xml` 到 `prompts/05_output.xml` 会首次复制到 `.alice/prompt/` 供用户编辑，再按固定顺序组装为运行时 `.alice/prompt/prompt.xml`。
- **旧运行时路径 `.alice/prompt.xml` 已废弃**；如果 `.alice/config.json` 里的 `memory.prompt_path` 仍指向它，配置加载应显式失败，而不是静默兼容或自动迁移。

修改后应确认模型、header profiles、memory/logging 路径等行为**不会再被环境变量覆盖**，且二次启动**不会覆盖用户已存在的运行时文件**。

```bash
python -m pytest backend/tests/unit/test_core/test_config_loader.py
python -m pytest backend/tests/unit/test_cli/test_bootstrap.py
python -m pytest backend/tests/unit/test_application/test_orchestration_service.py
python -m pytest backend/tests/unit/test_application/test_lifecycle_service.py
python -m pytest backend/tests/unit/test_domain/test_provider_capability.py
```

这组命令分别守住五条边界：
- `test_config_loader.py`: `.alice/config.json -> Settings` 解析与默认值
- `test_bootstrap.py`: CLI 启动装配、request header profile 解析、workflow max_iterations 接线
- `test_orchestration_service.py`: `Settings -> create_from_config()` 透传边界
- `test_lifecycle_service.py`: lifecycle 与 runtime backend owner 装配
- `test_provider_capability.py`: tool-calling capability 与 provider capability dataclass

## backend-only 最小验证集

当你改的是 backend runtime、function calling、legacy serializer、logging，且**没有修改 frontend wire contract** 时，优先跑这组最小回归：

```bash
python -m pytest backend/tests/integration/test_agent.py
python -m pytest backend/tests/integration/test_bridge.py
python -m pytest backend/tests/integration/test_logging_e2e.py
```

这组命令分别守住三条关键边界：
- `test_agent.py`: application/runtime/function-calling 主链路
- `test_bridge.py`: internal typed event -> legacy wire JSON 的兼容投影
- `test_logging_e2e.py`: 结构化日志事件写入 `tasks.jsonl` / `system.jsonl` / `changes.jsonl`

## 当前值得优先关注的集成测试

### `backend/tests/integration/test_agent.py`
主要保护：
- `ChatService` 的 system prompt 与 runtime context 注入方式
- `OrchestrationService.refresh_context()` 不再把记忆/技能伪装成 `user` 消息
- typed tool calling 与 `ExecutionService.execute_tool_invocation()` 兼容入口
- 对话、流式响应、内存与工具执行主链路不回退到旧的文本拼接行为

适用场景：
- 修改 `backend/alice/application/workflow/chat_workflow.py`
- 修改 `backend/alice/domain/llm/services/chat_service.py`
- 修改 `backend/alice/application/services/orchestration_service.py`
- 修改 `backend/alice/domain/execution/services/execution_service.py`

### `backend/tests/integration/test_bridge.py`
主要保护：
- `RuntimeEventResponse` / canonical event 是否正确投影到 frozen legacy wire
- `executing_tool`、`thinking`、`done` 等 legacy 状态归一化
- 旧前端不支持的内部事件不会伪造成新的顶层消息类型
- bridge 初始化失败/运行失败时仍输出旧 error shape

适用场景：
- 修改 `backend/alice/application/dto/responses.py`
- 修改 `backend/alice/infrastructure/bridge/legacy_compatibility_serializer.py`
- 修改 `backend/alice/infrastructure/bridge/protocol/messages.py`
- 修改 `protocols/bridge_schema.json`

### `backend/tests/integration/test_logging_e2e.py`
主要保护：
- JSONL logging pipeline 是否把记录落到正确文件
- `model.*` / `api.*` / `task.*` / `change.*` 事件是否保留基础字段
- `StreamService` 产生的流式日志上下文是否带上 `task_id`、`request_id`、`trace_id`
- runtime/function-calling 相关日志不会因为字段或路由调整而失去结构化上下文

适用场景：
- 修改 `backend/alice/core/logging/*`
- 修改 `backend/alice/domain/llm/services/stream_service.py`
- 修改 logging schema、事件命名、JSONL handler 路由

## 什么时候补什么测试
- 纯后端逻辑改动：优先补 unit tests。
- 影响 workflow orchestration、function calling、logging、跨模块边界：补 integration tests。
- 影响吞吐、日志写入、重执行路径：检查是否需要 performance tests。
- 改内部 typed runtime event，但外部 wire shape 不变：至少跑 backend-only 最小验证集。
- 改协议或状态流并影响 frontend 消费：前后端验证一起跑，不要只跑单侧。

## 什么时候必须联动前端验证
出现以下情况时，不要只跑后端：
- 修改 `protocols/bridge_schema.json`
- 修改 legacy 顶层消息结构或字段名
- 修改 legacy `status` 枚举值
- 修改中断信号 `__INTERRUPT__`
- 修改 Rust frontend 的 codec / dispatcher / state 消费逻辑

最小联动验证：

```bash
python -m pytest backend/tests/integration/test_bridge.py
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 当前值得注意的其他测试覆盖点
- `backend/tests/performance/test_log_write_speed.py`: Logging 性能
- `backend/tests/unit/`: 细粒度服务与模型逻辑回归

## 标记
当前常用 pytest markers：
- `unit`
- `integration`
- `slow`
- `docker`

## 文档维护提醒
如果你新增了重要测试类别、夹具模式或验证命令，请同步更新本页和 `backend/tests/README.md`。
