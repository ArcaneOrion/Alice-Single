# Alice API 文档

> 本文档描述 Alice-Single 重构后的 API 接口。

## 目录

- [概述](#概述)
- [Bridge 协议 API](#bridge-协议-api)
- [应用层 API](#应用层-api)
- [领域层 API](#领域层-api)
- [核心层 API](#核心层-api)

---

## 概述

Alice 的 API 分为三个层次：

1. **Bridge 协议 API**: Rust 前端与 Python 后端的通信协议
2. **应用层 API**: 工作流和编排服务的接口
3. **领域层 API**: 领域服务的核心接口

---

## Bridge 协议 API

### 消息类型

#### Python -> Rust 消息

所有消息通过 stdout 以 JSON Lines 格式发送：

```python
# 状态消息
{"type": "status", "content": "ready|thinking|executing_tool|done"}

# 思考消息（显示在侧边栏）
{"type": "thinking", "content": "..."}

# 正文消息（显示在主聊天区）
{"type": "content", "content": "..."}

# Token 统计
{"type": "tokens", "total": 1234, "prompt": 800, "completion": 434}

# 错误消息
{"type": "error", "content": "...", "code": "ERROR_CODE"}
```

#### Rust -> Python 消息

通过 stdin 发送，有两种格式：

```python
# 用户输入（原始字符串）
用户的输入内容

# 中断信号
__INTERRUPT__
```

### 协议定义

**位置**: `backend/alice/infrastructure/bridge/protocol/messages.py`

```python
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Union

class MessageType(str, Enum):
    STATUS = "status"
    THINKING = "thinking"
    CONTENT = "content"
    TOKENS = "tokens"
    ERROR = "error"
    INTERRUPT = "interrupt"

class StatusType(str, Enum):
    READY = "ready"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"

@dataclass
class StatusMessage:
    type: Literal[MessageType.STATUS] = MessageType.STATUS
    content: StatusType = StatusType.READY

@dataclass
class ThinkingMessage:
    type: Literal[MessageType.THINKING] = MessageType.THINKING
    content: str = ""

@dataclass
class ContentMessage:
    type: Literal[MessageType.CONTENT] = MessageType.CONTENT
    content: str = ""

@dataclass
class TokensMessage:
    type: Literal[MessageType.TOKENS] = MessageType.TOKENS
    total: int = 0
    prompt: int = 0
    completion: int = 0

@dataclass
class ErrorMessage:
    type: Literal[MessageType.ERROR] = MessageType.ERROR
    content: str = ""
    code: str = ""

# 联合类型
BridgeMessage = Union[
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
]
```

### Bridge Server

**位置**: `backend/alice/infrastructure/bridge/server.py`

```python
class BridgeServer:
    """桥接服务器，处理与 Rust TUI 的通信"""

    def __init__(
        self,
        input_stream: TextIO,
        output_stream: TextIO,
        workflow_service: Any,
    ):
        self.input = input_stream
        self.output = output_stream
        self.workflow = workflow_service
        self.interrupted = False

    def start(self) -> None:
        """启动桥接服务器，开始监听 stdin"""

    def send_message(self, message: BridgeMessage) -> None:
        """发送消息到 Rust 前端"""

    def handle_interrupt(self) -> None:
        """处理中断信号"""
```

---

## 应用层 API

### 请求 DTO

**位置**: `backend/alice/application/dto/requests.py`

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class RequestType(str, Enum):
    CHAT = "chat"
    INTERRUPT = "interrupt"
    STATUS = "status"
    REFRESH = "refresh"

@dataclass(frozen=True)
class ChatRequest:
    """聊天请求"""
    input: str
    session_id: Optional[str] = None
    enable_thinking: bool = True
    stream: bool = True

@dataclass(frozen=True)
class InterruptRequest:
    """中断请求"""
    session_id: Optional[str] = None

@dataclass(frozen=True)
class StatusRequest:
    """状态请求"""
    include_memory: bool = False
    include_skills: bool = False

@dataclass(frozen=True)
class RefreshRequest:
    """刷新请求"""
    refresh_type: str = "all"  # "all", "skills", "memory"

@dataclass
class RequestContext:
    """请求上下文"""
    request_type: RequestType
    user_input: str = ""
    interrupted: bool = False
    metadata: dict = field(default_factory=dict)
```

### 响应 DTO

**位置**: `backend/alice/application/dto/responses.py`

```python
from dataclasses import dataclass
from enum import Enum

class ResponseType(str, Enum):
    CONTENT = "content"
    THINKING = "thinking"
    STATUS = "status"
    ERROR = "error"
    TOKENS = "tokens"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"

class StatusType(str, Enum):
    READY = "ready"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"
    ERROR = "error"

@dataclass(frozen=True)
class BaseResponse:
    response_type: ResponseType

@dataclass(frozen=True)
class ContentResponse(BaseResponse):
    """正文响应"""
    response_type: ResponseType = ResponseType.CONTENT
    content: str = ""

@dataclass(frozen=True)
class ThinkingResponse(BaseResponse):
    """思考响应"""
    response_type: ResponseType = ResponseType.THINKING
    content: str = ""

@dataclass(frozen=True)
class StatusResponse(BaseResponse):
    """状态响应"""
    response_type: ResponseType = ResponseType.STATUS
    status: StatusType = StatusType.READY
    message: str = ""

@dataclass(frozen=True)
class ErrorResponse(BaseResponse):
    """错误响应"""
    response_type: ResponseType = ResponseType.ERROR
    content: str = ""
    code: str = ""
    details: dict = field(default_factory=dict)

@dataclass(frozen=True)
class TokensResponse(BaseResponse):
    """Token 统计响应"""
    response_type: ResponseType = ResponseType.TOKENS
    total: int = 0
    prompt: int = 0
    completion: int = 0

@dataclass(frozen=True)
class ExecutingToolResponse(BaseResponse):
    """执行工具响应"""
    response_type: ResponseType = ResponseType.EXECUTING_TOOL
    tool_type: str = ""
    command_preview: str = ""

@dataclass(frozen=True)
class DoneResponse(BaseResponse):
    """完成响应"""
    response_type: ResponseType = ResponseType.DONE

# 联合类型
ApplicationResponse = (
    ContentResponse |
    ThinkingResponse |
    StatusResponse |
    ErrorResponse |
    TokensResponse |
    ExecutingToolResponse |
    DoneResponse
)

@dataclass
class ChatResult:
    """聊天结果"""
    content: str = ""
    thinking: str = ""
    tokens: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    is_interrupted: bool = False

def response_to_dict(response: ApplicationResponse) -> dict:
    """将响应转换为字典（用于 JSON 序列化）"""
    ...
```

### ReAct 循环 API

**位置**: `backend/alice/application/agent/react_loop.py`

```python
from dataclasses import dataclass
from typing import Iterator, Callable, Optional

@dataclass
class ReActConfig:
    """ReAct 循环配置"""
    max_iterations: int = 10
    enable_thinking: bool = True
    timeout_seconds: int = 300

@dataclass
class ReActState:
    """ReAct 循环状态"""
    iteration: int = 0
    phase: str = "idle"
    full_content: str = ""
    full_thinking: str = ""
    tool_calls_found: bool = False
    interrupted: bool = False

class ReActLoop:
    """ReAct 循环引擎"""

    def __init__(
        self,
        config: Optional[ReActConfig] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_content: Optional[Callable[[str], None]] = None,
    ): ...

    @property
    def state(self) -> ReActState: ...

    def reset(self) -> None:
        """重置循环状态"""

    def should_continue(self) -> bool:
        """判断是否应该继续循环"""

    def start_iteration(self) -> None:
        """开始新迭代"""

    def transition_to_acting(self) -> None:
        """转换到行动阶段"""

    def transition_to_observing(self) -> None:
        """转换到观察阶段"""

    def transition_to_done(self) -> None:
        """转换到完成阶段"""

    def interrupt(self) -> None:
        """中断循环"""

    def emit_thinking(self, content: str) -> Iterator[ApplicationResponse]:
        """发送思考内容"""

    def emit_content(self, content: str) -> Iterator[ApplicationResponse]:
        """发送正文内容"""

    def emit_tokens(
        self, total: int, prompt: int, completion: int
    ) -> Iterator[ApplicationResponse]:
        """发送 Token 统计"""

    def emit_status(self, status: StatusType) -> Iterator[ApplicationResponse]:
        """发送状态更新"""

    def emit_executing_tool(
        self, tool_type: str
    ) -> Iterator[ApplicationResponse]:
        """发送工具执行通知"""

    def emit_done(self) -> Iterator[ApplicationResponse]:
        """发送完成信号"""

    def emit_error(self, content: str, code: str = "") -> Iterator[ApplicationResponse]:
        """发送错误"""

    def get_result_summary(self) -> dict:
        """获取循环结果摘要"""
```

### 工作流 API

**位置**: `backend/alice/application/workflow/`

#### BaseWorkflow

```python
class BaseWorkflow(ABC):
    """工作流基类"""

    @abstractmethod
    def execute(self, request: ApplicationRequest) -> Iterator[ApplicationResponse]:
        """执行工作流"""
        ...
```

#### ChatWorkflow

```python
class ChatWorkflow(BaseWorkflow):
    """聊天工作流"""

    def __init__(
        self,
        agent: Any,
        memory_manager: Any,
        skill_registry: Any,
    ): ...

    def execute(self, request: ChatRequest) -> Iterator[ApplicationResponse]:
        """执行聊天工作流"""
        yield StatusResponse(status=StatusType.THINKING)

        # 1. 加载上下文
        # 2. 运行 ReAct 循环
        # 3. 更新内存
        # ...
        yield DoneResponse()
```

---

## 领域层 API

### LLM Provider 接口

**位置**: `backend/alice/core/interfaces/llm_provider.py`

```python
from typing import Protocol, iter
from dataclasses import dataclass

@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # "system", "user", "assistant"
    content: str

@dataclass
class StreamChunk:
    """流式响应块"""
    content: str
    thinking: str
    is_complete: bool
    tool_calls: list[dict]
    usage: dict | None = None

@dataclass
class ChatResponse:
    """完整聊天响应"""
    content: str
    thinking: str
    tool_calls: list[dict]
    usage: dict

class LLMProvider(Protocol):
    """LLM 提供商接口"""

    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """同步聊天请求"""
        ...

    async def achat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """异步聊天请求"""
        ...

    def stream_chat(self, messages: list[ChatMessage], **kwargs) -> iter[StreamChunk]:
        """流式聊天请求"""
        ...

    def count_tokens(self, messages: list[ChatMessage]) -> int:
        """计算 Token 数量"""
        ...
```

### Memory Store 接口

**位置**: `backend/alice/core/interfaces/memory_store.py`

```python
from typing import Protocol, List
from datetime import datetime

@dataclass
class MemoryEntry:
    """记忆条目"""
    content: str
    timestamp: datetime
    tags: List[str] = None

@dataclass
class RoundEntry:
    """对话轮次"""
    user_input: str
    assistant_response: str
    timestamp: datetime
    thinking: str = ""

class MemoryStore(Protocol):
    """内存存储接口"""

    def add(self, entry: MemoryEntry) -> None:
        """添加记忆条目"""
        ...

    def get_content_text(self) -> str:
        """获取文本内容"""
        ...

    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """搜索记忆"""
        ...

    def clear(self) -> None:
        """清空记忆"""
        ...
```

### Command Executor 接口

**位置**: `backend/alice/core/interfaces/command_executor.py`

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    """执行结果"""
    output: str
    error: str = ""
    exit_code: int = 0
    duration_ms: int = 0

class CommandExecutor(Protocol):
    """命令执行器接口"""

    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令"""
        ...

    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性"""
        ...

    def interrupt(self) -> bool:
        """中断当前执行"""
        ...
```

### Skill Loader 接口

**位置**: `backend/alice/core/interfaces/skill_loader.py`

```python
from typing import Protocol, List
from dataclasses import dataclass

@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    description: str
    license: str = ""
    allowed_tools: List[str] = None
    metadata: dict = None

@dataclass
class Skill:
    """技能"""
    metadata: SkillMetadata
    content: str
    path: str

class SkillLoader(Protocol):
    """技能加载器接口"""

    def load(self, path: str) -> Skill:
        """加载技能"""
        ...

    def discover(self, directory: str) -> List[Skill]:
        """发现目录中的技能"""
        ...

    def refresh(self) -> None:
        """刷新技能列表"""
        ...
```

### 内存管理器 API

**位置**: `backend/alice/domain/memory/services/memory_manager.py`

```python
class MemoryManager:
    """内存管理器"""

    def __init__(
        self,
        working_memory_path: str,
        stm_path: str,
        ltm_path: str,
        llm_provider: Optional[ClientProvider] = None,
        max_working_rounds: int = 30,
        stm_days_to_keep: int = 7,
    ): ...

    def add_working_round(self, round_entry: RoundEntry) -> None:
        """添加工作内存对话轮次"""

    def add_stm_entry(self, content: str, timestamp: Optional[datetime] = None) -> None:
        """添加短期记忆条目"""

    def add_ltm_entry(self, content: str, timestamp: Optional[datetime] = None) -> None:
        """添加长期记忆条目"""

    def get_working_content(self) -> str:
        """获取工作内存文本内容"""

    def get_stm_content(self) -> str:
        """获取短期记忆文本内容"""

    def get_ltm_content(self) -> str:
        """获取长期记忆文本内容"""

    def get_recent_rounds(self, count: int) -> list[RoundEntry]:
        """获取最近的对话轮次"""

    def search_stm(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索短期记忆"""

    def search_ltm(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索长期记忆"""

    def manage_memory(self) -> dict[str, any]:
        """管理短期记忆滚动和长期记忆提炼"""

    def trim_working_memory(self, max_rounds: Optional[int] = None) -> None:
        """裁剪工作内存"""

    def clear_working_memory(self) -> None:
        """清空工作内存"""

    def clear_stm(self) -> None:
        """清空短期记忆"""

    def clear_ltm(self) -> None:
        """清空长期记忆"""

    def get_memory_summary(self) -> dict[str, any]:
        """获取内存摘要信息"""
```

### 执行服务 API

**位置**: `backend/alice/domain/execution/services/execution_service.py`

```python
class ExecutionService:
    """命令执行服务"""

    def __init__(
        self,
        executor: Optional[DockerExecutor] = None,
        snapshot_manager=None
    ): ...

    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult | str:
        """执行命令"""

    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性"""

    def add_security_rule(self, rule) -> None:
        """添加安全规则"""

    def interrupt(self) -> bool:
        """中断当前执行"""
```

### 技能注册表 API

**位置**: `backend/alice/domain/skills/services/skill_registry.py`

```python
class SkillRegistry:
    """技能注册表"""

    def __init__(self, loader: SkillLoader): ...

    def register(self, skill: Skill) -> None:
        """注册技能"""

    def unregister(self, name: str) -> None:
        """注销技能"""

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""

    def list_all(self) -> List[Skill]:
        """列出所有技能"""

    def search(self, query: str) -> List[Skill]:
        """搜索技能"""

    def refresh(self) -> None:
        """刷新技能列表"""

    def get_summary(self) -> dict:
        """获取注册表摘要"""
```

---

## 核心层 API

### 依赖注入容器

**位置**: `backend/alice/core/container/container.py`

```python
from typing import Type, TypeVar, Callable, Optional

T = TypeVar("T")

class Container:
    """依赖注入容器"""

    def __init__(self): ...

    def register_singleton(
        self,
        interface: Type[T],
        implementation: Type[T] | Callable[[], T],
        instance: Optional[T] = None
    ) -> None:
        """注册单例服务"""

    def register_factory(
        self,
        interface: Type[T],
        factory: Callable[[], T]
    ) -> None:
        """注册工厂服务"""

    def register_transient(
        self,
        interface: Type[T],
        implementation: Type[T]
    ) -> None:
        """注册瞬态服务（每次解析创建新实例）"""

    def get(self, interface: Type[T]) -> T:
        """解析服务"""

    def has(self, interface: Type) -> bool:
        """检查服务是否已注册"""

    def clear(self) -> None:
        """清空所有注册的服务"""

# 全局容器实例
def get_container() -> Container:
    """获取全局容器实例"""

def reset_container() -> None:
    """重置全局容器"""
```

### 事件总线

**位置**: `backend/alice/core/event_bus/event_bus.py`

```python
from typing import Callable, Type, List
from dataclasses import dataclass

@dataclass
class Event:
    """事件基类"""
    pass

class EventHandler(Protocol):
    """事件处理器接口"""
    def handle(self, event: Event) -> None: ...

class EventBus:
    """事件总线"""

    def __init__(self): ...

    def subscribe(self, event_type: Type[Event], handler: Callable[[Event], None]) -> None:
        """订阅事件"""

    def unsubscribe(self, event_type: Type[Event], handler: Callable[[Event], None]) -> None:
        """取消订阅"""

    def publish(self, event: Event) -> None:
        """同步发布事件"""

    async def async_publish(self, event: Event) -> None:
        """异步发布事件"""

    def clear(self) -> None:
        """清空所有订阅"""
```

### 配置管理

**位置**: `backend/alice/core/config/settings.py`

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class LLMConfig:
    """LLM 配置"""
    model_name: str = "gpt-4"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.7
    enable_thinking: bool = True
    timeout: int = 120

@dataclass
class MemoryConfig:
    """内存配置"""
    working_memory_max_rounds: int = 30
    stm_expiry_days: int = 7
    ltm_auto_distill: bool = True
    working_memory_path: str = "memory/working_memory.md"
    stm_path: str = "memory/short_term_memory.md"
    ltm_path: str = "memory/alice_memory.md"
    todo_path: str = "memory/todo.md"

@dataclass
class DockerConfig:
    """Docker 配置"""
    image_name: str = "alice-sandbox:latest"
    container_name: str = "alice-sandbox-instance"
    work_dir: str = "/app"
    mounts: Dict[str, str] = field(default_factory=lambda: {
        "skills": "/app/skills",
        "alice_output": "/app/alice_output",
    })
    timeout: int = 120

@dataclass
class Settings:
    """主配置类"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    # ... 其他配置

    project_root: Path = field(default_factory=lambda: Path.cwd())
    prompt_path: str = "prompts/alice.md"
    skills_dir: str = "skills"
    output_dir: str = "alice_output"

    def get_absolute_path(self, relative_path: str) -> Path:
        """获取绝对路径"""
```

### 装饰器

**位置**: `backend/alice/core/container/decorators.py`

```python
from functools import wraps
from typing import Callable

def inject(*dependencies: Type):
    """依赖注入装饰器

    用法:
        @inject(IMemoryStore, LLMProvider)
        def my_function(memory: IMemoryStore, llm: LLMProvider):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            container = get_container()
            resolved = [container.get(dep) for dep in dependencies]
            return func(*resolved, *args, **kwargs)
        return wrapper
    return decorator

def singleton(cls: Type[T]) -> Type[T]:
    """单例装饰器

    用法:
        @singleton
        class MyService:
            pass
    """
    instances = {}
    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance
```

---

## 使用示例

### 基本聊天请求

```python
from backend.alice.application.dto import ChatRequest
from backend.alice.application.workflow import ChatWorkflow

# 创建请求
request = ChatRequest(
    input="帮我分析这个数据文件",
    enable_thinking=True,
    stream=True
)

# 执行工作流
workflow = ChatWorkflow(agent, memory_manager, skill_registry)
for response in workflow.execute(request):
    if response.response_type == ResponseType.THINKING:
        print(f"[思考] {response.content}")
    elif response.response_type == ResponseType.CONTENT:
        print(f"[内容] {response.content}")
    elif response.response_type == ResponseType.DONE:
        print("[完成]")
```

### 使用依赖注入

```python
from backend.alice.core.container import Container, get_container
from backend.alice.core.interfaces import LLMProvider, IMemoryStore

# 创建容器
container = Container()

# 注册服务
container.register_singleton(
    LLMProvider,
    OpenAIProvider(api_key="...", model="gpt-4")
)
container.register_singleton(
    IMemoryStore,
    MemoryManager(...)
)

# 解析服务
llm = container.get(LLMProvider)
memory = container.get(IMemoryStore)
```

### 自定义 LLM Provider

```python
from backend.alice.core.interfaces.llm_provider import (
    LLMProvider, ChatMessage, ChatResponse, StreamChunk
)

class CustomLLMProvider:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        # 实现聊天逻辑
        ...

    def stream_chat(self, messages: list[ChatMessage], **kwargs) -> iter[StreamChunk]:
        # 实现流式聊天
        ...

    def count_tokens(self, messages: list[ChatMessage]) -> int:
        # 实现 Token 计数
        ...

# 注册自定义 Provider
container.register_singleton(LLMProvider, CustomLLMProvider)
```
