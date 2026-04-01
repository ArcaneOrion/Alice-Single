"""
数据传输对象 (DTO) 包

包含应用层的请求和响应数据结构。
"""

from .requests import (
    RequestType,
    ChatRequest,
    InterruptRequest,
    StatusRequest,
    RefreshRequest,
    ApplicationRequest,
    RequestContext,
    WorkflowContext,
)

from .responses import (
    ResponseType,
    StatusType,
    RuntimeEventType,
    StructuredToolCall,
    StructuredToolResult,
    StructuredRuntimeOutput,
    BaseResponse,
    ContentResponse,
    ThinkingResponse,
    StatusResponse,
    ErrorResponse,
    TokensResponse,
    ExecutingToolResponse,
    DoneResponse,
    RuntimeEventResponse,
    ApplicationResponse,
    ChatResult,
    AgentStatus,
    response_to_dict,
)

__all__ = [
    # Requests
    "RequestType",
    "ChatRequest",
    "InterruptRequest",
    "StatusRequest",
    "RefreshRequest",
    "ApplicationRequest",
    "RequestContext",
    "WorkflowContext",
    # Responses
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
    "response_to_dict",
]
