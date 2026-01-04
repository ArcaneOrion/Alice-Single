# Alice Agent 技术文档

> **⚠️ 免责声明**：本项目的所有代码均由 AI 生成。使用者在运行、部署或集成前，必须自行评估潜在的安全风险、逻辑缺陷及运行成本。作者不对因使用本项目而导致的任何损失负责。
>
> **💡 特别提示**：本项目包含特定的 **人格设定 (`prompts/alice.md`)** 及 **交互记忆记录 (`memory/`)**。相关文件会记录对话历史。如果您介意此类信息留存，请按需自行编辑或删除相关目录下的文件。

Alice 是一个基于 ReAct 模式的智能体框架，采用 **Rust TUI** 作为交互界面，**Python** 作为核心逻辑引擎，并在 **Docker 容器** 中执行具体任务，实现高性能交互与安全隔离的完美结合。

---

## 1. 技术架构

项目采用“Rust 终端界面 + Python 核心引擎 + 容器化沙盒”的三层隔离架构。

### 1.1 核心技术栈
- **用户界面 (TUI)**: Rust (Ratatui), 提供流畅的终端交互、实时思考过程显示及自动滚动历史。
- **逻辑引擎 (Engine)**: Python 3.8+, OpenAI API (兼容模式), 负责状态机管理、指令拦截与记忆处理。
- **安全沙盒 (Sandbox)**: Ubuntu 24.04 (Docker), Python 虚拟环境, Node.js 环境, Playwright。

### 1.2 物理隔离与挂载策略
为了保护宿主机安全，Alice 采用严格的物理隔离机制：
*   **挂载项 (容器可见)**:
    - `skills/` -> `/app/skills`: 存放可执行脚本（读写）。
    - `alice_output/` -> `/app/alice_output`: 存放任务产出物（读写）。
*   **非挂载项 (宿主机私有)**:
    - `.env`: 包含敏感 API Key。
    - `agent.py` / `tui_bridge.py`: 核心控制逻辑。
    - `memory/` / `prompts/`: 长期记忆、短期记忆及系统提示词。
*   **交互机制**: 宿主机引擎解析 LLM 的指令，仅将具体代码/命令通过 `docker exec` 发送至沙盒执行。

### 1.3 状态管理与分级记忆
*   **即时记忆 (Working Memory)**: 存储最近 $N$ 轮对话（默认 5 轮，可配置）。包含用户输入、Alice 的回答及思考过程，但**自动排除代码块**以节省上下文空间。
*   **短期记忆 (STM)**: 记录近 7 天的完整交互。系统启动时通过 `AliceAgent.manage_memory()` 实现过期内容的滚动清理。
*   **长期记忆 (LTM)**: 存储经提炼的高价值知识、偏好与经验教训。
*   **任务清单 (Todo)**: 存储当前活跃任务，辅助智能体维持长线目标。
*   **索引快照 (Snapshot)**: `SnapshotManager` 实时扫描 `skills/` 目录，生成文件索引快照注入 LLM 上下文。

---

## 2. 内置指令参考

这些指令由宿主机引擎直接拦截并执行，具有管理项目的最高权限：

| 指令 | 参数示例 | 描述 |
| :--- | :--- | :--- |
| `toolkit` | `list` / `info <name>` / `refresh` | 管理技能注册表。`refresh` 用于重新扫描 `skills/` 目录 |
| `memory` | `"内容"` [`--ltm`] | 更新记忆。带 `--ltm` 追加至 LTM，否则更新 STM |
| `update_prompt` | `"新的人设内容"` | 热更新 `prompts/alice.md` 系统提示词 |
| `todo` | `"任务列表内容"` | 更新任务清单 `memory/todo.md` |

---

## 3. 项目结构

```text
.
├── src/                    # Rust TUI 源代码 (Ratatui)
├── Cargo.toml              # Rust 项目配置文件
├── agent.py                # Python 核心逻辑：状态机、指令拦截与隔离调度
├── tui_bridge.py           # 桥接层：负责 Rust TUI 与 Python Engine 的 JSON 通信
├── main.py                 # CLI 模式入口 (传统的纯终端对话)
├── snapshot_manager.py     # 资产索引：技能自动发现与快照生成
├── Dockerfile.sandbox      # 沙盒镜像定义 (Ubuntu 24.04 + Python + Node)
├── alice_output/           # 输出目录：存储任务生成的文件 (已挂载)
├── prompts/                # 指令目录：存放系统提示词 (alice.md)
├── memory/                 # 记忆目录：存放分级记忆文件 (LTM/STM/Todo)
└── skills/                 # 技能库：19+ 内置技能 (已挂载)
    ├── playwright_browser/ # 网页自动化与爬虫
    ├── mcp-builder/        # MCP 服务端开发技能
    ├── artifacts-builder/  # UI 组件与工件构建
    ├── slack-gif-creator/  # 动态 GIF 生成
    ├── docx/xlsx/pptx/     # Office 文档处理
    ├── akshare/tavily/     # 金融数据与高级搜索
    └── ...                 # 更多技能持续演进中
```

---

## 4. 快速开始

### 4.1 环境准备
1. **基础依赖**: 安装 **Rust**, **Python 3.8+** 和 **Docker**。
2. **配置 API**: 参考 `.env.example` 创建 `.env` 文件，填写 OpenAI 兼容的 API Key。
3. **Docker 权限**: 确保当前用户有执行 `docker` 命令的权限。

### 4.2 运行 TUI 模式 (推荐)
提供交互式的终端界面，支持思考过程查看（Ctrl+O）。
```bash
# 启动 TUI 界面
cargo run --release
```

### 4.3 运行 CLI 模式
传统的逐行对话模式。
```bash
# 安装 Python 依赖
pip install -r requirements.txt
# 启动对话
python main.py
```

---

## 5. 安全与自演进

*   **指令审查**: 拦截危险指令（如 `rm`），防止沙盒内意外删除。
*   **最小权限**: 容器以非特权模式常驻运行，仅允许访问特定挂载目录。
*   **技能自主开发**: Alice 具备在沙盒内编写、测试并注册新技能的能力。现有的多项技能（如 `weather`, `weibo`）均由 Alice 独立编写并动态集成。

---

## 6. 许可证
项目遵循 MIT 开源协议。
