"""
工具执行工作流

处理独立的工具执行请求。
"""

import logging
from typing import Iterator

from .base_workflow import Workflow, WorkflowContext
from ..dto import (
    ApplicationResponse,
    RequestContext,
    StatusResponse,
    ContentResponse,
    ExecutingToolResponse,
    DoneResponse,
    ErrorResponse,
    StatusType,
    RequestType,
)


logger = logging.getLogger(__name__)


class ToolWorkflow(Workflow):
    """工具执行工作流

    处理直接的工具执行请求，不经过 LLM。
    """

    def __init__(self, execution_service=None):
        """初始化工具工作流

        Args:
            execution_service: 执行服务
        """
        self.execution_service = execution_service

    @property
    def name(self) -> str:
        return "ToolWorkflow"

    def can_handle(self, context: RequestContext) -> bool:
        """判断是否可以处理该请求

        工具工作流作为兜底，可以处理任何包含有效命令的请求。
        """
        # 实际上，工具工作流不主动处理，由聊天工作流调用
        return False

    def execute(
        self, context: WorkflowContext, command: str, is_python: bool = False
    ) -> Iterator[ApplicationResponse]:
        """执行工具命令

        Args:
            context: 工作流上下文
            command: 要执行的命令
            is_python: 是否为 Python 代码

        Yields:
            应用响应
        """
        yield ExecutingToolResponse(
            tool_type="python" if is_python else "bash",
            command_preview=command[:100],
        )

        try:
            if self.execution_service:
                result = self.execution_service.execute(command, is_python_code=is_python)
            else:
                result = "执行服务不可用"

            yield ContentResponse(content=result)
            yield DoneResponse()

        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            yield ErrorResponse(content=f"Tool execution failed: {str(e)}", code="EXEC_ERROR")


__all__ = ["ToolWorkflow"]
