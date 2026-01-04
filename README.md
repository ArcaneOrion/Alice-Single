# Alice Agent 技术文档

> **⚠️ 免责声明**：本项目的所有代码均由 AI 生成。使用者在运行、部署或集成前，必须自行评估潜在的安全风险、逻辑缺陷及运行成本。作者不对因使用本项目而导致的任何损失负责。
>
> **💡 特别提示**：本项目包含特定的 **人格设定 (`prompts/alice.md`)** 及 **交互记忆记录 (`memory/`)**。相关文件会记录对话历史。如果您介意此类信息留存，请按需自行编辑或删除相关目录下的文件。

Alice 是一个基于 ReAct 模式的智能体框架，采用 **Rust TUI** 作为交互界面，**Python** 作为核心逻辑引擎，并在 **Docker 容器** 中执行具体任务，实现高性能交互与安全隔离的完美结合。

---

## 1. 技术架构

项目采用“Rust 终端界面 + Python 核心引擎 + 容器化沙盒”的三层隔离架构。

### 1.1 核心技术栈
- **用户界面 (TUI)**: Rust (Ratatui), 提供流畅的终端交互、实时思考过程显示、侧边栏代码展示及自动滚动历史。
- **逻辑引擎 (Engine)**: Python 3.8+, OpenAI API (兼容模式), 负责状态机管理、指令拦截、多级记忆处理。
- **安全沙盒 (Sandbox)**: Ubuntu 24.04 (Docker), 提供物理隔离的执行环境，预装 Python 虚拟环境, Node.js, Playwright 等工具。

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
*   **即时记忆 (Working Memory)**: 存储最近 $N$ 轮对话。包含用户输入、Alice 的回答及思考过程，但**自动排除代码块**以节省上下文空间。
*   **短期记忆 (STM)**: 记录近 7 天的完整交互。系统启动时会自动提炼（Distill）即将过期的旧记忆。
*   **长期记忆 (LTM)**: 存储经提炼的高价值知识、偏好与经验教训。
*   **索引快照 (Snapshot)**: `SnapshotManager` 实时扫描项目资产，生成索引快照注入 LLM 上下文，确保 Alice 了解自己的能力边界。

---

## 2. 交互快捷键 (TUI)

| 快捷键 | 动作 |
| :--- | :--- |
| **Enter** | 发送当前输入的消息 |
| **Esc** | **中断/停止** 当前正在进行的思考、回复或工具执行任务 |
| **Ctrl + O** | 切换显示/隐藏侧边栏（思考过程与代码区） |
| **Ctrl + C** | 强制退出程序 |
| **Up / Down** | 在对话历史中手动滚动（禁用自动滚动） |

---

## 3. 内置指令参考

这些指令由宿主机引擎直接拦截并执行：

| 指令 | 描述 |
| :--- | :--- |
| `toolkit list/refresh` | 管理技能注册表。`refresh` 用于发现 `skills/` 下的新技能 |
| `memory "内容" [--ltm]` | 手动更新记忆。带 `--ltm` 会永久存入 LTM 经验教训区 |
| `update_prompt "新内容"` | 动态更新 `prompts/alice.md` 系统人设 |
| `todo "任务清单"` | 更新 `memory/todo.md` 任务追踪 |

---

## 4. 项目结构

```text
.
├── src/                    # Rust TUI 源代码 (基于 Ratatui)
├── Cargo.toml              # Rust 项目配置文件
├── agent.py                # Python 核心逻辑：状态机、分级记忆与安全隔离调度
├── tui_bridge.py           # 桥接层：管理 TUI 通信、异步输入及流式处理
├── snapshot_manager.py     # 快照管理器：技能自动发现与上下文索引生成
├── Dockerfile.sandbox      # 沙盒镜像定义 (Ubuntu 24.04 + Node + Playwright)
├── alice_output/           # 输出目录：存储任务生成的文件 (已挂载)
├── prompts/                # 指令目录：存放系统提示词 (alice.md)
├── memory/                 # 记忆目录：存放 LTM/STM/Todo 记录
└── skills/                 # 技能库：内置 20+ 自动化技能 (已挂载)
```

---

## 5. 快速开始

### 5.1 环境准备
1. **基础依赖**: 安装 **Rust**, **Python 3.8+** 和 **Docker**。
2. **配置 API**: 参考 `.env.example` 创建 `.env` 文件并填入 `API_KEY` 和 `MODEL_NAME`。
3. **Docker**: 确保 Docker 服务已启动且当前用户有执行权限。

### 5.2 运行方式
```bash
# 启动 Alice 智能体界面
cargo run --release
```
首次运行会自动构建 Docker 沙盒镜像并初始化工作环境。

---

## 6. 许可证
项目遵循 MIT 开源协议。
