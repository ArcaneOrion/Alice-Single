# CODE_MAP.md - 代码地图

> **用途**：Claude Code 改代码时的导航文件。定位代码、分析影响、同步更新。
> **最后同步**：2026-03-27 20:12 (commit: 8276e61)
> **维护规则**：每次修改代码后，运行 /code-map 同步，或手动更新受影响的行号和耦合关系。

---

## 文件树

```
Alice-Single/
├── src/
│   └── main.rs                           # Rust TUI 主程序（632 行）
├── backend/alice/                         # Python 后端（新架构 DDD 分层）
│   ├── __init__.py
│   ├── application/                      # 应用层
│   │   ├── __init__.py
│   │   ├── agent/                        # Agent、ReAct 循环
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                  # Agent 主控制器
│   │   │   └── react_loop.py             # ReAct 循环引擎（254 行）
│   │   ├── dto/                          # 数据传输对象
│   │   │   ├── __init__.py
│   │   │   ├── requests.py               # 请求 DTO（123 行）
│   │   │   └── responses.py              # 响应 DTO（229 行）
│   │   ├── services/                     # 应用服务
│   │   │   ├── __init__.py
│   │   │   ├── orchestration_service.py  # 编排服务
│   │   │   └── lifecycle_service.py      # 生命周期服务
│   │   └── workflow/                     # 工作流
│   │       ├── __init__.py
│   │       ├── base_workflow.py          # 工作流基类
│   │       ├── chat_workflow.py          # 聊天工作流
│   │       └── tool_workflow.py          # 工具执行工作流
│   ├── domain/                           # 领域层（核心业务逻辑）
│   │   ├── __init__.py
│   │   ├── execution/                    # 命令执行域
│   │   │   ├── __init__.py
│   │   │   ├── builtin/                  # 内置命令
│   │   │   │   ├── __init__.py
│   │   │   │   ├── memory_command.py     # memory 命令
│   │   │   │   ├── todo_command.py       # todo 命令
│   │   │   │   └── toolkit_command.py    # toolkit 命令
│   │   │   ├── executors/                # 执行器
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py               # 执行器基类
│   │   │   │   └── docker_executor.py    # Docker 执行器
│   │   │   ├── models/                   # 领域模型
│   │   │   │   ├── __init__.py
│   │   │   │   ├── command.py            # 命令模型
│   │   │   │   ├── execution_result.py   # 执行结果
│   │   │   │   └── security_rule.py      # 安全规则
│   │   │   └── services/                 # 领域服务
│   │   │       ├── __init__.py
│   │   │       ├── execution_service.py  # 执行服务（219 行）
│   │   │       └── security_service.py   # 安全服务
│   │   ├── llm/                          # LLM 服务域
│   │   │   ├── __init__.py
│   │   │   ├── models/                   # LLM 模型
│   │   │   │   ├── __init__.py
│   │   │   │   ├── message.py            # 消息模型
│   │   │   │   ├── response.py           # 响应模型
│   │   │   │   └── stream_chunk.py       # 流式块
│   │   │   ├── parsers/                  # 解析器
│   │   │   │   ├── __init__.py
│   │   │   │   └── stream_parser.py      # 流式解析
│   │   │   ├── providers/                # Provider 实现
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py               # Provider 基类
│   │   │   │   └── openai_provider.py    # OpenAI 兼容实现
│   │   │   └── services/                 # LLM 服务
│   │   │       ├── __init__.py
│   │   │       ├── chat_service.py       # 聊天服务
│   │   │       └── stream_service.py     # 流式服务
│   │   ├── memory/                       # 内存管理域
│   │   │   ├── __init__.py
│   │   │   ├── models/                   # 内存模型
│   │   │   │   ├── __init__.py
│   │   │   │   ├── memory_entry.py       # 记忆条目
│   │   │   │   └── round_entry.py        # 对话轮次
│   │   │   ├── repository/               # 内存仓储
│   │   │   │   ├── __init__.py
│   │   │   │   └── file_repository.py    # 文件仓储
│   │   │   ├── services/                 # 内存服务
│   │   │   │   ├── __init__.py
│   │   │   │   ├── distiller.py          # 记忆提炼
│   │   │   │   └── memory_manager.py     # 内存管理器（218 行）
│   │   │   └── stores/                   # 内存存储
│   │   │       ├── __init__.py
│   │   │       ├── base.py               # 存储基类
│   │   │       ├── ltm_store.py          # 长期记忆存储
│   │   │       ├── stm_store.py          # 短期记忆存储
│   │   │       └── working_store.py      # 工作内存存储
│   │   └── skills/                       # 技能管理域
│   │       ├── __init__.py
│   │       ├── loaders/                  # 技能加载器
│   │       │   ├── __init__.py
│   │       │   ├── base.py               # 加载器基类
│   │       │   ├── cache_loader.py       # 缓存加载器
│   │       │   └── directory_loader.py   # 目录扫描
│   │       ├── models/                   # 技能模型
│   │       │   ├── __init__.py
│   │       │   ├── skill.py              # 技能模型
│   │       │   └── skill_metadata.py     # 元数据模型
│   │       ├── repository/               # 技能仓储
│   │       │   ├── __init__.py
│   │       │   └── file_repository.py    # 文件仓储
│   │       └── services/                 # 技能服务
│   │           ├── __init__.py
│   │           ├── skill_cache.py        # 技能缓存
│   │           └── skill_registry.py     # 技能注册表
│   ├── infrastructure/                   # 基础设施层
│   │   ├── __init__.py
│   │   ├── bridge/                       # Bridge 通信
│   │   │   ├── __init__.py
│   │   │   ├── server.py                 # 桥接服务器
│   │   │   ├── stream_manager.py         # 流式管理器
│   │   │   ├── event_handlers/           # 事件处理器
│   │   │   │   ├── __init__.py
│   │   │   │   ├── interrupt_handler.py # 中断处理
│   │   │   │   └── message_handler.py   # 消息处理
│   │   │   ├── protocol/                 # 协议定义
│   │   │   │   ├── __init__.py
│   │   │   │   ├── codec.py             # 编解码
│   │   │   │   └── messages.py          # 协议消息（124 行）
│   │   │   └── transport/                # 传输层
│   │   │       ├── __init__.py
│   │   │       ├── transport_trait.py   # 传输抽象
│   │   │       └── stdio_transport.py   # stdin/stdout 实现
│   │   ├── cache/                        # 缓存层
│   │   │   └── __init__.py
│   │   ├── docker/                       # Docker 管理
│   │   │   ├── __init__.py
│   │   │   ├── client.py                # Docker 客户端
│   │   │   ├── config.py                # Docker 配置
│   │   │   ├── container_manager.py     # 容器管理
│   │   │   └── image_builder.py         # 镜像构建
│   │   └── logging/                      # 日志配置
│   │       └── __init__.py
│   └── core/                             # 核心层
│       ├── __init__.py
│       ├── config/                       # 配置管理
│       │   ├── __init__.py
│       │   ├── loader.py                 # 配置加载
│       │   └── settings.py               # 配置类（96 行）
│       ├── container/                    # 依赖注入
│       │   ├── __init__.py
│       │   ├── container.py             # DI 容器（201 行）
│       │   └── decorators.py            # 装饰器
│       ├── event_bus/                    # 事件总线
│       │   ├── __init__.py
│       │   ├── event.py                 # 事件定义
│       │   ├── event_bus.py             # 事件总线
│       │   └── handler_trait.py         # 处理器接口
│       ├── exceptions/                   # 异常定义
│       │   ├── __init__.py
│       │   ├── base.py                  # 异常基类
│       │   ├── config_errors.py         # 配置异常
│       │   ├── execution_errors.py      # 执行异常
│       │   ├── llm_errors.py            # LLM 异常
│       │   └── memory_errors.py         # 内存异常
│       ├── interfaces/                   # 核心接口
│       │   ├── __init__.py
│       │   ├── command_executor.py      # 命令执行接口
│       │   ├── llm_provider.py          # LLM 接口（60 行）
│       │   ├── memory_store.py          # 内存存储接口
│       │   └── skill_loader.py          # 技能加载接口
│       ├── logging/                      # 日志配置
│       │   ├── __init__.py
│       │   ├── configure.py             # 日志配置
│       │   └── formatters.py            # 格式化器
│       └── registry/                     # 注册表
│           ├── __init__.py
│           ├── command_registry.py      # 命令注册表
│           ├── llm_registry.py          # LLM 注册表
│           ├── memory_registry.py       # 内存注册表
│           └── skill_registry.py        # 技能注册表
├── agent.py                               # 旧版入口（兼容）
├── tui_bridge.py                          # 桥接层入口（366 行）
├── snapshot_manager.py                    # 技能快照管理器（138 行）
├── config.py                              # 旧版配置（41 行）
├── request_headers.py                     # 请求头轮换
├── protocols/
│   └── shared_types.py                    # 共享类型定义
├── Cargo.toml                             # Rust 项目配置
├── requirements.txt                       # Python 依赖
├── Dockerfile.sandbox                     # 沙盒镜像定义
├── .env.example                           # 环境变量模板
├── CLAUDE.md                              # 开发指南
├── README.md                              # 项目说明
├── ARCHITECTURE.md                        # 架构文档
├── API.md                                 # API 文档
├── CODE_MAP.md                            # 本文件
├── prompts/
│   └── alice.md                          # Alice 系统提示词
├── memory/                               # 四层内存文件
│   ├── alice_memory.md                   # 长期记忆
│   ├── short_term_memory.md              # 短期记忆（7 天）
│   ├── working_memory.md                 # 即时记忆（30 轮）
│   └── todo.md                           # 任务清单
├── skills/                               # 技能插件目录（18+ 个）
│   ├── akshare/                          # AKShare 财经数据
│   ├── artifacts-builder/                # HTML 工件构建
│   ├── brand-guidelines/                 # 品牌规范
│   ├── docx/                             # Word 文档
│   ├── fetch/                            # 网页抓取
│   ├── file_explorer/                    # 文件浏览
│   ├── internal-comms/                   # 通信模板
│   ├── market-research-html/             # 市场调研
│   ├── mcp-builder/                      # MCP 服务器
│   ├── pdf/                              # PDF 处理
│   ├── playwright_browser/               # 浏览器自动化
│   ├── pptx/                             # PPT 处理
│   ├── skill-creator/                    # 技能创建
│   ├── slack-gif-creator/                # Slack GIF
│   ├── tavily/                           # Tavily 搜索
│   ├── template-skill/                   # 技能模板
│   ├── weather/                          # 天气查询
│   ├── weibo/                            # 微博热榜
│   └── xlsx/                             # Excel 处理
└── alice_output/                         # 容器输出目录
```

