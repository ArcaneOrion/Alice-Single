# CODE_MAP.md - 代码地图

> **用途**：Claude Code 改代码时的导航文件。定位代码、分析影响、同步更新。
> **最后同步**：2026-03-27 (commit: 163eaf0)
> **维护规则**：每次修改代码后，运行 /code-map 同步，或手动更新受影响的行号和耦合关系。

---

## 文件树

```
.
├── frontend/                   # Rust TUI 前端 (~3719 行)
│   └── src/
│       ├── main.rs             # 应用入口，主事件循环
│       ├── app/
│       │   ├── state.rs        # 应用状态结构体（Message, AgentStatus, App）
│       │   ├── message_queue.rs
│       │   ├── constants.rs
│       │   └── mod.rs
│       ├── bridge/             # Python 桥接层
│       │   ├── client.rs       # Python 子进程管理
│       │   ├── protocol/
│       │   │   ├── message.rs  # BridgeMessage 枚举定义
│       │   │   └── codec.rs
│       │   └── transport/
│       │       └── stdio_transport.rs
│       ├── core/
│       │   ├── dispatcher.rs   # 事件分发器
│       │   └── handler/
│       │       ├── keyboard_handler.rs
│       │       └── mouse_handler.rs
│       └── ui/                 # TUI 渲染组件
│           ├── screen.rs
│           └── component/
│               ├── chat/
│               ├── header/
│               ├── sidebar/
│               └── input/
├── backend/                    # Python 引擎后端 (~13155 行)
│   └── alice/
│       ├── application/
│       │   ├── agent/
│       │   │   ├── agent.py    # AliceAgent 核心类
│       │   │   └── react_loop.py  # ReAct 循环引擎
│       │   ├── dto/            # 数据传输对象
│       │   ├── services/       # 应用服务
│       │   └── workflow/       # 工作流
│       ├── cli/
│       │   └── main.py         # CLI 入口
│       ├── core/
│       │   ├── config/         # 配置管理
│       │   ├── container/      # 依赖注入容器
│       │   ├── event_bus/      # 事件总线
│       │   ├── exceptions/     # 异常定义
│       │   ├── interfaces/     # 核心接口
│       │   ├── logging/        # 日志配置
│       │   └── registry/       # 注册表（命令、技能、内存）
│       ├── domain/
│       │   ├── execution/      # 命令执行域
│       │   ├── llm/            # LLM 服务域
│       │   ├── memory/         # 内存管理域
│       │   └── skills/         # 技能系统域
│       └── infrastructure/
│           ├── bridge/         # Bridge 桥接层
│           │   ├── server.py   # BridgeServer 核心
│           │   ├── protocol/
│           │   │   └── messages.py  # 消息类型定义
│           │   └── stream_manager.py
│           ├── docker/         # Docker 客户端
│           └── cache/          # 缓存实现
├── protocols/
│   ├── shared_types.py         # 共享协议类型定义
│   └── bridge_schema.json
├── prompts/alice.md            # Agent 人设提示词
├── memory/                     # 内存文件目录
├── skills/                     # 技能插件目录
├── Dockerfile.sandbox          # 沙盒容器镜像
└── requirements.txt
```

---

## L0 系统总览

**Alice-Single** 是一个基于 ReAct 模式的多语言智能体框架，采用三层隔离架构：

| 层级 | 语言 | 模块 | 职责 |
|------|------|------|------|
| **TUI 层** | Rust | `frontend/` | 用户界面、交互、渲染 |
| **引擎层** | Python | `backend/alice/` | 状态机、内存管理、LLM 调用 |
| **沙盒层** | Docker | `Dockerfile.sandbox` | 安全执行环境、技能运行 |

**核心通信流**：`Rust TUI <--(JSON stdin/stdout)--> Python Bridge --> ReAct Loop --> LLM/Tools`

---

## L1 文件 -> 类/函数

### frontend/src/main.rs (122 行)

**入口函数**：
- `main() [L43]` - 主函数，启动 Python 后端，初始化 TUI，运行事件循环

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 启动 Python 路径 | `BridgeClient::spawn_default()` | 硬编码相对路径 |

---

### frontend/src/app/state.rs (473 行)

