# Alice-Single 重构规划文档

> **版本**: v2.0
> **日期**: 2026-03-26
> **状态**: 进行中
> **性质**: 动态协作文档

---

## 变更日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-03-26 | v2.0 | 前后端分离架构，引入接口隔离、注册模式、DI容器、事件总线 |

---

## 1. 重构目标

### 1.1 核心目标

| 目标 | 说明 | 验收标准 |
|------|------|----------|
| **前后端分离** | Rust TUI 与 Python 引擎独立演进 | 可独立测试、独立部署 |
| **接口隔离** | 所有模块通过 Protocol/Trait 定义 | 清晰的依赖关系图 |
| **依赖注入** | 通过容器管理依赖 | 单元测试可 mock 所有依赖 |
| **注册模式** | 命令、技能、内存类型动态注册 | 新增功能无需修改核心代码 |
| **事件驱动** | 模块间通过事件总线通信 | 可追踪所有状态变化 |

### 1.2 非目标

- 不改变用户交互界面（TUI 保持不变）
- 不改变核心功能（ReAct 模式、四层记忆系统）
- 不破坏现有数据格式（记忆文件、技能配置）

---

## 2. 架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Rust)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  UI Layer   │  │ Event Bus   │  │  Protocol Layer     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼─────────────────┼─────────────────────┼─────────────┘
          │                 │                     │
          └─────────────────┼─────────────────────┘
                           │ stdin/stdout (JSON)
         ┌─────────────────┼─────────────────────┐
         │                 │                     │
┌────────▼────────┐ ┌──────▼──────┐ ┌───────────▼───────────┐
│ Backend (Python)│             │                        │
│ ┌──────────────┐ │ ┌───────────▼─▼──────────────────┐    │
│ │Protocol Layer│ │ │      Domain Layer              │    │
│ └──────┬───────┘ │ │  ┌─────┐ ┌─────┐ ┌─────┐ ┌────┐  │    │
│        │          │ │  │ LLM │ │Mem │ │Exec │ │Skll│  │    │
│ ┌──────▼───────┐  │ │  └──┬──┘ └──┬──┘ └──┬──┘ └─┬──┘  │    │
│ │ Event Bus    │  │ └─────┼──────┼──────┼──────┼─────┘    │
│ └──────────────┘  │        │      │      │      │         │
│                   │ ┌──────▼──────▼──────▼──────▼─────┐    │
│                   │ │     Application Layer           │    │
│                   └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 2.2 依赖规则

- **Frontend**: 仅依赖 Protocol Layer，不直接知道 Backend 实现
- **Protocol Layer**: 共享消息定义，前后端独立实现
- **Backend Application**: 协调 Domain 层服务
- **Backend Domain**: 纯业务逻辑，无基础设施依赖
- **Backend Infrastructure**: 实现 Domain 定义的接口

---

## 3. 文件结构

### 3.1 完整文件树

