# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

> **文档结构**：本文档采用渐进式披露原则 —— 从快速开始到深入架构，高级内容折叠在 `<details>` 中。
> **项目状态**：Alice-Single 正在进行**架构重构**，目标是优化代码结构、提升性能与扩展性。

---

## 快速开始

### 一分钟启动

```bash
# 1. 安装依赖
pip install openai python-dotenv

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 API_KEY 和 MODEL_NAME

# 3. 运行（首次启动会自动构建 Docker 镜像）
cargo run --release
```

### 常用命令

| 操作 | 命令 |
|------|------|
| 构建运行 | `cargo run --release` |
| 列出技能 | 在 TUI 中发送：`toolkit list` |
| 刷新技能 | 在 TUI 中发送：`toolkit refresh` |
| 更新代码地图 | 运行：`/code-map`（使用 skill:code-map） |
| 检查容器 | `docker ps -a --filter name=alice-sandbox-instance` |
| 重建容器 | `docker rmi alice-sandbox:latest` |
| 查看容器日志 | `docker logs alice-sandbox-instance` |

### TUI 快捷键

| 按键 | 功能 |
|------|------|
| `Enter` | 发送消息 |
| `Esc` | 中断当前操作 |
| `Ctrl+O` | 切换思考侧边栏 |
| `Ctrl+C` | 退出应用 |
| `Up/Down` | 滚动历史 |
| 鼠标滚轮 | 滚动聊天区/侧边栏 |

---

## 项目概述

Alice 是一个基于 **ReAct 模式**的智能体框架，采用**三层隔离架构**：

```
┌─────────────────────────────────────────────────────────────┐
│  TUI 层 (Rust) ─── 用户界面、交互、渲染                     │
├─────────────────────────────────────────────────────────────┤
│  引擎层 (Python) ─── 状态机、内存管理、命令拦截             │
├─────────────────────────────────────────────────────────────┤
│  沙盒层 (Docker) ─── 安全执行环境、技能运行                 │
└─────────────────────────────────────────────────────────────┘
```

**核心特性**：
- 🦀 **Rust TUI**：流畅的终端界面，支持实时思考过程可视化
- 🐍 **Python 引擎**：四层内存系统、内置命令拦截、LLM 流式调用
- 🐳 **Docker 沙盒**：物理隔离执行环境，支持 Python/Node.js/Playwright
- 🔌 **技能系统**：自动发现、热加载、上下文注入

### 代码地图

本项目维护了一份代码地图文件 `CODE_MAP.md`，记录了：
- 项目文件树和所有源代码文件的结构索引（类、函数、行号）
- 跨文件耦合关系和变更传播场景
- 数据文件格式契约

**修改代码前请先查阅 CODE_MAP.md 中对应文件的耦合点。修改代码后请运行 `/code-map` 同步更新。**

---

## 核心架构

### 通信协议

**Rust ↔ Python** 通过 stdin/stdout 传递 JSON 消息：

```json
// 状态更新
{"type": "status", "content": "thinking"}

// 思考内容（侧边栏）
{"type": "thinking", "content": "..."}

// 正文内容（主聊天区）
{"type": "content", "content": "..."}

// Token 统计
{"type": "tokens", "total": 1234, "prompt": 800, "completion": 434}

// 错误消息
{"type": "error", "content": "..."}
```

**中断机制**：按下 `Esc` 时，Rust 通过 stdin 发送 `__INTERRUPT__` 信号，Python 在 LLM 流式输出和工具执行期间检查该标志。

### 内存系统

四层内存架构由 `agent.py` 管理：

| 层级 | 文件 | 用途 | 保留策略 |
|------|------|------|----------|
| **工作内存** | `memory/working_memory.md` | 对话历史 | 最近 30 轮（可配置） |
| **STM** | `memory/short_term_memory.md` | 短期事实/发现 | 7 天滚动，过期提炼到 LTM |
| **LTM** | `memory/alice_memory.md` | 经验教训/用户偏好 | 永久存储 |
| **Todo** | `memory/todo.md` | 任务追踪 | 手动管理 |

### 技能系统

技能从 `skills/` 目录自动发现：

```yaml
---
name: skill-name          # 必需：技能名称（与目录名匹配）
description: 技能描述     # 必需：功能说明
license: MIT             # 可选：许可证
allowed-tools: [...]     # 可选：允许使用的工具
metadata: {...}          # 可选：扩展元数据
---
# Markdown 内容...
```

**重要**：调用技能前务必阅读 `SKILL.md`，不同 LLM 模型可能以不同方式使用工具。

### 内置命令

这些命令在**宿主机**执行（非沙盒内）：

