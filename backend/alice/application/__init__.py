"""
Application 层

协调 Domain 层服务，实现应用编排逻辑。

主要组件：
- Agent: 主协调器
- Workflow: 工作流实现
- Services: 应用服务
- DTO: 数据传输对象
"""

# Agent
from .agent import AliceAgent, ReActLoop, ReActConfig, ReActState

# Workflow
from .workflow import Workflow, WorkflowContext, WorkflowChain, ChatWorkflow, ToolWorkflow

# Services
from .services import OrchestrationService, LifecycleService

# DTO
from .dto import (
    RequestType,
    ChatRequest,
    InterruptRequest,
    StatusRequest,
    RefreshRequest,
    ApplicationRequest,
    RequestContext,
    ResponseType,
    StatusType,
    BaseResponse,
    ContentResponse,
    ThinkingResponse,
    StatusResponse,
    ErrorResponse,
    TokensResponse,
    ExecutingToolResponse,
    DoneResponse,
    ApplicationResponse,
    ChatResult,
    AgentStatus,
    response_to_dict,
)

__all__ = [
    # Agent
    "AliceAgent",
    "ReActLoop",
    "ReActConfig",
    "ReActState",
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
