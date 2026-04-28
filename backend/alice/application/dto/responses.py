"""
响应数据传输对象 (DTO)

定义应用层返回的响应数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResponseType(str, Enum):
    """响应类型枚举"""

    CONTENT = "content"
    THINKING = "thinking"
    STATUS = "status"
    ERROR = "error"
    TOKENS = "tokens"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"
    RUNTIME_EVENT = "runtime_event"


class StatusType(str, Enum):
    """状态类型枚举"""

    READY = "ready"
    THINKING = "thinking"
    STREAMING = "streaming"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class RuntimeEventType(str, Enum):
    """运行时事件类型枚举"""

    STATUS_CHANGED = "status_changed"
    REASONING_DELTA = "reasoning_delta"
    CONTENT_DELTA = "content_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_ARGUMENT_DELTA = "tool_call_argument_delta"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_RESULT = "tool_result"
    USAGE_UPDATED = "usage_updated"
    MESSAGE_COMPLETED = "message_completed"
    ERROR_RAISED = "error_raised"
    INTERRUPT_ACK = "interrupt_ack"


@dataclass(frozen=True)
class StructuredToolCall:
    """结构化工具调用。"""

    index: int = 0
    id: str = ""
    type: str = "function"
    function_name: str = ""
    function_arguments: str = ""

    @property
    def function(self) -> dict[str, str]:
        return {
            "name": self.function_name,
            "arguments": self.function_arguments,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StructuredToolCall":
        function = payload.get("function") or {}
        return cls(
            index=int(payload.get("index") or 0),
            id=str(payload.get("id") or ""),
            type=str(payload.get("type") or "function"),
            function_name=str(function.get("name") or payload.get("function_name") or ""),
            function_arguments=str(function.get("arguments") or payload.get("function_arguments") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "id": self.id,
            "type": self.type,
            "function": dict(self.function),
        }


@dataclass(frozen=True)
class StructuredToolResult:
    """结构化工具结果。"""

    tool_call_id: str = ""
    tool_type: str = ""
    content: str = ""
    status: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return self.tool_type

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StructuredToolResult":
        return cls(
            tool_call_id=str(payload.get("tool_call_id") or ""),
            tool_type=str(payload.get("type") or payload.get("tool_type") or ""),
            content=str(payload.get("content") or ""),
            status=str(payload.get("status") or "success"),
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "type": self.tool_type,
            "content": self.content,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StructuredRuntimeOutput:
    """后端 canonical structured runtime 输出"""

    message_id: str = ""
    status: str = ""
    reasoning: str = ""
    content: str = ""
    tool_calls: list[StructuredToolCall] = field(default_factory=list)
    tool_results: list[StructuredToolResult] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "status": self.status,
            "reasoning": self.reasoning,
            "content": self.content,
            "tool_calls": [tool_call.to_dict() for tool_call in self.tool_calls],
            "tool_results": [tool_result.to_dict() for tool_result in self.tool_results],
            "usage": dict(self.usage),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BaseResponse:
    """响应基类"""

    response_type: ResponseType


@dataclass(frozen=True)
class ContentResponse(BaseResponse):
    """正文响应

    显示在主聊天区的内容。
    """

    response_type: ResponseType = ResponseType.CONTENT
    content: str = ""


@dataclass(frozen=True)
class ThinkingResponse(BaseResponse):
    """思考响应

    显示在思考侧边栏的内容。
    """

    response_type: ResponseType = ResponseType.THINKING
    content: str = ""


@dataclass(frozen=True)
class StatusResponse(BaseResponse):
    """状态响应

    通知前端当前运行状态。
    """

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
    """执行工具响应

    通知前端正在执行工具。
    """

    response_type: ResponseType = ResponseType.EXECUTING_TOOL
    tool_type: str = ""
    command_preview: str = ""


@dataclass(frozen=True)
class DoneResponse(BaseResponse):
    """完成响应

    通知前端当前操作完成。
    """

    response_type: ResponseType = ResponseType.DONE


@dataclass(frozen=True)
class RuntimeEventResponse(BaseResponse):
    """内部 structured runtime 事件响应"""

    response_type: ResponseType = ResponseType.RUNTIME_EVENT
    event_type: RuntimeEventType = RuntimeEventType.STATUS_CHANGED
    payload: dict[str, Any] = field(default_factory=dict)
    runtime_output: StructuredRuntimeOutput | None = None


# 联合类型：所有可能的响应
ApplicationResponse = (
    ContentResponse
    | ThinkingResponse
    | StatusResponse
    | ErrorResponse
    | TokensResponse
    | ExecutingToolResponse
    | DoneResponse
    | RuntimeEventResponse
)


@dataclass
class ChatResult:
    """聊天结果

    一次完整对话的最终结果。

    Attributes:
        content: 完整的正文内容
        thinking: 完整的思考内容
        tokens: Token 使用统计
        tool_calls: 执行的工具调用
        is_interrupted: 是否被中断
    """

    content: str = ""
    thinking: str = ""
    tokens: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    is_interrupted: bool = False

    def has_content(self) -> bool:
        """是否有正文内容"""
        return bool(self.content)

    def has_thinking(self) -> bool:
        """是否有思考内容"""
        return bool(self.thinking)

    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return bool(self.tool_calls)


@dataclass
class AgentStatus:
    """代理状态

    Attributes:
        state: 当前状态
        model_name: 使用的模型名称
        total_requests: 总请求数
        memory_summary: 内存摘要
        skills_count: 已注册技能数量
    """

    state: StatusType = StatusType.READY
    model_name: str = ""
    total_requests: int = 0
    memory_summary: dict = field(default_factory=dict)
    skills_count: int = 0


__all__ = [
    "ResponseType",
    "StatusType",
    "RuntimeEventType",
    "StructuredToolCall",
    "StructuredToolResult",
    "StructuredRuntimeOutput",
    "BaseResponse",
    "ContentResponse",
    "ThinkingResponse",
    "StatusResponse",
    "ErrorResponse",
    "TokensResponse",
    "ExecutingToolResponse",
    "DoneResponse",
    "RuntimeEventResponse",
    "ApplicationResponse",
    "ChatResult",
    "AgentStatus",
]