---

## L0 系统总览

Alice 采用 **DDD 分层架构** + **Rust TUI 前端**：

| 层级 | 目录 | 职责 |
|------|------|------|
| **Frontend** | `src/main.rs` | Rust TUI、用户界面渲染 |
| **Infrastructure** | `backend/alice/infrastructure/` | Bridge、Docker、缓存 |
| **Application** | `backend/alice/application/` | 工作流、ReAct 循环、DTO |
| **Domain** | `backend/alice/domain/` | 内存、LLM、执行、技能 |
| **Core** | `backend/alice/core/` | DI 容器、事件总线、接口 |

---

## L1 关键文件索引

### frontend/src/bridge/protocol/message.rs

**Bridge 协议消息定义**

```
BridgeMessage [L33-55]
├── Status { content: StatusContent }
├── Thinking { content: String }
├── Content { content: String }
├── Tokens { total, prompt, completion }
├── Error { content: String }
└── Interrupt

StatusContent [L76-88]
├── Ready
├── Thinking
├── ExecutingTool
└── Done
```

**耦合点**：
- `backend/alice/infrastructure/bridge/protocol/messages.py`
- `frontend/src/bridge/protocol/codec.rs`
- `frontend/src/core/dispatcher.rs`

---

### frontend/src/bridge/transport/stdio_transport.rs