```bash
# 内存管理
memory "内容"              # 添加到 STM
memory "关键教训" --ltm    # 添加到 LTM

# 任务追踪
todo "任务描述"

# 提示词修改
update_prompt "新内容"

# 技能管理
toolkit list              # 列出技能
toolkit refresh           # 扫描新技能
```

---

## 配置

### 环境变量（`.env`）

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `API_KEY` | ✅ | - | OpenAI 兼容 API 密钥 |
| `API_BASE_URL` | ❌ | `https://api-inference.modelscope.cn/v1/` | API 端点 |
| `MODEL_NAME` | ✅ | - | 模型标识符（如 `qwen-plus`） |
| `WORKING_MEMORY_MAX_ROUNDS` | ❌ | `30` | 工作内存保留轮数 |

### 路径配置（`config.py`）

```python
DEFAULT_PROMPT_PATH = "prompts/alice.md"
MEMORY_FILE_PATH = "memory/alice_memory.md"
TODO_FILE_PATH = "memory/todo.md"
SHORT_TERM_MEMORY_FILE_PATH = "memory/short_term_memory.md"
WORKING_MEMORY_FILE_PATH = "memory/working_memory.md"
ALICE_OUTPUT_DIR = "alice_output/"
```

---

## 关键实现细节

### 数据流

```
用户输入
  │
  ▼
Rust TUI 捕获按键 → 构建 input 字符串
  │
  ▼ stdin
Python tui_bridge.py 读取 → 传递给 agent.py
  │
  ▼
agent.py 处理
  ├─ 检查内置命令拦截
  ├─ 刷新内存上下文
  ├─ LLM API 流式调用
  └─ 工具执行（docker exec）
  │
  ▼ stdout (JSON)
Rust TUI 解析 → 更新 UI → 渲染
```

### Docker 沙盒隔离

**挂载策略**（仅挂载必要的目录）：

| 宿主机 | 容器 | 说明 |
|--------|------|------|
| `skills/` | `/app/skills` | 技能库（只读） |
| `alice_output/` | `/app/alice_output` | 输出目录 |
| *(未挂载)* | - | `prompts/`、`memory/`、源代码 |

**安全提示**：容器当前以 root 运行（Dockerfile 中无 `USER` 指令），生产环境需加固。

### 思考内容解析

`StreamManager` 识别以下标记作为"思考内容"（显示在侧边栏）：

- 三重反引号代码块：`` ```python ``, `` ```bash ``, `` ``` ``
- XML 标签：`<thought>`, `<reasoning>`, `<thinking>`
- 裸关键词：`python `, `cat `, `ls `, `grep `, `mkdir `

其他内容显示在主聊天区。

---

## 开发指南

### 添加新技能

```bash
# 1. 创建技能目录
mkdir skills/my-skill

# 2. 创建 SKILL.md
cat > skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 技能描述
---

# 技能说明
EOF

# 3. 添加脚本（可选）
touch skills/my-skill/script.py

# 4. 在 TUI 中刷新
toolkit refresh
```

### 调试

| 问题 | 排查方法 |
|------|----------|
| TUI 渲染问题 | 检查终端 Rust panic，审查 `src/main.rs` |
| 流式解析问题 | 检查 `alice_runtime.log`，启用详细日志 |
| Docker 执行失败 | `docker ps -a --filter name=alice-sandbox-instance` |
| 技能未加载 | 运行 `toolkit refresh`，检查日志 |

**日志位置**：
- Python 日志：`alice_runtime.log`
- 容器日志：`docker logs alice-sandbox-instance`
- Rust panics：终端 stderr

### 修改代码后

修改代码后请运行 `/code-map` 同步更新 `CODE_MAP.md`，确保代码地图中的行号和耦合关系保持准确。

---

<details>
<summary><b>🔧 深入架构 - Rust TUI 层</b></summary>

### 核心数据结构

**App 结构体** (`src/main.rs:61-81`)：

```rust
struct App {
    input: String,                    // 用户输入缓冲区
    messages: Vec<Message>,           // 消息历史
    status: AgentStatus,              // 运行状态
    show_thinking: bool,              // 侧边栏开关
    should_quit: bool,                // 退出标志
    scroll_offset: usize,             // 聊天区滚动
    thinking_scroll_offset: usize,    // 侧边栏滚动
    total_tokens: usize,              // Token 统计
    child_stdin: Option<ChildStdinWrapper>,  // Python stdin
}
```

**AgentStatus 状态机**：

```
Starting → Idle → Thinking → Responding → Idle
                ↓
           ExecutingTool
