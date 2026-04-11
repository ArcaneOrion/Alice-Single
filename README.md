# Alice

Alice 是一个带 Rust TUI 前端与 Python 后端的智能体运行时。

当前仓库已经完成从单文件入口到分层架构的重构；长期知识、代码地图与专题说明统一收敛到 `docs/`，根目录文档只保留最小入口、启动方式和操作说明。

## 先看哪里
- 项目文档入口：`docs/README.md`
- 架构总览：`docs/architecture/overview.md`
- 代码地图：`docs/reference/code-map.md`
- Bridge 协议：`docs/protocols/bridge.md`
- 测试指南：`docs/testing/guide.md`
- Agent 工作约束：`CLAUDE.md` / `AGENTS.md`

## 仓库结构
```text
.
├── frontend/               # Rust TUI
├── backend/alice/          # Python 引擎
├── backend/tests/          # 后端测试
├── protocols/              # 跨语言协议与 schema
├── prompts/                # 仓库 prompt 模板分片
├── skills/                 # 技能目录
├── docs/                   # 结构化文档入口
├── Dockerfile.sandbox      # 运行时镜像定义
└── .alice/                 # 本地运行时配置、prompt、memory、logs、workspace
```

## 最小启动
1. 准备运行时配置：
   ```bash
   ${EDITOR:-vi} .alice/config.json
   ```
   至少填写：
   - `llm.api_key`
   - `llm.model_name`

2. 启动 TUI：
   ```bash
   cd frontend && cargo run --release
   ```

首次启动会幂等补齐以下运行时目录与文件：
- `.alice/config.json`
- `.alice/prompt/*.xml`
- `.alice/prompt/prompt.xml`
- `.alice/memory/*`

注意：旧路径 `.alice/prompt.xml` 已废弃；当前唯一合法的运行时 prompt 聚合文件是 `.alice/prompt/prompt.xml`。

## 运行时说明
- 默认用户配置源是 `.alice/config.json`
- 仓库里的 `prompts/01_identity.xml` 到 `prompts/05_output.xml` 是模板分片
- 首次启动会把模板复制到 `.alice/prompt/*.xml`，再组装出运行时 `.alice/prompt/prompt.xml`
- `update_prompt` 修改的是 `.alice/prompt/*.xml`，不会回写仓库 `prompts/`
- `.alice/`、日志、缓存、coverage、build 产物属于运行时数据，不是设计文档

## 常用命令
```bash
# 后端测试
python -m pytest backend/tests

# Python 静态检查
python -m ruff check backend/alice backend/tests
python -m mypy backend/alice

# 前端验证
cd frontend && cargo test
cd frontend && cargo clippy
cd frontend && cargo fmt --check
```

## TUI 快捷键
- `Enter`：发送
- `Esc`：中断当前响应或工具执行
- `Ctrl+O`：切换思考侧边栏
- `Ctrl+C`：退出

## 内置文本命令
- `toolkit list`
- `toolkit refresh`
- `memory "内容" [--ltm]`
- `todo "任务清单"`
- `update_prompt 01_identity.xml "新内容"`

## 文档维护规则
- 结构、协议、日志、测试入口或代码地图发生变化后，运行 `/code_map_team`
- 长期知识优先写入 `docs/`
- 不要把运行时产物、聊天上下文或根目录旧文档当作权威来源