**Python stdio 传输层**

```
ChildStdinWrapper [L35]
StdioTransport [L61-220]
├── DEFAULT_BRIDGE_PATH [L71]
├── default_bridge_path() [L74-76]
├── spawn() [L94-158]
├── spawn_default() [L161-164]
├── spawn_test_transport() [L167-186]
├── send_text() [L197-200]
├── send_interrupt() [L203-205]
├── stdin()/stdin_mut() [L208-215]
└── kill() [L218-220]

StdioWriter [L226-247]
├── new() [L232-236]
├── send() [L239-241]
└── interrupt() [L244-246]
```

**耦合点**：
- `frontend/src/bridge/client.rs`
- `backend/alice/cli/main.py`
- 子进程 stdout/stderr JSON Lines 协议

---

### frontend/src/bridge/client.rs

**桥接客户端**

```
BridgeClient [L41-210]
├── spawn_default() [L77-79]
├── spawn() [L90-99]
├── send_input() [L106-109]
├── send_interrupt() [L114-117]
├── try_recv_message()/recv_message() [L126-143]
├── try_recv_error() [L146-148]
├── stdin()/stdin_mut() [L160-168]
├── state()/set_state() [L171-178]
├── handle_status_message() [L181-187]
└── shutdown() [L190-194]

ClientState [L57-69]
├── Initial
├── Connected
├── Ready
└── Disconnected
```

