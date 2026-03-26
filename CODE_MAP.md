# CODE_MAP.md - 代码地图

> **用途**：Claude Code 改代码时的导航文件。定位代码、分析影响、同步更新。
> **最后同步**：2026-03-26 (commit: 17977b7)
> **维护规则**：每次修改代码后，运行 /code-map 同步，或手动更新受影响的行号和耦合关系。

---

## 文件树

```
Alice-Single/
├── src/
│   └── main.rs                    # Rust TUI 主程序（632 行）
├── agent.py                        # Python 引擎核心（626 行）
├── tui_bridge.py                   # Rust-Python 桥接层（366 行）
├── config.py                       # 配置管理（41 行）
├── snapshot_manager.py             # 技能快照管理器（138 行）
├── Cargo.toml                      # Rust 依赖声明
├── requirements.txt                # Python 依赖声明
├── Dockerfile.sandbox              # 沙盒容器镜像定义
├── .env.example                    # 环境变量模板
├── CLAUDE.md                       # 项目指令文档
├── README.md                       # 项目说明
├── prompts/
│   └── alice.md                    # Alice 系统提示词/人设
├── memory/                         # 四层内存文件（运行时生成）
│   ├── alice_memory.md             # 长期记忆
│   ├── short_term_memory.md        # 短期记忆（7 天滚动）
│   ├── working_memory.md           # 即时记忆（最近 30 轮）
│   └── todo.md                     # 任务清单
├── skills/                         # 技能插件目录（18+ 个技能）
│   ├── akshare/                    # AKShare 财经数据
│   ├── artifacts-builder/          # HTML 工件构建
│   ├── brand-guidelines/           # Anthropic 品牌规范
│   ├── docx/                       # Word 文档处理
│   ├── fetch/                      # 网页抓取
│   ├── file_explorer/              # 文件浏览
│   ├── internal-comms/             # 内部通信模板
│   ├── market-research-html/       # 市场调研报告生成
│   ├── mcp-builder/                # MCP 服务器构建
│   ├── pdf/                        # PDF 处理
│   ├── playwright_browser/         # 浏览器自动化
│   ├── pptx/                       # PPT 处理
│   ├── skill-creator/              # 技能创建工具
│   ├── slack-gif-creator/          # Slack GIF 生成
│   ├── tavily/                     # Tavily 搜索
│   ├── template-skill/             # 技能模板
│   ├── weather/                    # 天气查询
│   ├── weibo/                      # 微博热榜
│   └── xlsx/                       # Excel 处理
└── alice_output/                   # 容器输出目录（挂载到容器）
```

---

## L0 系统总览

Alice 是一个基于 **ReAct 模式**的三层隔离智能体框架：

| 模块 | 文件 | 职责 |
|------|------|------|
| **TUI 层** | `src/main.rs` | 用户界面、交互、渲染、键盘/鼠标事件处理 |
| **桥接层** | `tui_bridge.py` | Rust-Python 通信协议转换、流式输出解析、中断处理 |
| **引擎层** | `agent.py` | 状态机、四层内存管理、LLM 调用、命令执行 |
| **配置层** | `config.py` | 环境变量、路径配置 |
| **技能管理** | `snapshot_manager.py` | 技能发现、注册、缓存 |
| **沙盒层** | `Dockerfile.sandbox` | Docker 容器隔离执行环境 |

---

## L1 文件 -> 类/函数

### src/main.rs (632 行)

**Rust TUI 主程序** - 使用 ratatui 构建终端界面