```
Alice-Single/
├── frontend/                                    # Rust 前端
│   ├── src/
│   │   ├── main.rs                             # 入口
│   │   ├── lib.rs
│   │   │
│   │   ├── app/                                # 应用状态
│   │   │   ├── mod.rs
│   │   │   ├── state.rs                        # 应用状态（纯数据）
│   │   │   ├── message_queue.rs                # 消息队列
│   │   │   └── constants.rs                    # 常量定义
│   │   │
│   │   ├── core/                               # 核心基础设施
│   │   │   ├── event_bus.rs                    # 事件总线
│   │   │   ├── event/
│   │   │   │   ├── mod.rs
│   │   │   │   ├── types.rs                    # 事件类型
│   │   │   │   ├── keyboard.rs                 # 键盘事件
│   │   │   │   ├── mouse.rs                    # 鼠标事件
│   │   │   │   └── protocol.rs                 # 协议事件
│   │   │   ├── handler/
│   │   │   │   ├── mod.rs
│   │   │   │   ├── keyboard_handler.rs         # 键盘处理
│   │   │   │   ├── mouse_handler.rs            # 鼠标处理
│   │   │   │   └── handler_trait.rs            # Handler Trait
│   │   │   └── dispatcher.rs                   # 事件分发器
│   │   │
│   │   ├── ui/                                 # UI 组件
│   │   │   ├── mod.rs
│   │   │   ├── renderer.rs                     # 渲染协调器
│   │   │   ├── theme.rs                        # 主题配置
│   │   │   ├── component/
│   │   │   │   ├── mod.rs
│   │   │   │   ├── component_trait.rs          # Component Trait
│   │   │   │   ├── header/
│   │   │   │   │   ├── mod.rs
│   │   │   │   │   ├── header.rs               # 头部组件
│   │   │   │   │   ├── status_bar.rs           # 状态栏
│   │   │   │   │   └── token_display.rs        # Token 显示
│   │   │   │   ├── chat/
│   │   │   │   │   ├── mod.rs
│   │   │   │   │   ├── chat_view.rs            # 聊天视图
│   │   │   │   │   ├── message.rs              # 消息渲染
│   │   │   │   │   └── scroll_state.rs         # 滚动状态
│   │   │   │   ├── sidebar/
│   │   │   │   │   ├── mod.rs
│   │   │   │   │   ├── sidebar.rs              # 侧边栏
│   │   │   │   │   └── thinking_view.rs        # 思考视图
│   │   │   │   ├── input/
│   │   │   │   │   ├── mod.rs
│   │   │   │   │   ├── input_box.rs            # 输入框
│   │   │   │   │   ├── cursor.rs               # 光标管理
│   │   │   │   │   └── history.rs              # 输入历史
│   │   │   │   └── layout/
│   │   │   │       ├── mod.rs
│   │   │   │       ├── layout_trait.rs         # Layout Trait
│   │   │   │       ├── main_layout.rs          # 主布局
│   │   │   │       └── area.rs                 # 区域计算
│   │   │   └── widget/
│   │   │       ├── mod.rs
│   │   │       ├── widget_trait.rs             # Widget Trait
│   │   │       ├── text_widget.rs
│   │   │       ├── block_widget.rs
│   │   │       └── spinner_widget.rs
│   │   │
│   │   ├── bridge/                             # 桥接层
│   │   │   ├── mod.rs
│   │   │   ├── client.rs                       # Python 客户端
│   │   │   ├── protocol/
│   │   │   │   ├── mod.rs
│   │   │   │   ├── message.rs                  # 消息类型
│   │   │   │   ├── codec.rs                    # 编解码
│   │   │   │   └── validator.rs                # 消息验证
│   │   │   └── transport/
│   │   │       ├── mod.rs
│   │   │       ├── stdio_transport.rs          # stdin/stdout
│   │   │       └── transport_trait.rs          # Transport Trait
│   │   │
│   │   └── util/
│   │       ├── mod.rs
│   │       ├── string.rs
│   │       └── timer.rs
│   │
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── backend/                                    # Python 后端
│   ├── alice/
│   │   ├── __init__.py
│   │   ├── __main__.py                         # 入口点
│   │   │
│   │   ├── core/                               # 核心基础设施
│   │   │   ├── interfaces/                     # 接口定义
│   │   │   │   ├── __init__.py
│   │   │   │   ├── llm_provider.py             # LLM Provider Protocol
│   │   │   │   ├── memory_store.py             # Memory Store Protocol
│   │   │   │   ├── command_executor.py         # Executor Protocol
│   │   │   │   ├── skill_loader.py             # Skill Loader Protocol
│   │   │   │   └── message_handler.py          # Message Handler Protocol
│   │   │   ├── container/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── container.py                # 依赖注入容器
│   │   │   │   └── decorators.py               # 装饰器
│   │   │   ├── event_bus/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── event_bus.py                # 事件总线
│   │   │   │   ├── event.py                    # 事件定义
│   │   │   │   └── handler_trait.py            # Handler Trait
│   │   │   ├── registry/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── command_registry.py         # 命令注册表
│   │   │   │   ├── memory_registry.py          # 内存类型注册表
│   │   │   │   ├── skill_registry.py           # 技能注册表
│   │   │   │   └── llm_registry.py             # LLM 提供商注册表
│   │   │   ├── config/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── settings.py                 # 配置数据类
│   │   │   │   ├── loader.py                   # 配置加载器
│   │   │   │   ├── validator.py                # 配置验证
│   │   │   │   └── defaults.py                 # 默认值
│   │   │   ├── logging/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── configure.py                # 日志配置
│   │   │   │   └── formatters.py               # 自定义格式化
│   │   │   └── exceptions/
│   │   │       ├── __init__.py
│   │   │       ├── base.py                     # 基础异常
│   │   │       ├── llm_errors.py               # LLM 异常
│   │   │       ├── memory_errors.py            # 内存异常
│   │   │       ├── execution_errors.py         # 执行异常
│   │   │       └── config_errors.py            # 配置异常
│   │   │
│   │   ├── domain/                             # 领域层
│   │   │   ├── llm/
│   │   │   │   ├── models/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── message.py              # 消息模型
│   │   │   │   │   ├── response.py             # 响应模型
│   │   │   │   │   ├── stream_chunk.py         # 流式块
│   │   │   │   │   └── tool_call.py            # 工具调用
│   │   │   │   ├── providers/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py                 # 抽象基类
│   │   │   │   │   ├── openai_provider.py      # OpenAI 兼容
│   │   │   │   │   ├── anthropic_provider.py   # Anthropic
│   │   │   │   │   └── factory.py              # Provider 工厂
│   │   │   │   ├── services/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── chat_service.py         # 聊天服务
│   │   │   │   │   ├── stream_service.py       # 流处理服务
│   │   │   │   │   └── token_counter.py        # Token 计数
│   │   │   │   └── parsers/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── stream_parser.py        # 流解析器
│   │   │   │       ├── thought_parser.py       # 思考内容解析
│   │   │   │       └── tool_parser.py          # 工具调用解析
│   │   │   │
│   │   │   ├── memory/
│   │   │   │   ├── models/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── memory_entry.py         # 内存条目
│   │   │   │   │   ├── round_entry.py          # 对话轮次
│   │   │   │   │   └── distill_result.py       # 提炼结果
│   │   │   │   ├── stores/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py                 # Memory Store Protocol
│   │   │   │   │   ├── working_store.py        # 工作内存
│   │   │   │   │   ├── stm_store.py            # 短期记忆
│   │   │   │   │   ├── ltm_store.py            # 长期记忆
│   │   │   │   │   └── todo_store.py           # 任务内存
│   │   │   │   ├── services/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── memory_manager.py       # 内存管理器
│   │   │   │   │   ├── distiller.py            # 提炼服务
│   │   │   │   │   └── context_builder.py      # 上下文构建
│   │   │   │   └── repository/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── file_repository.py      # 文件存储
│   │   │   │       └── repository_trait.py     # Repository Protocol
│   │   │   │
│   │   │   ├── execution/
│   │   │   │   ├── models/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── command.py              # 命令模型
│   │   │   │   │   ├── execution_result.py     # 执行结果
│   │   │   │   │   └── security_rule.py        # 安全规则
│   │   │   │   ├── executors/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py                 # Executor Protocol
│   │   │   │   │   ├── docker_executor.py      # Docker 执行器
│   │   │   │   │   ├── local_executor.py       # 本地执行器
│   │   │   │   │   └── factory.py              # Executor 工厂
│   │   │   │   ├── services/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── execution_service.py    # 执行服务
│   │   │   │   │   ├── security_service.py     # 安全检查
│   │   │   │   │   └── interrupt_handler.py    # 中断处理
│   │   │   │   └── builtin/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── command_trait.py        # Command Protocol
│   │   │   │       ├── registry.py             # 内置命令注册表
│   │   │   │       ├── memory_command.py       # memory 命令
│   │   │   │       ├── todo_command.py         # todo 命令
│   │   │   │       ├── toolkit_command.py      # toolkit 命令
│   │   │   │       └── prompt_command.py       # update_prompt 命令
│   │   │   │
│   │   │   └── skills/
│   │   │       ├── models/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── skill.py                # 技能模型
│   │   │       │   ├── skill_metadata.py       # 技能元数据
│   │   │       │   └── skill_snapshot.py       # 技能快照
│   │   │       ├── loaders/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py                 # Loader Protocol
│   │   │       │   ├── directory_loader.py     # 目录加载器
│   │   │       │   └── cache_loader.py         # 缓存加载器
│   │   │       ├── services/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── skill_registry.py       # 技能注册表
│   │   │       │   ├── skill_cache.py          # 技能缓存
│   │   │       │   └── snapshot_service.py     # 快照服务
│   │   │       └── repository/
│   │   │           ├── __init__.py
│   │   │           ├── file_repository.py      # 文件仓库
│   │   │           └── repository_trait.py     # Repository Protocol
│   │   │
│   │   ├── application/                         # 应用层
│   │   │   ├── agent/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py                    # 主协调器
│   │   │   │   ├── react_loop.py               # ReAct 循环
│   │   │   │   └── workflow/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── base_workflow.py        # Workflow Protocol
│   │   │   │       ├── chat_workflow.py        # 聊天工作流
│   │   │   │       └── tool_workflow.py        # 工具执行工作流
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── orchestration_service.py    # 编排服务
│   │   │   │   └── lifecycle_service.py        # 生命周期管理
│   │   │   └── dto/
│   │   │       ├── __init__.py
│   │   │       ├── requests.py                 # 请求数据传输对象
│   │   │       └── responses.py                # 响应数据传输对象
│   │   │
│   │   ├── infrastructure/                     # 基础设施层
│   │   │   ├── bridge/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── server.py                   # 桥接服务器
│   │   │   │   ├── protocol/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── messages.py             # 消息定义
│   │   │   │   │   ├── codec.py                # 编解码
│   │   │   │   │   └── validator.py            # 验证器
│   │   │   │   ├── transport/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── stdio_transport.py      # stdin/stdout
│   │   │   │   │   └── transport_trait.py      # Transport Protocol
│   │   │   │   └── event_handlers/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── message_handler.py      # 消息处理
│   │   │   │       └── interrupt_handler.py    # 中断处理
│   │   │   │
│   │   │   ├── docker/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py                   # Docker 客户端封装
│   │   │   │   ├── container_manager.py        # 容器管理
│   │   │   │   ├── image_builder.py            # 镜像构建
│   │   │   │   └── config.py                   # Docker 配置
│   │   │   │
│   │   │   ├── logging/
│   │   │   │   ├── __init__.py
│   │   │   │   └── structured_logger.py        # 结构化日志
│   │   │   │
│   │   │   └── cache/
│   │   │       ├── __init__.py
│   │   │       ├── cache_trait.py              # Cache Protocol
│   │   │       ├── memory_cache.py             # 内存缓存
│   │   │       └── file_cache.py               # 文件缓存
│   │   │
│   │   └── cli/                                # CLI 入口
│   │       ├── __init__.py
│   │       └── main.py                         # CLI 入口
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── protocols/                                   # 共享协议
│   ├── bridge_schema.json                      # JSON Schema
│   └── shared_types.py                         # 共享类型
│
├── scripts/
│   ├── migrate.py                              # 数据迁移
│   ├── dev_setup.py                            # 开发环境初始化
│   └── codegen.py                              # 协议代码生成
│
├── alice.toml                                  # 配置文件
└── docker-compose.yml                          # Docker 配置
```