**耦合点**：
- `frontend/src/bridge/transport/stdio_transport.rs`
- `frontend/src/app/state.rs`
- `frontend/src/main.rs`

---

### frontend/src/app/state.rs

**应用状态模型**

```
Author [L13-18]
Message [L22-63]
AgentStatus [L74-101]
TokenStats [L105-131]
App [L136-328]
├── new() [L209-226]
├── send_message() [L232-254]
├── on_tick() [L259-261]
├── toggle_thinking() [L264-266]
├── append_content() [L270-281]
├── append_thinking() [L285-296]
├── mark_last_message_complete() [L300-304]
└── latest_thinking_content() [L307-328]

AreaBounds [L167-205]
SPINNER [L339]
```

**耦合点**：
- `frontend/src/bridge/client.rs`
- `frontend/src/core/dispatcher.rs`
- `frontend/src/ui/screen.rs`

---

### frontend/src/core/event/types.rs

**前端事件类型**

```
AppEvent [L12-24]
KeyboardEvent [L27-35]
MouseEvent [L38-46]
KeyCode [L49-85]
KeyModifiers [L88-112]
MouseEventKind [L115-129]
MouseButton [L132-140]
UiArea [L143-153]
ScrollState [L156-219]
AreaBounds [L223-232]
```

**耦合点**：
- `frontend/src/core/event/event_bus.rs`
- `frontend/src/core/handler/keyboard_handler.rs`
- `frontend/src/core/handler/mouse_handler.rs`

---

### frontend/src/core/event/event_bus.rs

**事件总线**

```
EventBus [L12-73]
├── new()/default() [L21-24, L69-73]
├── sender()/receiver() [L27-34]
├── send()/try_recv()/recv() [L37-49]
├── recv_timeout() [L52-54]
├── drain() [L57-61]
└── has_pending() [L64-66]

EventSender [L79-125]
├── from_bus()/from_sender() [L85-94]
├── send() [L97-99]
├── send_key() [L102-114]
├── send_tick() [L117-119]
└── send_quit() [L122-124]
```

**耦合点**：
- `frontend/src/core/event/types.rs`
- `frontend/src/main.rs`

---

