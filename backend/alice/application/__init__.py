"""
Application 层。

协调 Domain 层服务，实现应用编排逻辑。

该包仅提供稳定的导出名；具体对象采用惰性导入，
避免导入子包时触发不必要的跨层初始化与循环依赖。
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent import AliceAgent
    from .dto import (
        AgentStatus,
        ApplicationRequest,
        ApplicationResponse,
        BaseResponse,
        ChatRequest,
        ChatResult,
        ContentResponse,
        DoneResponse,
        ErrorResponse,
        ExecutingToolResponse,
        InterruptRequest,
        RefreshRequest,
        RequestContext,
        RequestType,
        ResponseType,
        StatusRequest,
        StatusResponse,
        StatusType,
        ThinkingResponse,
        TokensResponse,
        response_to_dict,
    )
    from .services import LifecycleService, OrchestrationService
    from .workflow import ChatWorkflow, ToolWorkflow, Workflow, WorkflowChain, WorkflowContext

__all__ = [
    # Agent
    "AliceAgent",
    # Workflow
    "Workflow",
    "WorkflowContext",
    "WorkflowChain",
    "ChatWorkflow",
    "ToolWorkflow",
    # Services
    "OrchestrationService",
    "LifecycleService",
    # DTO - Requests
    "RequestType",
    "ChatRequest",
    "InterruptRequest",
    "StatusRequest",
    "RefreshRequest",
    "ApplicationRequest",
    "RequestContext",
    # DTO - Responses
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

_EXPORT_MODULES = {
    # Agent
    "AliceAgent": ".agent",
    # Workflow
    "Workflow": ".workflow",
    "WorkflowContext": ".workflow",
    "WorkflowChain": ".workflow",
    "ChatWorkflow": ".workflow",
    "ToolWorkflow": ".workflow",
    # Services
    "OrchestrationService": ".services",
    "LifecycleService": ".services",
    # DTO
    "RequestType": ".dto",
    "ChatRequest": ".dto",
    "InterruptRequest": ".dto",
    "StatusRequest": ".dto",
    "RefreshRequest": ".dto",
    "ApplicationRequest": ".dto",
    "RequestContext": ".dto",
    "ResponseType": ".dto",
    "StatusType": ".dto",
    "BaseResponse": ".dto",
    "ContentResponse": ".dto",
    "ThinkingResponse": ".dto",
    "StatusResponse": ".dto",
    "ErrorResponse": ".dto",
    "TokensResponse": ".dto",
    "ExecutingToolResponse": ".dto",
    "DoneResponse": ".dto",
    "ApplicationResponse": ".dto",
    "ChatResult": ".dto",
    "AgentStatus": ".dto",
    "response_to_dict": ".dto",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