### 3.2 文件职责清单

| 文件 | 职责（一句话） |
|------|----------------|
| `state.rs` | 管理应用状态数据 |
| `event_bus.rs` | 事件总线实现 |
| `component_trait.rs` | UI 组件接口定义 |
| `handler_trait.rs` | 事件处理器接口 |
| `transport_trait.rs` | 传输层接口 |
| `llm_provider.py` | LLM 提供商接口定义 |
| `memory_store.py` | 内存存储接口定义 |
| `command_executor.py` | 命令执行器接口定义 |
| `container.py` | 依赖注入容器 |
| `command_registry.py` | 命令注册表 |
| `event.py` | 事件类型定义 |
| `settings.py` | 配置数据类 |
| `base.py` | 各领域抽象基类 |
| `factory.py` | 工厂模式实现 |

---

## 4. 实施计划

### 阶段 0：基础设施

**目标**：搭建核心基础设施，为后续重构提供支撑

#### 0.1 项目结构

- [ ] 创建 `frontend/` 目录，迁移 Rust 代码
- [ ] 创建 `backend/` 目录，迁移 Python 代码
- [ ] 创建 `protocols/` 共享协议目录
- [ ] 创建 `scripts/` 工具脚本目录

#### 0.2 核心接口定义

- [ ] `core/interfaces/llm_provider.py` - LLM 接口
- [ ] `core/interfaces/memory_store.py` - 内存接口
- [ ] `core/interfaces/command_executor.py` - 执行器接口
- [ ] `core/interfaces/skill_loader.py` - 技能加载接口