```

**BridgeMessage 协议**：

```rust
enum BridgeMessage {
    Status { content: String },       // "ready", "thinking", "executing_tool", "done"
    Thinking { content: String },     // 思考内容流
    Content { content: String },      // 正文内容流
    Tokens { total, prompt, completion },
    Error { content: String },
}
```

### UI 布局

```
┌─────────────────────────────────────────────────────────────┐
│ Header (3 行)                                                │
│ ├─ 标题: "ALICE ASSISTANT"                                   │
│ ├─ 状态: [Idle/Thinking/ExecutingTool]                      │
│ └─ Token 统计                                                │
├─────────────────────────────┬───────────────────────────────┤
│                             │                               │
│     聊天区 (75%)            │     💭 思考 (25%)             │
│                             │                               │
│                             │                               │
├─────────────────────────────┴───────────────────────────────┤
│ Input (3 行)                                                 │
│ > 用户输入...                                               │
└─────────────────────────────────────────────────────────────┘
```

### 鼠标碰撞检测

```rust
// 判断滚轮作用于哪个区域
let is_in_sidebar = show_thinking &&
    x >= sidebar_area.x && x < sidebar_area.x + sidebar_area.width &&
    y >= sidebar_area.y && y < sidebar_area.y + sidebar_area.height;

let is_in_chat =
    x >= chat_area.x && x < chat_area.x + chat_area.width &&
    y >= chat_area.y && y < chat_area.y + chat_area.height;
```

### 滚动行为

- 新消息到达时自动置底
- 用户手动滚动禁用自动滚动
- 滚动到底部时恢复自动滚动

</details>

---

<details>
<summary><b>🔧 深入架构 - Python 引擎层</b></summary>

### AliceAgent 状态机核心流程

```python
用户输入
  │
  ▼
_refresh_context()  # 注入内存 + 技能快照
  │
  ▼
LLM 流式调用
  │
  ├─ 有工具调用?
  │   ├─ execute_command() → docker exec
  │   └─ 反馈给 LLM → 循环
  │
  └─ 无工具?
      ├─ _update_working_memory()
      └─ 结束
```

### 四层内存系统详解

#### 工作内存 (Working Memory)

- 代码块过滤：使用正则 `r'```[\s\S]*?```'` 移除
- 轮次分隔符：`--- ROUND ---` 标记每轮对话
- FIFO 淘汰：超过 `WORKING_MEMORY_MAX_ROUNDS` 时保留最新 N 轮

#### STM 提炼策略 (7天滚动)

```python
# 1. 识别超过 7 天的日期小节 (格式: ## YYYY-MM-DD)
expiry_limit = today - timedelta(days=7)

# 2. 调用 LLM 提炼长期价值
distill_prompt = f"请重点分析即将被删除的旧记忆：\n{pruned_content}"

# 3. 将提炼结果追加到 LTM
# 4. 从 STM 文件中删除过期内容
```

#### LTM 结构

```markdown
## 经验教训
### 自动提炼记忆 (YYYY-MM-DD)
...
```

### 内置命令拦截流程

```python
def execute_command(self, command, is_python_code=False):
    # 0. 安全审查
    if not is_safe_command(command):
        return warning

    # 1. 拦截内置指令（宿主机执行）
    if cmd_strip.startswith("toolkit"):
        return handle_toolkit(...)
    if cmd_strip.startswith("update_prompt"):
        return handle_update_prompt(...)
    if cmd_strip.startswith("todo"):
        return handle_todo(...)
    if cmd_strip.startswith("memory"):
        return handle_memory(...)

    # 2. 性能优化：cat skills/* 缓存拦截
    cat_match = re.match(r'cat\s+skills/(.+)', cmd_strip)
    if cat_match:
        return snapshot_mgr.read_skill_file(...)  # 缓存命中

    # 3. Docker 容器执行
    return subprocess.run(["docker", "exec", ...])
```

### StreamManager 滑动窗口机制

```python
class StreamManager:
    def __init__(self, max_buffer_size=10*1024*1024, window_size=20):
        self.buffer = ""
        self.in_code_block = False
        self.window_size = window_size  # 滑动预判窗口

    def process_chunk(self, chunk_text):
        self.buffer += chunk_text

        # 溢出保护
        if len(self.buffer) > self.max_buffer_size:
            self.buffer = ""
            self.in_code_block = False
            return

        # 智能前缀保留（避免标记截断）
        hold_back = self.window_size
        for start_tag, _ in markers:
            for i in range(len(start_tag)-1, 0, -1):
                if self.buffer.endswith(start_tag[:i]):
                    hold_back = max(hold_back, i)
```

**识别标记**：

```python
markers = [
    ("```python", "```"),
    ("```bash", "```"),
    ("```", "```"),
    ("<thought>", "</thought>"),
    ("<reasoning>", "</reasoning>"),
    ("<thinking>", "</thinking>"),
    ("<python>", "</python>"),
]