**核心类型**：
- `Message [L22]` - 单条消息结构
  - `Message::user() [L35]` - 创建用户消息
  - `Message::assistant() [L45]` - 创建助手消息
  - `Message::assistant_pending() [L55]` - 创建流式响应占位
- `Author [L12]` - 消息作者枚举
- `AgentStatus [L74]` - Agent 运行状态（Starting/Idle/Thinking/Responding/ExecutingTool）
- `TokenStats [L105]` - Token 统计
- `App [L136]` - 应用状态核心结构体
  - `App::new() [L188]` - 创建应用状态
  - `App::send_message() [L211]` - 发送用户消息
  - `App::append_thinking() [L248]` - 添加思考内容
  - `App::append_content() [L257]` - 添加正文内容
  - `App::handle_ready() [L310]` - 处理就绪状态
  - `App::interrupt() [L320]` - 发送中断信号

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| Message 结构 | `bridge/protocol/message.rs::BridgeMessage` | JSON 序列化格式必须一致 |
| AgentStatus 变体 | `core/dispatcher.rs::AppState` | 状态转换逻辑依赖 |

---

### frontend/src/bridge/protocol/message.rs (171 行)

**核心类型**：
- `BridgeMessage [L33]` - Bridge 通信消息枚举
  - `Status { content }` - 状态更新
  - `Thinking { content }` - 思考内容
  - `Content { content }` - 正文内容
  - `Tokens { total, prompt, completion }` - Token 统计
  - `Error { content }` - 错误消息
  - `Interrupt` - 中断信号
- `StatusContent [L76]` - 状态内容枚举（Ready/Thinking/ExecutingTool/Done）

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| BridgeMessage 变体 | `backend/alice/infrastructure/bridge/protocol/messages.py` | **跨语言协议** |
| StatusContent 值 | `backend/alice/infrastructure/bridge/protocol/messages.py::StatusType` | JSON 值必须匹配 |
| JSON tag 字段名 | `protocols/bridge_schema.json` | 序列化格式约定 |

---

### frontend/src/bridge/client.rs (223 行)

**核心类型**：
- `BridgeClient [L41]` - Python 桥接客户端
  - `spawn_default() [L77]` - 使用默认路径启动
  - `spawn(bridge_path) [L90]` - 指定路径启动
  - `send_input() [L106]` - 发送用户输入
  - `send_interrupt() [L114]` - 发送中断信号
  - `try_recv_message() [L126]` - 非阻塞接收消息
  - `shutdown() [L190]` - 终止 Python 进程
- `ClientState [L56]` - 客户端状态

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 默认 bridge 路径 | `main.rs` | 相对路径约定 |
| 中断信号字符串 | `backend/alice/infrastructure/bridge/protocol/messages.py::INTERRUPT_SIGNAL` | 信号约定 |

---

### frontend/src/core/dispatcher.rs (741 行)

**核心类型**：
- `EventDispatcher [L43]` - 事件分发器
  - `new() [L74]` - 创建分发器
  - `handle_bridge_message() [L229]` - 处理后端消息
  - `handle_key_event() [L289]` - 处理键盘事件
  - `handle_mouse_event() [L295]` - 处理鼠标事件
  - `send_interrupt() [L303]` - 发送中断信号
- `AppState [L19]` - 应用状态枚举（与 AgentStatus 对应）
- `drain_bridge_messages() [L56]` - 排空后端消息队列（公开函数）

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| BridgeMessage 匹配 | `bridge/protocol/message.rs` | 消息类型匹配 |
| AppState 状态转换 | `app/state.rs::AgentStatus` | 状态同步 |

---

### backend/alice/application/agent/agent.py (229 行)

**核心类型**：
- `AliceAgent [L29]` - Agent 核心类
  - `__init__() [L39]` - 初始化（注入服务）
  - `status() [L67]` - 获取状态
  - `process() [L82]` - 处理请求（核心 ReAct 循环）
  - `chat() [L130]` - 聊天接口
  - `interrupt() [L147]` - 中断执行
  - `get_status() [L161]` - 获取状态摘要
  - `refresh_skills() [L188]` - 刷新技能注册表
  - `manage_memory() [L198]` - 管理内存滚动
  - `clear_working_memory() [L208]` - 清空工作内存
  - `shutdown() [L213]` - 关闭 Agent

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 依赖注入字段 | `backend/alice/core/container/container.py` | 容器注册键名 |
| 输出消息格式 | `frontend/src/bridge/protocol/message.rs` | **跨语言协议** |