#### 0.3 依赖注入容器

- [ ] `core/container/container.py` - DI 容器实现
- [ ] `core/container/decorators.py` - `@inject` 装饰器
- [ ] 单例模式支持
- [ ] 工厂模式支持

#### 0.4 事件总线

- [ ] `core/event_bus/event_bus.py` - 事件总线实现
- [ ] `core/event_bus/event.py` - 事件类型定义
- [ ] `core/event_bus/handler_trait.py` - 处理器接口
- [ ] 同步/异步发布支持

#### 0.5 注册表

- [ ] `core/registry/command_registry.py` - 命令注册表
- [ ] `core/registry/skill_registry.py` - 技能注册表
- [ ] `core/registry/memory_registry.py` - 内存类型注册表
- [ ] `core/registry/llm_registry.py` - LLM 提供商注册表

#### 0.6 配置系统

- [ ] `core/config/settings.py` - 配置数据类
- [ ] `core/config/loader.py` - TOML 加载器
- [ ] `core/config/validator.py` - 配置验证
- [ ] `core/config/defaults.py` - 默认值
- [ ] 环境变量展开 `${VAR}`

#### 0.7 异常体系

- [ ] `core/exceptions/base.py` - 基础异常
- [ ] `core/exceptions/llm_errors.py` - LLM 异常
- [ ] `core/exceptions/memory_errors.py` - 内存异常
- [ ] `core/exceptions/execution_errors.py` - 执行异常
- [ ] `core/exceptions/config_errors.py` - 配置异常