```
BridgeMessage [L25-33]
├── Status { content: String }      # 状态更新: "ready", "thinking", "executing_tool", "done"
├── Thinking { content: String }    # 思考内容流（侧边栏）
├── Content { content: String }     # 正文内容流（主聊天区）
├── Tokens { total, prompt, completion }  # Token 统计
└── Error { content: String }       # 错误消息

Author [L36-40]
├── User
└── Assistant

Message [L43-48]
├── author: Author
├── thinking: String
├── content: String
└── is_complete: bool

AgentStatus [L52-58]
├── Starting
├── Idle
├── Thinking
├── Responding
└── ExecutingTool

App [L61-81]
├── input: String                          # 用户输入缓冲区
├── messages: Vec<Message>                 # 消息历史
├── status: AgentStatus                    # 运行状态
├── show_thinking: bool                    # 侧边栏开关
├── should_quit: bool                      # 退出标志
├── spinner_index: usize                   # 动画帧索引
├── scroll_offset: usize                   # 聊天区滚动位置
├── auto_scroll: bool                      # 自动滚动标志
├── thinking_scroll_offset: usize          # 侧边栏滚动位置
├── thinking_auto_scroll: bool             # 侧边栏自动滚动
├── total_tokens: usize                    # Token 统计
├── list_state: ListState                  # 列表状态
├── chat_area: Rect                        # 聊天区坐标（鼠标碰撞检测）
├── sidebar_area: Rect                     # 侧边栏坐标
└── child_stdin: Option<ChildStdinWrapper>  # Python stdin

impl App [L85-160]
├── new() [L86-111]                        # 构造函数
├── send_message() [L113-150]              # 发送消息到 Python
├── on_tick() [L152-154]                   # 定时器回调
└── get_spinner() [L156-159]               # 获取动画字符

main() [L162-391]                          # 主函数：启动 Python 子进程、事件循环
├── 启动 tui_bridge.py 子进程 [L164-169]
├── 创建 stdout/stderr 线程 [L180-202]
├── 终端初始化 [L205-214]
└── 事件循环 [L219-376]
    ├── BridgeMessage 处理 [L221-272]
    ├── UI 渲染 [L274]
    ├── 键盘事件 [L282-333]
    │   ├── Ctrl+C: 退出
    │   ├── Ctrl+O: 切换侧边栏
    │   ├── Enter: 发送消息
    │   ├── Esc: 中断当前对话
    │   └── Up/Down: 滚动
    └── 鼠标事件 [L334-363]

ui() [L393-488]                            # UI 布局渲染
├── Header (状态、Token 统计) [L404-439]
├── Main Area (对话区 + 侧边栏) [L441-467]
└── Input Box [L469-487]

render_messages() [L490-549]              # 渲染对话历史
render_sidebar() [L551-602]               # 渲染思考过程侧边栏
format_text_to_lines() [L605-631]         # 文本换行辅助函数
```

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| BridgeMessage 变体 | `tui_bridge.py` 的 JSON 输出格式 | 通信协议 |
| 消息类型新增 | Rust TUI 渲染逻辑 | JSON 解析 |

---

### agent.py (626 行)

**Python 引擎核心** - 四层内存管理、LLM 流式调用、命令执行拦截

```
AliceAgent [L21-626]
├── __init__() [L22-54]                   # 初始化：Docker 环境、内存管理
├── _ensure_docker_environment() [L56-112]  # Docker 镜像/容器检查与构建
├── _refresh_context() [L114-173]         # 刷新上下文：加载内存、技能快照
├── _load_prompt() [L175-183]             # 加载系统提示词
├── manage_memory() [L185-259]            # STM 滚动与 LTM 提炼（7 天过期）
├── _load_file_content() [L261-270]       # 文件读取辅助
├── handle_update_prompt() [L272-279]     # 内置命令：更新提示词
├── handle_toolkit() [L281-309]           # 内置命令：技能管理
├── handle_todo() [L311-318]              # 内置命令：更新 TODO
├── _update_working_memory() [L320-367]   # 更新即时记忆（自动过滤代码块）
├── handle_memory() [L369-425]            # 内置命令：记忆写入（STM/LTM）
├── interrupt() [L427-429]                # 设置中断标志
├── is_safe_command() [L431-436]          # 安全审查（拦截 rm）
├── execute_command() [L438-531]          # 命令执行：拦截/缓存/Docker
└── chat() [L533-626]                     # 对话主循环（流式输出、工具调用）
```

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 内置命令名称 | `tui_bridge.py` 的命令拦截逻辑 | 命令协议 |
| Docker 容器名称 | `Dockerfile.sandbox` 构建流程 | 容器启动 |
| 内存文件路径 | `config.py` 路径定义 | 文件读写 |