---

### backend/alice/application/agent/react_loop.py (254 行)

**核心类型**：
- `ReActLoop [L74]` - ReAct 循环引擎
  - `should_continue() [L111]` - 判断是否继续
  - `start_iteration() [L123]` - 开始新迭代
  - `emit_thinking() [L147]` - 发送思考内容
  - `emit_content() [L161]` - 发送正文内容
  - `emit_tokens() [L175]` - 发送 Token 统计
  - `emit_status() [L190]` - 发送状态更新
  - `emit_executing_tool() [L201]` - 发送工具执行通知
  - `interrupt() [L141]` - 中断循环
- `ReActConfig [L29]` - 循环配置
- `ReActState [L45]` - 循环状态

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| ApplicationResponse 类型 | `backend/alice/application/dto/responses.py` | 响应类型契约 |

---

### backend/alice/domain/execution/services/execution_service.py (219 行)

**核心类型**：
- `ExecutionService [L23]` - 命令执行服务
  - `execute() [L50]` - 执行命令（内置拦截 + Docker）
  - `_try_handle_builtin() [L86]` - 尝试处理内置命令
  - `_try_handle_cat_skills() [L107]` - 拦截 cat skills/*（缓存优化）
  - `_handle_toolkit() [L129]` - 处理 toolkit 命令
  - `_handle_update_prompt() [L133]` - 处理 update_prompt 命令
  - `_handle_todo() [L142]` - 处理 todo 命令
  - `_handle_memory() [L158]` - 处理 memory 命令
  - `validate() [L196]` - 验证命令安全性

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 内置命令名称 | `prompts/alice.md` | 提示词中可用的命令列表 |
| cat skills 拦截正则 | `backend/alice/domain/skills/loaders/cache_loader.py` | 缓存读取路径约定 |

---

### backend/alice/domain/llm/providers/openai_provider.py (269 行)

**核心类型**：
- `OpenAIProvider [L122]` - OpenAI API 兼容 LLM 提供商
  - `client [L143]` - 延迟初始化的 OpenAI 客户端
  - `_make_chat_request() [L166]` - 执行聊天请求
  - `_extract_stream_chunks() [L208]` - 提取流式数据块
  - `count_tokens() [L224]` - 计算 Token 数量
- `OpenAIConfig [L91]` - Provider 配置
- `RequestHeaderRotator [L71]` - 请求头轮换器

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| API 响应解析 | `backend/alice/domain/llm/parsers/stream_parser.py` | 流式解析器契约 |

---

### backend/alice/domain/memory/services/memory_manager.py (218 行)

**核心类型**：
- `MemoryManager [L19]` - 内存管理器
  - `add_working_round() [L58]` - 添加工作内存对话轮次
  - `add_stm_entry() [L66]` - 添加短期记忆
  - `add_ltm_entry() [L77]` - 添加长期记忆
  - `get_working_content() [L87]` - 获取工作内存文本
  - `manage_memory() [L146]` - 管理短期记忆滚动和提炼
  - `trim_working_memory() [L182]` - 裁剪工作内存
  - `clear_working_memory() [L192]` - 清空工作内存

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 内存文件路径 | `backend/alice/core/config/settings.py` | 配置中的路径常量 |
| 日期小节格式 | `memory/short_term_memory.md` | `## YYYY-MM-DD` 格式约定 |

---

### backend/alice/infrastructure/bridge/server.py (312 行)

**核心类型**：
- `BridgeServer [L33]` - 桥接服务器
  - `start() [L65]` - 启动服务器
  - `run() [L99]` - 运行主循环
  - `send_message() [L118]` - 发送消息到前端
  - `send_status() [L136]` - 发送状态消息
  - `send_thinking() [L147]` - 发送思考消息
  - `send_content() [L156]` - 发送正文消息
  - `send_tokens() [L165]` - 发送 Token 统计
  - `send_error() [L181]` - 发送错误消息
  - `_on_message_received() [L193]` - 接收消息回调
- `create_bridge_server() [L233]` - 工厂函数
- `main_with_agent() [L253]` - 主入口

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 输出消息格式 | `frontend/src/bridge/protocol/message.rs::BridgeMessage` | **跨语言协议** |
| INTERRUPT_SIGNAL 常量 | `protocols/shared_types.py` | 中断信号约定 |

---

### backend/alice/infrastructure/bridge/protocol/messages.py (124 行)

**核心类型**：
- `MessageType [L15]` - 消息类型枚举（STATUS/THINKING/CONTENT/TOKENS/ERROR/INTERRUPT）
- `StatusType [L25]` - 状态类型枚举（READY/THINKING/EXECUTING_TOOL/DONE）
- `StatusMessage [L40]` - 状态消息
- `ThinkingMessage [L47]` - 思考消息
- `ContentMessage [L54]` - 正文消息
- `TokensMessage [L61]` - Token 统计消息
- `ErrorMessage [L70]` - 错误消息
- `InterruptMessage [L78]` - 中断消息
- `BridgeMessage [L84]` - 联合类型（所有消息）
- `INTERRUPT_SIGNAL [L102]` - 中断信号常量 `"__INTERRUPT__"`

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| MessageType/StatusType 值 | `frontend/src/bridge/protocol/message.rs` | **跨语言协议** |
| INTERRUPT_SIGNAL | `frontend/src/core/dispatcher.rs::send_interrupt()` | 中断信号约定 |

---

### backend/alice/domain/skills/services/skill_registry.py (141 行)

**核心类型**：
- `SkillRegistry [L17]` - 技能注册表
  - `refresh() [L32]` - 刷新技能注册表
  - `get_skill() [L44]` - 获取指定技能
  - `list_skills() [L57]` - 列出所有技能名称
  - `get_all_skills() [L67]` - 获取所有技能
  - `get_skill_info() [L77]` - 获取技能详细信息
  - `list_skills_summary() [L99]` - 生成技能列表摘要

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| SKILL.md 格式 | `skills/*/SKILL.md` | YAML frontmatter 解析 |

---

### protocols/shared_types.py (153 行)

**核心类型**：
- `MessageType [L13]` - 消息类型枚举
- `StatusType [L23]` - 状态类型枚举
- `StatusMessage/ThinkingMessage/...` - 各类消息 dataclass
- `BridgeMessage [L82]` - 联合类型
- `INTERRUPT_SIGNAL [L100]` - 中断信号常量
- `message_from_dict() [L103]` - 从字典解析消息
- `message_to_dict() [L132]` - 消息转字典

**耦合点**：
| 改动 | 必须同步 | 原因 |
|------|---------|------|
| 全部类型定义 | `backend/alice/infrastructure/bridge/protocol/messages.py` | 类型重复定义 |
| 全部类型定义 | `frontend/src/bridge/protocol/message.rs` | **跨语言协议** |

---

## L2 跨文件耦合总图

### 场景 A：修改 Bridge 通信协议

**触发条件**：新增/修改/删除 Bridge 消息类型

**需要同步修改的文件**：
| 文件 | 位置 | 变更内容 |
|------|------|----------|
| `frontend/src/bridge/protocol/message.rs` | `BridgeMessage` 枚举 | 添加新变体 |
| `backend/alice/infrastructure/bridge/protocol/messages.py` | `MessageType` 枚举 | 添加新类型 |
| `protocols/shared_types.py` | `MessageType/BridgeMessage` | 添加新类型 |
| `frontend/src/core/dispatcher.rs` | `handle_bridge_message()` | 处理新消息类型 |
| `backend/alice/infrastructure/bridge/server.py` | 发送方法 | 添加新发送方法 |

**注意**：协议变更属于破坏性变更，需要确保 Rust 和 Python 两侧同时更新。

---

### 场景 B：修改 Agent 状态

**触发条件**：新增/修改 Agent 运行状态

**需要同步修改的文件**：
| 文件 | 位置 | 变更内容 |
|------|------|----------|
| `frontend/src/app/state.rs` | `AgentStatus` 枚举 | 添加新状态 |
| `frontend/src/core/dispatcher.rs` | `AppState` 枚举 | 添加新状态 |
| `frontend/src/core/dispatcher.rs` | `convert_state_to_agent_status()` | 更新转换逻辑 |
| `frontend/src/core/dispatcher.rs` | `convert_agent_status_to_app_state()` | 更新转换逻辑 |
| `backend/alice/infrastructure/bridge/protocol/messages.py` | `StatusType` 枚举 | 添加新状态值 |

---

### 场景 C：新增内置命令

**触发条件**：添加新的宿主机执行命令（如 `history`）

**需要同步修改的文件**：
| 文件 | 位置 | 变更内容 |
|------|------|----------|
| `backend/alice/domain/execution/services/execution_service.py` | `_builtin_handlers` 字典 | 添加命令映射 |
| `backend/alice/domain/execution/services/execution_service.py` | `_handle_*()` 方法 | 实现命令处理 |
| `prompts/alice.md` | 命令说明部分 | 更新可用命令列表 |

---

### 场景 D：修改内存文件格式

**触发条件**：修改 `memory/` 目录下文件的存储格式

**需要同步修改的文件**：
| 文件 | 位置 | 变更内容 |
|------|------|----------|
| `backend/alice/domain/memory/services/memory_manager.py` | 内存读写方法 | 适配新格式 |
| `backend/alice/domain/memory/stores/*.py` | 文件解析逻辑 | 更新解析器 |
| `prompts/alice.md` | 内存使用说明 | 更新格式说明 |

**关键格式约定**：
- STM 日期小节：`## YYYY-MM-DD`
- 工作内存轮次分隔：`--- ROUND ---`

---

## L3 数据文件格式契约

### `prompts/alice.md`

- **写入方**：`backend/alice/domain/execution/services/execution_service.py::_update_prompt_file()`
- **读取方**：`backend/alice/application/agent/agent.py`（通过 LLM 上下文注入）
- **格式**：Markdown 文本，包含 Agent 人设和可用命令说明
- **关键约定**：内置命令列表必须与 `_builtin_handlers` 中定义的一致

---

### `memory/working_memory.md`

- **写入方**：`backend/alice/domain/memory/stores/working_store.py`
- **读取方**：`backend/alice/domain/memory/services/memory_manager.py`
- **格式**：对话轮次列表，每轮用 `--- ROUND ---` 分隔
- **关键正则**：`r'--- ROUND ---'` 用于轮次分割

---

### `memory/short_term_memory.md`

- **写入方**：`backend/alice/domain/memory/stores/stm_store.py`
- **读取方**：`backend/alice/domain/memory/services/memory_manager.py`
- **格式**：日期小节结构 `## YYYY-MM-DD`
- **关键约定**：超过 7 天的小节会被提炼到 LTM 并删除

---

### `memory/alice_memory.md`

- **写入方**：`backend/alice/domain/memory/stores/ltm_store.py`
- **读取方**：`backend/alice/domain/memory/services/memory_manager.py`
- **格式**：Markdown，包含 `## 经验教训` 小节和自动提炼条目

---

### `memory/todo.md`

- **写入方**：`backend/alice/domain/execution/builtin/todo_command.py`
- **读取方**：内置 `todo` 命令处理
- **格式**：Markdown 任务列表

---

### `skills/*/SKILL.md`

- **写入方**：手动维护
- **读取方**：`backend/alice/domain/skills/loaders/directory_loader.py`
- **格式**：YAML frontmatter + Markdown 内容
- **关键正则**：
  - 分隔符：`^---$`
  - name 字段：`^name:\s*(.+)$`
  - description 字段：`^description:\s*(.+)$`

---

### `protocols/bridge_schema.json`

- **写入方**：手动维护
- **读取方**：文档参考
- **格式**：JSON Schema，描述 Bridge 消息格式
- **关键约定**：与 Rust/Python 中的消息类型定义保持一致

---

## 附录：LSP 符号提取统计

| 语言 | 源文件数 | 总行数 | 主要 LSP 服务器 |
|------|---------|--------|----------------|
| Rust | ~30 | ~3719 | rust-analyzer |
| Python | ~95 | ~13155 | pyright/pylsp |

---

**同步报告**：
- CODE_MAP.md 已创建 (commit: 163eaf0)
- 首次创建，扫描了全部源代码文件
- LSP 可用性：rust-analyzer 未就绪（回退到文本分析），pyright 部分可用
- 识别跨语言协议耦合 2 处（BridgeMessage、StatusType）
- 识别配置耦合 4 处（内置命令、内存路径、技能格式、日期小节）
