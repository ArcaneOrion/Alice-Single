"""
Workflow Protocol

定义工作流的基础接口和抽象类。
"""

from abc import ABC, abstractmethod
from typing import Any, Iterator
from dataclasses import dataclass

from ..dto import ApplicationResponse, RequestContext
from ..runtime import RuntimeContext


RuntimeContextPayload = RuntimeContext


@dataclass
class WorkflowContext:
    """工作流上下文

    包含工作流执行过程中的共享状态。

    Attributes:
        request_context: 原始请求上下文
        user_input: 用户输入
        messages: 消息历史
        interrupted: 是否被中断
        metadata: 额外的元数据
    """

    request_context: RequestContext
    user_input: str
    messages: list
    interrupted: bool = False
    metadata: dict[str, Any] | None = None
    runtime_context: RuntimeContextPayload | None = None

    def __init__(
        self,
        request_context: RequestContext,
        user_input: str,
        messages: list | None = None,
        interrupted: bool = False,
        metadata: dict | None = None,
        runtime_context: RuntimeContextPayload | None = None,
    ):
        self.request_context = request_context
        self.user_input = user_input
        self.messages = messages or []
        self.interrupted = interrupted
        self.metadata = metadata or {}
        self.runtime_context = runtime_context


class Workflow(ABC):
    """工作流抽象基类

    定义工作流的执行接口。
    """

    @abstractmethod
    def can_handle(self, context: RequestContext) -> bool:
        """判断是否可以处理该请求

        Args:
            context: 请求上下文

        Returns:
            是否可以处理
        """
        pass

    @abstractmethod
    def execute(self, context: WorkflowContext) -> Iterator[ApplicationResponse]:
        """执行工作流

        Args:
            context: 工作流上下文

        Yields:
            应用响应
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """工作流名称"""
        pass

    def cleanup(self) -> None:
        """清理工作流资源

        子类可以重写此方法来释放资源。
        """
        pass


class WorkflowChain:
    """工作流链

    按顺序尝试多个工作流，直到找到可以处理的工作流。
    """

    def __init__(self, workflows: list[Workflow] | None = None):
        """初始化工作流链

        Args:
            workflows: 工作流列表（按优先级排序）
        """
        self.workflows = workflows or []

    def add_workflow(self, workflow: Workflow) -> None:
        """添加工作流到链中

        Args:
            workflow: 要添加的工作流
        """
        self.workflows.append(workflow)

    def process(self, context: WorkflowContext) -> Iterator[ApplicationResponse]:
        """处理请求

        Args:
            context: 工作流上下文

        Yields:
            应用响应

        Raises:
            ValueError: 如果没有工作流可以处理该请求
        """
        for workflow in self.workflows:
            if workflow.can_handle(context.request_context):
                yield from workflow.execute(context)
                return

        # 没有工作流可以处理
        from ..dto import ErrorResponse

        yield ErrorResponse(
            content=f"No workflow can handle request type: {context.request_context.request_type}",
            code="NO_WORKFLOW",
        )

    def cleanup_all(self) -> None:
        """清理所有工作流的资源"""
        for workflow in self.workflows:
            workflow.cleanup()


__all__ = [
    "WorkflowContext",
    "Workflow",
    "WorkflowChain",
]