#### 0.8 日志系统

- [ ] `core/logging/configure.py` - 日志配置
- [ ] `core/logging/formatters.py` - 自定义格式化
- [ ] 结构化日志支持
- [ ] 彩色输出（开发模式）

#### 0.9 共享协议

- [ ] `protocols/bridge_schema.json` - JSON Schema
- [ ] `protocols/shared_types.py` - 共享类型
- [ ] `scripts/codegen.py` - 代码生成工具

#### 0.10 开发工具

- [ ] `scripts/dev_setup.py` - 开发环境初始化
- [ ] `pyproject.toml` - 项目配置
- [ ] Ruff 配置
- [ ] MyPy 配置
- [ ] Pytest 配置

**交付物**：
- 完整的目录结构
- 核心接口定义
- DI 容器、事件总线、注册表
- 配置系统、异常体系、日志系统

---

### 阶段 1：后端 - Domain 层

**目标**：重构业务逻辑，实现纯领域模型

#### 1.1 LLM 模块

- [ ] `domain/llm/models/message.py` - 消息模型
- [ ] `domain/llm/models/response.py` - 响应模型
- [ ] `domain/llm/models/stream_chunk.py` - 流式块
- [ ] `domain/llm/models/tool_call.py` - 工具调用
- [ ] `domain/llm/providers/base.py` - Provider 基类
- [ ] `domain/llm/providers/openai_provider.py` - OpenAI 兼容
- [ ] `domain/llm/providers/anthropic_provider.py` - Anthropic（TODO）
- [ ] `domain/llm/providers/factory.py` - Provider 工厂
- [ ] `domain/llm/services/chat_service.py` - 聊天服务
- [ ] `domain/llm/services/stream_service.py` - 流处理服务
- [ ] `domain/llm/services/token_counter.py` - Token 计数
- [ ] `domain/llm/parsers/stream_parser.py` - 流解析器
- [ ] `domain/llm/parsers/thought_parser.py` - 思考解析
- [ ] `domain/llm/parsers/tool_parser.py` - 工具解析

#### 1.2 Memory 模块