---

### tui_bridge.py (366 行)

**Rust-Python 桥接层** - stdin/stdout JSON 通信协议

```
StreamManager [L15-158]
├── __init__() [L17-23]                   # 初始化：缓冲区、滑动窗口
├── process_chunk() [L25-37]              # 处理流式文本块
├── _try_dispatch() [L39-153]             # 分发数据到 thinking/content
└── flush() [L156-158]                    # 强制冲刷缓冲区

识别标记 [L50-59]
├── ```python / ```bash / ```             # 代码块标记
├── <thought> / <reasoning> / <thinking>  # 思考标签
├── <python>                              # Python 执行标签
└── 裸关键词 [L62]                        # python, cat, ls, grep, mkdir

stdin_reader() [L169-179]                 # stdin 异步监听线程
main() [L181-365]                         # 主循环
├── 启动 AliceAgent [L187-192]
├── 发送 ready 信号 [L195]
├── 接收用户输入 [L197-207]
├── LLM 流式调用 [L214-307]
│   ├── 中断检测 [L234-241]
│   ├── Token 统计 [L244-251]
│   └── 思考/正文分流 [L256-299]
├── 工具执行 [L309-352]
└── 反馈循环 [L350-353]
```

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| JSON type 字段 | `src/main.rs` BridgeMessage 解析 | 通信协议 |
| 思考内容标记 | UI 侧边栏渲染逻辑 | 内容分流 |
| __INTERRUPT__ 信号 | Rust TUI Esc 键处理 | 中断机制 |

---

### config.py (41 行)

**配置管理** - 环境变量加载、路径定义

```
get_env_var() [L9-14]                     # 环境变量读取（支持 required）
API_KEY [L17]                              # OpenAI API 密钥
BASE_URL [L18]                             # API 端点
MODEL_NAME [L21]                           # 模型名称
DEFAULT_PROMPT_PATH [L24]                  # 提示词路径
MEMORY_FILE_PATH [L27]                     # 长期记忆路径
TODO_FILE_PATH [L30]                       # TODO 路径
SHORT_TERM_MEMORY_FILE_PATH [L33]          # 短期记忆路径
WORKING_MEMORY_FILE_PATH [L36]             # 即时记忆路径
WORKING_MEMORY_MAX_ROUNDS [L37]            # 即时记忆保留轮数
ALICE_OUTPUT_DIR [L40]                     # 输出目录
```

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 路径常量 | `agent.py` 文件读写 | 文件定位 |
| 环境变量名 | `.env.example` 模板 | 配置指导 |

---

### snapshot_manager.py (138 行)

**技能快照管理器** - 技能发现、注册、mtime 缓存

```
SnapshotManager [L5-138]
├── __init__() [L10-18]                   # 初始化：扫描 skills/
├── _get_summary() [L20-66]               # 生成文件摘要
├── refresh() [L68-85]                    # 刷新技能注册表
├── get_index_text() [L87-96]             # 生成上下文索引文本
└── read_skill_file() [L98-137]           # 带缓存的技能文件读取
```

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| skills/ 目录结构 | Docker 容器挂载配置 | 文件可访问性 |
| SKILL.md 格式 | 所有技能的元数据 | 技能发现 |

---

## L2 跨文件耦合总图

### 场景 1：Rust-Python 通信协议

**触发条件**：修改消息类型或 JSON 格式

**需要同步的文件**：
| 文件 | 位置 | 说明 |
|------|------|------|
| `src/main.rs` | L25-33 | BridgeMessage enum 定义 |
| `tui_bridge.py` | L195, L226, L246-251, L291-292, L361 | JSON 输出 |

---

### 场景 2：内置命令拦截

**触发条件**：新增或修改内置命令

**需要同步的文件**：
| 文件 | 位置 | 说明 |
|------|------|------|
| `agent.py` | L438-531 | execute_command() 命令拦截逻辑 |
| `tui_bridge.py` | - | 命令在宿主机执行，无需同步 |
| `prompts/alice.md` | L56-100 | 内置命令文档 |

---

### 场景 3：思考内容识别标记

**触发条件**：修改思考内容标记（用于侧边栏显示）

**需要同步的文件**：
| 文件 | 位置 | 说明 |
|------|------|------|
| `tui_bridge.py` | L50-59, L62 | markers 和 naked_keywords |
| `prompts/alice.md` | L102-109 | 思考显性化文档 |

---

### 场景 4：Docker 容器环境

**触发条件**：修改容器配置或镜像

**需要同步的文件**：
| 文件 | 位置 | 说明 |
|------|------|------|
| `agent.py` | L40-41, L83-103 | docker_image, container_name, 挂载配置 |
| `Dockerfile.sandbox` | - | 镜像构建定义 |

---

### 场景 5：内存文件路径

**触发条件**：修改内存文件存储位置

**需要同步的文件**：
| 文件 | 位置 | 说明 |
|------|------|------|
| `config.py` | L24-36 | 路径常量 |
| `agent.py` | L26-29, L49 | 路径引用 |
| `.gitignore` | - | 确保内存文件不被提交 |

---

## L3 数据文件格式契约

### prompts/alice.md
- **写入方**：用户手动编辑 / `update_prompt` 内置命令
- **读取方**：`agent.py:_load_prompt()` [L175-183]
- **格式定义**：Markdown 文本，Alice 的系统提示词/人设

---

### memory/alice_memory.md (LTM)
- **写入方**：`agent.py:handle_memory(target="ltm")` [L402-423]
- **读取方**：`agent.py:_load_file_content()` [L118]
- **格式定义**：
  ```markdown
  # Alice 的长期记忆

  ## 经验教训
  - [YYYY-MM-DD] 内容
  ```

---

### memory/short_term_memory.md (STM)
- **写入方**：`agent.py:handle_memory(target="stm")` [L387-401]
- **读取方**：`agent.py:_load_file_content()` [L119]
- **格式定义**：
  ```markdown
  # Alice 的短期记忆 (最近 7 天)

  ## YYYY-MM-DD
  - [HH:MM] 内容
  ```
- **关键正则**：`r'^## (\d{4}-\d{2}-\d{2})'` [L200]

---

### memory/working_memory.md
- **写入方**：`agent.py:_update_working_memory()` [L320-367]
- **读取方**：`agent.py:_load_file_content()` [L120]
- **格式定义**：
  ```markdown
  # Alice 的即时对话背景 (Working Memory)

  --- ROUND ---
  USER: ...
  ALICE_THINKING: ...
  ALICE_RESPONSE: ...
  ```
- **关键正则**：`r'^--- ROUND ---\n'` [L350]
- **关键特征**：自动过滤代码块 `r'```[\s\S]*?```'` [L325]

---

### memory/todo.md
- **写入方**：`agent.py:handle_todo()` [L311-318]
- **读取方**：`agent.py:_load_file_content()` [L121]
- **格式定义**：自由文本，任务列表

---

### skills/*/SKILL.md
- **写入方**：技能开发者
- **读取方**：`snapshot_manager.py:_get_summary()` [L36-54]
- **格式定义**：
  ```yaml
  ---
  name: skill-name          # 必需：与目录名匹配
  description: 技能描述     # 必需：功能说明
  license: MIT             # 可选
  allowed-tools: [...]     # 可选
  metadata: {...}          # 可选
  ---
  # Markdown 内容...
  ```
- **关键正则**：`r'^---\n(.*?)\n---\n'` [L38]

---

### .env
- **写入方**：用户手动创建（从 .env.example 复制）
- **读取方**：`config.py:get_env_var()` [L9-14]
- **格式定义**：`KEY=value` 标准 dotenv 格式
- **必需变量**：`API_KEY`, `MODEL_NAME`
- **可选变量**：`API_BASE_URL`, `WORKING_MEMORY_MAX_ROUNDS`
