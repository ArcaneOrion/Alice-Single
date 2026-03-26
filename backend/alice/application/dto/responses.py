"""
响应数据传输对象 (DTO)

定义应用层返回的响应数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


class ResponseType(str, Enum):
    """响应类型枚举"""

    CONTENT = "content"
    THINKING = "thinking"
    STATUS = "status"
    ERROR = "error"
    TOKENS = "tokens"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"


class StatusType(str, Enum):
    """状态类型枚举"""

    READY = "ready"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"
    ERROR = "error"


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
    tool_type: str = ""  # "python" or "bash"
    command_preview: str = ""


@dataclass(frozen=True)
class DoneResponse(BaseResponse):
    """完成响应

    通知前端当前操作完成。
    """

    response_type: ResponseType = ResponseType.DONE


# 联合类型：所有可能的响应
ApplicationResponse = (
    ContentResponse
    | ThinkingResponse
    | StatusResponse
    | ErrorResponse
    | TokensResponse
    | ExecutingToolResponse
    | DoneResponse
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


def response_to_dict(response: ApplicationResponse) -> dict[str, Any]:
    """将响应转换为字典（用于 JSON 序列化）

    Args:
        response: 响应对象

    Returns:
        字典格式的响应
    """
    if isinstance(response, ContentResponse):
        return {"type": "content", "content": response.content}
    elif isinstance(response, ThinkingResponse):
        return {"type": "thinking", "content": response.content}
    elif isinstance(response, StatusResponse):
        return {"type": "status", "content": response.status.value}
    elif isinstance(response, ErrorResponse):
        return {"type": "error", "content": response.content, "code": response.code}
    elif isinstance(response, TokensResponse):
        return {
            "type": "tokens",
            "total": response.total,
            "prompt": response.prompt,
            "completion": response.completion,
        }
    elif isinstance(response, ExecutingToolResponse):
        return {"type": "executing_tool", "tool_type": response.tool_type}
    elif isinstance(response, DoneResponse):
        return {"type": "status", "content": "done"}
    else:
        return {"type": "unknown"}


__all__ = [
    "ResponseType",
    "StatusType",
    "BaseResponse",
    "ContentResponse",
    "ThinkingResponse",
    "StatusResponse",
    "ErrorResponse",
    "TokensResponse",
    "ExecutingToolResponse",
    "DoneResponse",
    "ApplicationResponse",
    "ChatResult",
    "AgentStatus",
    "response_to_dict",
]