- [ ] `domain/memory/models/memory_entry.py` - 内存条目
- [ ] `domain/memory/models/round_entry.py` - 对话轮次
- [ ] `domain/memory/models/distill_result.py` - 提炼结果
- [ ] `domain/memory/stores/base.py` - Store Protocol
- [ ] `domain/memory/stores/working_store.py` - 工作内存
- [ ] `domain/memory/stores/stm_store.py` - 短期记忆
- [ ] `domain/memory/stores/ltm_store.py` - 长期记忆
- [ ] `domain/memory/stores/todo_store.py` - 任务内存
- [ ] `domain/memory/services/memory_manager.py` - 内存管理器
- [ ] `domain/memory/services/distiller.py` - 提炼服务
- [ ] `domain/memory/services/context_builder.py` - 上下文构建
- [ ] `domain/memory/repository/file_repository.py` - 文件存储
- [ ] `domain/memory/repository/repository_trait.py` - Repository Protocol

#### 1.3 Execution 模块

- [ ] `domain/execution/models/command.py` - 命令模型
- [ ] `domain/execution/models/execution_result.py` - 执行结果
- [ ] `domain/execution/models/security_rule.py` - 安全规则
- [ ] `domain/execution/executors/base.py` - Executor Protocol
- [ ] `domain/execution/executors/docker_executor.py` - Docker 执行器
- [ ] `domain/execution/executors/local_executor.py` - 本地执行器（TODO）
- [ ] `domain/execution/executors/factory.py` - Executor 工厂
- [ ] `domain/execution/services/execution_service.py` - 执行服务
- [ ] `domain/execution/services/security_service.py` - 安全检查
- [ ] `domain/execution/services/interrupt_handler.py` - 中断处理
- [ ] `domain/execution/builtin/command_trait.py` - Command Protocol
- [ ] `domain/execution/builtin/registry.py` - 命令注册表
- [ ] `domain/execution/builtin/memory_command.py` - memory 命令
- [ ] `domain/execution/builtin/todo_command.py` - todo 命令
- [ ] `domain/execution/builtin/toolkit_command.py` - toolkit 命令
- [ ] `domain/execution/builtin/prompt_command.py` - update_prompt 命令

#### 1.4 Skills 模块

- [ ] `domain/skills/models/skill.py` - 技能模型
- [ ] `domain/skills/models/skill_metadata.py` - 技能元数据
- [ ] `domain/skills/models/skill_snapshot.py` - 技能快照
- [ ] `domain/skills/loaders/base.py` - Loader Protocol
- [ ] `domain/skills/loaders/directory_loader.py` - 目录加载器
- [ ] `domain/skills/loaders/cache_loader.py` - 缓存加载器
- [ ] `domain/skills/services/skill_registry.py` - 技能注册表
- [ ] `domain/skills/services/skill_cache.py` - 技能缓存
- [ ] `domain/skills/services/snapshot_service.py` - 快照服务
- [ ] `domain/skills/repository/file_repository.py` - 文件仓库
- [ ] `domain/skills/repository/repository_trait.py` - Repository Protocol

**交付物**：
- 完整的 Domain 层实现
- 单元测试（覆盖率目标 60%+）

---

### 阶段 2：后端 - Infrastructure 层

**目标**：实现基础设施，对接 Domain 层接口

#### 2.1 Bridge 模块

- [ ] `infrastructure/bridge/server.py` - 桥接服务器
- [ ] `infrastructure/bridge/protocol/messages.py` - 消息定义
- [ ] `infrastructure/bridge/protocol/codec.py` - 编解码
- [ ] `infrastructure/bridge/protocol/validator.py` - 验证器
- [ ] `infrastructure/bridge/transport/stdio_transport.py` - stdin/stdout
- [ ] `infrastructure/bridge/transport/transport_trait.py` - Transport Protocol
- [ ] `infrastructure/bridge/event_handlers/message_handler.py` - 消息处理
- [ ] `infrastructure/bridge/event_handlers/interrupt_handler.py` - 中断处理

#### 2.2 Docker 模块

- [ ] `infrastructure/docker/client.py` - Docker 客户端封装
- [ ] `infrastructure/docker/container_manager.py` - 容器管理
- [ ] `infrastructure/docker/image_builder.py` - 镜像构建
- [ ] `infrastructure/docker/config.py` - Docker 配置