### frontend/src/ui/component/input/input_box.rs

**输入框组件**

```
InputBoxConfig [L15-32]
render_input_box() [L41-65]
INPUT_HEIGHT [L68]
```

**耦合点**：
- `frontend/src/ui/screen.rs`
- `frontend/src/app/state.rs`

---

### backend/alice/infrastructure/bridge/protocol/messages.py (124 行)

**Bridge 协议定义**

```
MessageType [L15-22]
├── STATUS, THINKING, CONTENT
├── TOKENS, ERROR, INTERRUPT

StatusType [L25-30]
├── READY, THINKING, EXECUTING_TOOL, DONE

StatusMessage [L40-43]
ThinkingMessage [L47-50]
ContentMessage [L54-57]
TokensMessage [L61-66]
ErrorMessage [L70-74]
InterruptMessage [L78-80]

BridgeMessage = Union[所有消息类型]
INTERRUPT_SIGNAL = "__INTERRUPT__"
```

**耦合点**：
- `src/main.rs` BridgeMessage enum
- 所有发送消息到 Rust 的代码

---

### backend/alice/application/agent/react_loop.py (254 行)

**ReAct 循环引擎**

```
ReActConfig [L30-41]
├── max_iterations: int = 10
├── enable_thinking: bool = True
└── timeout_seconds: int = 300

ReActState [L45-62]
├── iteration, phase
├── full_content, full_thinking
├── tool_calls_found, interrupted

ReActLoop [L74-247]
├── should_continue() [L111-121]
├── start_iteration() [L123-127]
├── transition_to_*() [L129-144]
├── interrupt() [L141-144]
├── emit_thinking() [L147-159]
├── emit_content() [L161-173]
├── emit_tokens() [L175-188]
├── emit_status() [L190-199]
├── emit_executing_tool() [L201-212]
├── emit_done() [L214-220]
└── emit_error() [L222-232]
```

**耦合点**：
- `backend/alice/application/dto/responses.py`
- `backend/alice/domain/llm/`
- `backend/alice/domain/execution/`

---

### backend/alice/core/config/settings.py (96 行)

**配置管理**

```
LLMConfig [L13-21]
├── model_name, api_key, base_url
├── max_tokens, temperature
└── enable_thinking, timeout

MemoryConfig [L25-33]
├── working_memory_max_rounds: int = 30
├── stm_expiry_days: int = 7
├── ltm_auto_distill: bool = True
└── 路径配置

DockerConfig [L37-45]
├── image_name, container_name, work_dir
├── mounts: Dict[str, str]
└── timeout: int = 120

Settings [L78-96]
├── llm, memory, docker
├── logging, bridge, security
└── project_root, paths
```

**耦合点**：
- `.env` 环境变量
- 所有使用配置的模块

---

### backend/alice/domain/memory/services/memory_manager.py (218 行)

**内存管理器**

```
MemoryManager [L19-217]
├── __init__() [L26-56]
├── add_working_round() [L58-64]
├── add_stm_entry() [L66-75]
├── add_ltm_entry() [L77-85]
├── get_working_content() [L87-93]
├── get_stm_content() [L95-101]
├── get_ltm_content() [L103-109]
├── get_recent_rounds() [L111-120]
├── search_stm() [L122-132]
├── search_ltm() [L134-144]
├── manage_memory() [L146-180]
├── trim_working_memory() [L182-190]
├── clear_*() [L192-202]
└── get_memory_summary() [L204-215]
```

**耦合点**：
- `backend/alice/domain/memory/stores/`
- `backend/alice/domain/memory/repository/`
- `memory/` 文件目录

---

### backend/alice/domain/execution/services/execution_service.py (219 行)

**执行服务**

```
ExecutionService [L23-218]
├── __init__() [L29-48]
├── execute() [L50-84]
├── _try_handle_builtin() [L86-105]
├── _try_handle_cat_skills() [L107-127]
├── _handle_*() [L129-195]
│   ├── toolkit
│   ├── update_prompt
│   ├── todo
│   └── memory
├── validate() [L196-205]
├── add_security_rule() [L207-209]
└── interrupt() [L211-213]
```

