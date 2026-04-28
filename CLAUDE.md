# CLAUDE.md

本文件为 Claude Code 在此仓库中的最小工作约束。

## 最小启动
```bash
${EDITOR:-vi} .alice/config.json
cd frontend && cargo run --release
```

首次启动会补齐：
- `.alice/config.json`
- `.alice/prompt/*.xml`
- `.alice/prompt/prompt.xml`
- `.alice/memory/*`

## 最小验证
```bash
python -m pytest backend/tests
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## 调试入口
- TUI 渲染：`frontend/frontend.log`、终端 stderr
- 流式与任务日志：`.alice/logs/tasks.jsonl`、`alice_runtime.log`
- 容器状态：`docker ps -a --filter name=alice-sandbox-instance`
- 技能刷新：在 TUI 中发送 `toolkit refresh`

## 关键边界
1. 默认用户配置源是 `.alice/config.json`
2. 运行时 prompt 边界是 `.alice/prompt/*.xml` 与 `.alice/prompt/prompt.xml`
3. `backend/alice/cli/main.py` 是默认 Python CLI / bridge 入口
4. `backend/alice/infrastructure/bridge/server.py` 已废弃（legacy）
5. 执行后端改动至少联动：`command_registry.py`、`lifecycle_service.py`、`execution_service.py`、`executors/`

## 分层约束
```text
application/ → domain/       (业务规则)
             → infrastructure/ (外部系统适配)
             → core/          (共享框架能力)

domain/      → core/
infrastructure/ → core/
```

- 业务规则进入 `domain/`
- 编排和请求流程进入 `application/`
- 外部系统、IO、协议适配进入 `infrastructure/`
- 可复用框架能力进入 `core/`

## 高联动区域
- **Bridge 协议**：改字段/状态/中断语义至少联调 frontend 和 backend
- **执行后端**：改 executor 联调 `command_registry`、`lifecycle_service`、`execution_service`
- **Agent 工作流**：`chat_workflow.py` ↔ `chat_service.py` ↔ `stream_service.py` ↔ `function_calling_orchestrator.py`
- **配置系统**：改 Settings 字段联调 `loader.py`、`bootstrap.py`、`orchestration_service.py`

## 工作约束
- 改代码前先做针对性检查；改完后做同类验证
- 不要跨层直连
- 新增能力优先扩展现有包，不创建新的顶层杂项目录
