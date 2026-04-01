"""
请求数据传输对象 (DTO)

定义应用层接收的请求数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..runtime import RuntimeContext


class RequestType(str, Enum):
    """请求类型枚举"""

    CHAT = "chat"
    INTERRUPT = "interrupt"
    STATUS = "status"
    REFRESH = "refresh"


@dataclass(frozen=True)
class ChatRequest:
    """聊天请求

    Attributes:
        input: 用户输入内容
        session_id: 会话 ID（可选）
        enable_thinking: 是否启用思考模式
        stream: 是否使用流式响应
        metadata: 请求级元数据
    """

    input: str
    session_id: Optional[str] = None
    enable_thinking: bool = True
    stream: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterruptRequest:
    """中断请求

    用于中断当前正在执行的生成或工具调用。
    """

    session_id: Optional[str] = None


@dataclass(frozen=True)
class StatusRequest:
    """状态请求

    获取当前代理状态。
    """

    include_memory: bool = False
    include_skills: bool = False


@dataclass(frozen=True)
class RefreshRequest:
    """刷新请求

    刷新技能索引或内存快照。
    """

    refresh_type: str = "all"  # "all", "skills", "memory"


# 联合类型：所有可能的请求
ApplicationRequest = ChatRequest | InterruptRequest | StatusRequest | RefreshRequest


@dataclass
class RequestContext:
    """请求上下文

    包含请求处理过程中的上下文信息。

    Attributes:
        request_type: 请求类型
        user_input: 用户输入（如果有）
        interrupted: 是否被中断
        metadata: 额外的元数据
    """

    request_type: RequestType
    user_input: str = ""
    interrupted: bool = False
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_chat_request(cls, request: ChatRequest) -> "RequestContext":
        """从聊天请求创建上下文"""
        metadata = dict(request.metadata or {})
        metadata.update(
            {
                "session_id": request.session_id,
                "enable_thinking": request.enable_thinking,
                "stream": request.stream,
            }
        )
        return cls(
            request_type=RequestType.CHAT,
            user_input=request.input,
            metadata=metadata,
        )

    @classmethod
    def from_interrupt(cls, session_id: Optional[str] = None) -> "RequestContext":
        """从中断请求创建上下文"""
        return cls(
            request_type=RequestType.INTERRUPT,
            interrupted=True,
            metadata={"session_id": session_id},
        )


@dataclass
class WorkflowContext:
    """工作流上下文

    包含工作流执行过程中需要的上下文信息。

    Attributes:
        request_context: 请求上下文
        user_input: 用户输入
        messages: 消息历史
        interrupted: 是否被中断
        metadata: 工作流级元数据
        runtime_context: 结构化运行时上下文
    """

    request_context: RequestContext
    user_input: str
    messages: list = field(default_factory=list)
    interrupted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_context: RuntimeContext | None = None


__all__ = [
    "RequestType",
    "ChatRequest",
    "InterruptRequest",
    "StatusRequest",
    "RefreshRequest",
    "ApplicationRequest",
    "RequestContext",
    "WorkflowContext",
]
