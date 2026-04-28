# Alice

带 Rust TUI 前端与 Python 后端的智能体运行时。

## 仓库结构

```
.
├── frontend/          # Rust TUI
├── backend/alice/     # Python 引擎
├── backend/tests/     # 后端测试
├── protocols/         # 跨语言协议与 schema
├── prompts/           # 仓库 prompt 模板分片
├── skills/            # 技能目录
├── .alice/            # 本地运行时配置、prompt、memory、logs、workspace
└── Dockerfile.sandbox # 运行时镜像定义
```

## 最小启动

1. 编辑配置：
   ```bash
   ${EDITOR:-vi} .alice/config.json
   ```
   至少填写 `llm.api_key` 和 `llm.model_name`

2. 启动 TUI：
   ```bash
   cd frontend && cargo run --release
   ```

首次启动会幂等补齐 `.alice/config.json`、`.alice/prompt/*.xml`、`.alice/prompt/prompt.xml`、`.alice/memory/*`。

## 常用命令

```bash
# 后端测试
python -m pytest backend/tests

# Python 静态检查
python -m ruff check backend/alice backend/tests

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