#### 2.3 Logging 模块

- [ ] `infrastructure/logging/structured_logger.py` - 结构化日志
- [ ] 日志聚合支持（TODO）

#### 2.4 Cache 模块

- [ ] `infrastructure/cache/cache_trait.py` - Cache Protocol
- [ ] `infrastructure/cache/memory_cache.py` - 内存缓存
- [ ] `infrastructure/cache/file_cache.py` - 文件缓存
- [ ] 分布式缓存支持（TODO）

**交付物**：
- 完整的 Infrastructure 层实现
- 与 Domain 层的集成测试

---

### 阶段 3：后端 - Application 层

**目标**：实现应用编排，协调 Domain 层服务

#### 3.1 Agent 模块

- [ ] `application/agent/agent.py` - 主协调器
- [ ] `application/agent/react_loop.py` - ReAct 循环
- [ ] `application/agent/workflow/base_workflow.py` - Workflow Protocol
- [ ] `application/agent/workflow/chat_workflow.py` - 聊天工作流
- [ ] `application/agent/workflow/tool_workflow.py` - 工具执行工作流

#### 3.2 Services

- [ ] `application/services/orchestration_service.py` - 编排服务
- [ ] `application/services/lifecycle_service.py` - 生命周期管理

#### 3.3 DTO

- [ ] `application/dto/requests.py` - 请求数据传输对象
- [ ] `application/dto/responses.py` - 响应数据传输对象

**交付物**：
- 完整的 Application 层实现
- 端到端集成测试

---

### 阶段 4：前端重构

**目标**：重构 Rust 前端，实现组件化架构

#### 4.1 App 模块

- [ ] `app/state.rs` - 应用状态
- [ ] `app/message_queue.rs` - 消息队列
- [ ] `app/constants.rs` - 常量定义

#### 4.2 Core 模块

- [ ] `core/event_bus.rs` - 事件总线
- [ ] `core/event/types.rs` - 事件类型
- [ ] `core/event/keyboard.rs` - 键盘事件
- [ ] `core/event/mouse.rs` - 鼠标事件
- [ ] `core/event/protocol.rs` - 协议事件
- [ ] `core/handler/handler_trait.rs` - Handler Trait
- [ ] `core/handler/keyboard_handler.rs` - 键盘处理
- [ ] `core/handler/mouse_handler.rs` - 鼠标处理
- [ ] `core/dispatcher.rs` - 事件分发器

#### 4.3 UI 组件

- [ ] `ui/component/component_trait.rs` - Component Trait
- [ ] `ui/component/header/header.rs` - 头部组件
- [ ] `ui/component/header/status_bar.rs` - 状态栏
- [ ] `ui/component/header/token_display.rs` - Token 显示
- [ ] `ui/component/chat/chat_view.rs` - 聊天视图
- [ ] `ui/component/chat/message.rs` - 消息渲染
- [ ] `ui/component/chat/scroll_state.rs` - 滚动状态
- [ ] `ui/component/sidebar/sidebar.rs` - 侧边栏
- [ ] `ui/component/sidebar/thinking_view.rs` - 思考视图
- [ ] `ui/component/input/input_box.rs` - 输入框
- [ ] `ui/component/input/cursor.rs` - 光标管理
- [ ] `ui/component/input/history.rs` - 输入历史
- [ ] `ui/component/layout/layout_trait.rs` - Layout Trait
- [ ] `ui/component/layout/main_layout.rs` - 主布局
- [ ] `ui/component/layout/area.rs` - 区域计算
- [ ] `ui/widget/widget_trait.rs` - Widget Trait
- [ ] `ui/widget/text_widget.rs` - 文本组件
- [ ] `ui/widget/block_widget.rs` - 块组件
- [ ] `ui/widget/spinner_widget.rs` - 加载动画

#### 4.4 Bridge 模块

- [ ] `bridge/client.rs` - Python 客户端
- [ ] `bridge/protocol/message.rs` - 消息类型
- [ ] `bridge/protocol/codec.rs` - 编解码
- [ ] `bridge/protocol/validator.rs` - 消息验证
- [ ] `bridge/transport/stdio_transport.rs` - stdin/stdout
- [ ] `bridge/transport/transport_trait.rs` - Transport Trait

