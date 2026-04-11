# CLAUDE.md

本文件为 Claude Code 在此仓库中的最小工作约束。

原则：`docs/` 是长期知识统一入口；根目录文档只保留导航、启动方式和最小约束，不继续堆主题知识。

## 先读这些
- 文档入口：`docs/README.md`
- 架构总览：`docs/architecture/overview.md`
- 代码地图：`docs/reference/code-map.md`
- 耦合视图：`docs/reference/code-map-coupling.md`
- Bridge 协议：`docs/protocols/bridge.md`
- 测试指南：`docs/testing/guide.md`
- 日志专题：`docs/operations/logging/README.md`

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

## 最小调试入口
- TUI 渲染：`frontend/frontend.log`、终端 stderr
- 流式与任务日志：`.alice/logs/tasks.jsonl`、`alice_runtime.log`
- 容器状态：`docker ps -a --filter name=alice-sandbox-instance`
- 技能刷新：在 TUI 中发送 `toolkit refresh`

## 当前关键边界
1. 当前默认用户配置源是 `.alice/config.json`
2. 当前运行时 prompt 边界是 `.alice/prompt/*.xml` 与 `.alice/prompt/prompt.xml`，不是旧的 `.alice/prompt.xml`
3. `backend/alice/cli/main.py` 是当前默认 Python CLI / bridge 入口；`backend/alice/infrastructure/bridge/server.py` 仍是 legacy 兼容边界
4. 执行后端改动至少联动：`backend/alice/core/registry/command_registry.py`、`backend/alice/application/services/lifecycle_service.py`、`backend/alice/domain/execution/services/execution_service.py`、`backend/alice/domain/execution/executors/`
5. 结构、协议、日志、测试入口或代码地图导航变更后，运行 `/code_map_team`

## 工作约束
- 改代码前先做针对性检查；改完后做同类验证
- 需要结构定位看 `docs/reference/code-map.md`
- 需要联动面看 `docs/reference/code-map-coupling.md`
- 需要判断哪份文档权威，看 `docs/reference/sources-of-truth.md`
- 如果发现根目录旧说明与 `docs/` 冲突，优先修正到 `docs/`