**耦合点**：
- `backend/alice/domain/execution/executors/`
- `backend/alice/domain/execution/builtin/`
- `snapshot_manager.py` 缓存

---

### backend/alice/core/container/container.py (201 行)

**依赖注入容器**

```
ServiceDescriptor [L16-22]
├── interface, implementation
├── is_singleton, instance, factory

Container [L25-183]
├── register_singleton() [L46-69]
├── register_factory() [L71-89]
├── register_transient() [L91-108]
├── get() [L110-147]
├── _create_instance() [L149-173]
├── has() [L175-177]
└── clear() [L179-182]

get_container() [L189-193]
reset_container() [L196-198]
```

**耦合点**：
- 所有使用依赖注入的模块

---

## L2 跨文件耦合

### 场景 1：Bridge 通信协议

**触发条件**：修改消息类型、状态值或 JSON Lines 格式

**需要同步的文件**：
| 文件 | 位置 |
|------|------|
| `frontend/src/bridge/protocol/message.rs` | `BridgeMessage` / `StatusContent` |
| `frontend/src/bridge/protocol/codec.rs` | 编解码逻辑 |
| `backend/alice/infrastructure/bridge/protocol/messages.py` | 消息定义 |
| `backend/alice/application/dto/responses.py` | 响应 DTO |
| `frontend/src/core/dispatcher.rs` | 消息分发与状态更新 |

---

### 场景 2：内置命令拦截

**触发条件**：新增或修改内置命令

**需要同步的文件**：
| 文件 | 说明 |
|------|------|
| `backend/alice/domain/execution/services/execution_service.py` | 命令拦截逻辑 |
| `backend/alice/domain/execution/builtin/` | 命令处理器 |
| `prompts/alice.md` | 命令文档 |

---

### 场景 3：内存文件路径

**触发条件**：修改内存文件位置

**需要同步的文件**：
| 文件 | 说明 |
|------|------|
| `backend/alice/core/config/settings.py` | 路径配置 |
| `backend/alice/domain/memory/services/memory_manager.py` | 文件引用 |

---

### 场景 4：LLM Provider 接口

**触发条件**：修改 LLM 接口

**需要同步的文件**：
| 文件 | 说明 |
|------|------|
| `backend/alice/core/interfaces/llm_provider.py` | 接口定义 |
| `backend/alice/domain/llm/providers/` | Provider 实现 |
| `backend/alice/domain/llm/services/` | 服务使用 |

---

## L3 数据文件格式

### prompts/alice.md
- **格式**：Markdown 系统提示词
- **读取**：`backend/alice/application/agent/agent.py`

### memory/alice_memory.md (LTM)
- **格式**：
  ```markdown
  # Alice 的长期记忆
  ## 经验教训
  - [YYYY-MM-DD] 内容
  ```

### memory/short_term_memory.md (STM)
- **格式**：
  ```markdown
  # Alice 的短期记忆 (最近 7 天)
  ## YYYY-MM-DD
  - [HH:MM] 内容
  ```

### memory/working_memory.md
- **格式**：
  ```markdown
  --- ROUND ---
  USER: ...
  ALICE_THINKING: ...
  ALICE_RESPONSE: ...
  ```

### skills/*/SKILL.md
- **格式**：
  ```yaml
  ---
  name: skill-name
  description: 技能描述
  ---
  # Markdown 内容
  ```

### .env
- **必需变量**：`API_KEY`, `MODEL_NAME`
- **可选变量**：`API_BASE_URL`, `WORKING_MEMORY_MAX_ROUNDS`

---

## 参考文档

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 详细架构说明
- **[API.md](API.md)** - API 接口文档
- **[CLAUDE.md](CLAUDE.md)** - 开发指南
- **[README.md](README.md)** - 项目说明