#### 4.5 工具模块

- [ ] `util/string.rs` - 字符串工具
- [ ] `util/timer.rs` - 定时器

**交付物**：
- 完整的前端重构
- 单元测试
- 与后端的集成测试

---

### 阶段 5：测试与文档

**目标**：补充测试，更新文档

#### 5.1 单元测试

- [ ] `tests/unit/core/` - 核心测试
- [ ] `tests/unit/domain/` - 领域测试
- [ ] `tests/unit/application/` - 应用测试
- [ ] `tests/unit/frontend/` - 前端测试

#### 5.2 集成测试

- [ ] `tests/integration/test_agent.py` - Agent 测试
- [ ] `tests/integration/test_bridge.py` - Bridge 测试
- [ ] `tests/integration/test_docker.py` - Docker 测试

#### 5.3 Fixtures

- [ ] `tests/fixtures/mock_llm.py` - Mock LLM
- [ ] `tests/fixtures/mock_responses.py` - Mock 响应
- [ ] `tests/fixtures/test_config.toml` - 测试配置

#### 5.4 文档

- [ ] 更新 `CLAUDE.md`
- [ ] 更新 `CODE_MAP.md`
- [ ] 创建 `ARCHITECTURE.md`
- [ ] 创建 `API.md`
- [ ] 更新 `README.md`

**交付物**：
- 测试覆盖率 60%+
- 完整文档

---

## 5. 核心设计

### 5.1 接口定义示例

```python
# core/interfaces/llm_provider.py
from typing import AsyncIterator, Protocol
from dataclasses import dataclass

@dataclass
class ChatMessage:
    role: str
    content: str

@dataclass
class StreamChunk:
    content: str
    is_thinking: bool
    is_complete: bool
    tool_calls: list

class LLMProvider(Protocol):
    """LLM 提供商接口"""

    async def chat(self, messages: list[ChatMessage]) -> str: ...
    async def stream_chat(self, messages: list[ChatMessage]) -> AsyncIterator[StreamChunk]: ...
    def count_tokens(self, messages: list[ChatMessage]) -> int: ...
```

### 5.2 注册模式示例

```python
# core/registry/command_registry.py
@dataclass
class CommandSpec:
    name: str
    description: str
    handler: Callable
    patterns: list[str]

class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        for pattern in spec.patterns:
            self._commands[pattern] = spec
```

### 5.3 依赖注入示例

```python
# core/container/container.py
class Container:
    def __init__(self):
        self._singletons: Dict[Type, object] = {}
        self._factories: Dict[Type, Callable] = {}

    def register_singleton(self, interface: Type[T], instance: T) -> None: ...
    def register_factory(self, interface: Type[T], factory: Callable) -> None: ...
    def get(self, interface: Type[T]) -> T: ...
```

### 5.4 事件总线示例

```python
# core/event_bus/event_bus.py
class EventType(Enum):
    LLM_START = "llm.start"
    LLM_CHUNK = "llm.chunk"
    EXEC_START = "exec.start"
    MEMORY_ADD = "memory.add"

@dataclass
class Event:
    type: EventType
    data: dict

class EventBus:
    def subscribe(self, event_type: EventType, handler: Callable) -> None: ...
    async def publish(self, event: Event) -> None: ...
```

---

## 6. 待办扩展

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 本地执行器 | 无 Docker 的本地执行模式 | 低 |
| Anthropic Provider | 支持 Claude API | 中 |
| 日志聚合 | 集中式日志收集 | 低 |
| 分布式缓存 | Redis 缓存支持 | 低 |
| Web UI | 基于 Web 的界面 | 低 |
| 多会话 | 并发会话支持 | 中 |
| 插件系统 | 动态插件加载 | 低 |

---

## 7. 成功标准

- [ ] 所有现有功能正常运行
- [ ] 单元测试覆盖率 ≥ 60%
- [ ] 所有模块通过接口定义
- [ ] 依赖注入覆盖所有核心组件
- [ ] 事件总线可追踪所有状态变化
- [ ] 新增功能无需修改核心代码
- [ ] 前后端可独立测试、独立部署
