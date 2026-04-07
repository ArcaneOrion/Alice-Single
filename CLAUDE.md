# CLAUDE.md

本文件为 Claude Code 在此代码库中工作时提供指导。

`docs/` 是长期知识的统一入口；如遇到根目录历史文档残留，应优先收敛到 `docs/` 对应专题，而不是恢复平行文档。

> **项目状态**：Alice 已完成从单文件到分层架构的重构。旧入口 (`agent.py`/`tui_bridge.py`) 保留但已由新架构替代。

---

## 最小启动

```bash
# 1. 配置运行时 LLM
${EDITOR:-vi} .alice/config.json
# 编辑 llm.api_key / llm.model_name，按需设置 llm.base_url

# 2. 运行（首次启动会自动补齐 `.alice/` 运行时目录，并按需构建 Docker 镜像）
cd frontend && cargo run --release
```

## 常用命令

| 操作 | 命令 |
|------|------|
| 构建运行 | `cd frontend && cargo run --release` |
| 列出/刷新技能 | 在 TUI 中发送 `toolkit list` / `toolkit refresh` |
| 检查容器 | `docker ps -a --filter name=alice-sandbox-instance` |
| 同步文档索引 | `/code_map_team` |

**TUI 快捷键**：`Enter` 发送 | `Esc` 中断 | `Ctrl+O` 切换思考侧边栏 | `Ctrl+C` 退出

---

## 渐进式阅读

先看这里，再按需下钻，不要把长期知识继续堆回本文件：

- 架构入口：`docs/architecture/overview.md`
- Bridge 协议与状态流：`docs/protocols/bridge.md`
- 代码地图与高耦合区域：`docs/reference/code-map.md`
- 结构化日志专题：`docs/operations/logging/README.md`
- 测试入口：`docs/testing/guide.md`

适用建议：
- 需要理解系统分层、依赖方向、跨边界风险时，看 `docs/architecture/overview.md`
- 需要改消息结构、状态枚举、中断语义时，看 `docs/protocols/bridge.md`
- 需要定位改动目录或判断联动面时，看 `docs/reference/code-map.md`
- 需要改日志 schema、字段、路由或校验时，看 `docs/operations/logging/README.md`
- 需要决定最小验证集或补测方向时，看 `docs/testing/guide.md`

---

## 最小测试入口

```bash
# 后端测试
python -m pytest backend/tests

# 前端验证
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

---

## 最小调试入口

| 问题 | 排查 |
|------|------|
| TUI 渲染 | 检查 `frontend/frontend.log`、终端 stderr |
| 流式解析 | 检查 `.alice/logs/tasks.jsonl`、`alice_runtime.log` |
| Docker 执行 | `docker ps -a --filter name=alice-sandbox-instance` |
| 技能未加载 | 在 TUI 中发送 `toolkit refresh` |

---

## 重要约束

1. **双入口并存**：`cli/main.py`（新，AliceAgent + WorkflowChain）和 `bridge/server.py`（旧，BridgeServer + MessageHandler）并行存在
2. **Execution Harness 双路径**：当前默认是 `container` harness（`LocalProcessExecutor`），`docker` 为兼容路径；改执行后端时要联动 `command_registry.py`、`lifecycle_service.py`、`execution_service.py` 与相关测试
3. **类型重复定义**：`AgentStatus`、`Author`、`Message` 在 Rust app/core/ui 层各有独立定义，通过转换函数互转
4. **`MessageQueue` 未使用**：已定义但 `App` 直接用 `Vec<Message>`
5. **`EventBus` 基本空转**：创建后未实际用于事件分发
6. **安全审查弱**：仅拦截 `rm` 命令
7. **运行时配置与 Prompt 边界**：`.alice/config.json` 是运行时配置源；`prompts/01_identity.xml` 到 `05_output.xml` 会组装为运行时 `.alice/prompt.xml`
8. **修改代码后**如影响架构、协议、代码地图、日志或测试入口，请运行 `/code_map_team` 以同步 `docs/` 下的相关文档索引

---