naked_keywords = ["python ", "cat ", "ls ", "grep ", "mkdir "]
```

### 容器管理三阶段初始化

```python
def _ensure_docker_environment(self):
    # 阶段1：Docker 引擎检查
    subprocess.run("docker --version", ...)

    # 阶段2：镜像构建（缺失时）
    subprocess.run(f"docker image inspect {self.docker_image}", ...)
    # 缺失则：docker build -t alice-sandbox:latest ...

    # 阶段3：常驻容器启动
    subprocess.run([
        "docker", "run", "-d",
        "--name", "alice-sandbox-instance",
        "--restart", "always",
        "-v", f"{skills_path}:/app/skills",
        "-v", f"{output_path}:/app/alice_output",
        "-w", "/app",
        self.docker_image,
        "tail", "-f", "/dev/null"  # 保持运行
    ])
```

</details>

---

<details>
<summary><b>🔧 深入架构 - Docker 与技能系统</b></summary>

### Dockerfile.sandbox 解析

**基础镜像**：`ubuntu:24.04`

**系统依赖**：
```dockerfile
RUN apt-get update && apt-get install -y \
    ca-certificates curl wget git \
    build-essential pkg-config libssl-dev \
    python3 python3-pip python3-dev python3-venv
```

**Node.js**：
```dockerfile
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest
```

**Python 虚拟环境**：
```dockerfile
ENV VIRTUAL_ENV=/opt/alice_env
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
```

**Playwright**：
```dockerfile
RUN pip install playwright \
    && playwright install-deps chromium \
    && playwright install chromium
```

### 安全配置分析

**已实现**：
- ✅ Docker 隔离执行环境
- ✅ 敏感文件物理隔离（未挂载）
- ✅ `shell=False` 避免宿主机 Shell 注入
- ✅ 命令超时限制（120 秒）
- ✅ 基础 `rm` 命令拦截

**潜在风险**：
- ⚠️ 容器以 root 运行（Dockerfile 缺少 `USER` 指令）
- ⚠️ 安全审查过于宽松（仅拦截 `rm`）
- ⚠️ 无网络隔离
- ⚠️ 无资源限制（`--memory`, `--cpus`）

### SnapshotManager 技能发现

```python
def refresh(self):
    self.skills = {}  # 重置注册表
    for path in ["prompts/alice.md", "skills"]:
        if os.path.isdir(path):
            for item in sorted(os.listdir(path)):
                skill_md = os.path.join(path, item, "SKILL.md")
                if os.path.exists(skill_md):
                    self.skills[item] = self._parse_skill(skill_md)
```

### mtime 缓存策略

```python
def read_skill_file(self, relative_path):
    current_mtime = os.path.getmtime(full_path)
    cached = self.skill_content_cache.get(full_path)

    if cached and cached["mtime"] == current_mtime:
        return cached["content"]  # 缓存命中 (<10ms)

    # 缓存失效，重新加载
    content = read_file(full_path)
    self.skill_content_cache[full_path] = {
        "content": content,
        "mtime": current_mtime
    }
    return content
```

**性能提升**：100-300ms (docker exec) → <10ms (缓存命中)

</details>

---

<details>
<summary><b>🛠️ 高级开发 - Rust 扩展</b></summary>

### 添加测试

```bash
# 在 src/main.rs 中添加测试
#[cfg(test)]
mod tests {
    #[test]
    fn test_example() {
        // ...
    }
}

cargo test
```

### 使用 clippy

```bash
cargo clippy
```

### 格式化代码

```bash
cargo fmt
```

**关键 Rust 模式**：
- `Result<(), Box<dyn Error>>` - 错误传播
- `mpsc::channel()` - 线程安全通信
- `Mutex<Arc<T>>` - 共享状态（如 `app.interrupted`）

</details>

---

<details>
<summary><b>🛠️ 高级开发 - Python 扩展</b></summary>

### 添加测试

```bash
pip install pytest
mkdir tests
# 创建 tests/test_agent.py
pytest tests/
```

### 类型检查

```bash
pip install mypy
mypy agent.py tui_bridge.py
```

### 关键 Python 模式

- `subprocess.Popen()` - Rust 启动 Python 子进程
- `sys.stdout.flush()` - 每条 JSON 后必须调用
- `queue.Queue()` - 线程安全的 stdin 监听
- 守护线程 - `stdin_reader` 设为 daemon

</details>

---

## 重要约束与警告

1. **无看门狗**：`tui_bridge.py` 崩溃时整个系统失败
2. **硬编码路径**：`./tui_bridge.py` 路径在 `main.rs:165` 中硬编码
3. **行缓冲依赖**：Python 必须调用 `sys.stdout.flush()` 确保 JSON 实时传输
4. **同步通信**：TUI 会阻塞等待 Python 响应
5. **安全审查弱**：`is_safe_command()` 仅拦截 `rm` 命令

---

## 项目状态

Alice-Single 正在进行**架构重构**，目标是优化代码结构、提升性能与扩展性。
