"""
Alice Agent - 应用层主协调器

协调 Domain 层服务，实现应用编排逻辑。
"""

import logging
import os
from pathlib import Path
from typing import Iterator, Optional

from ..dto import (
    ApplicationResponse,
    RequestContext,
    WorkflowContext,
    StatusResponse,
    DoneResponse,
    ErrorResponse,
    AgentStatus,
    StatusType,
)
from ..workflow import WorkflowChain, ChatWorkflow
from ..services import OrchestrationService, LifecycleService


logger = logging.getLogger(__name__)


class AliceAgent:
    """Alice 智能体

    应用层的主协调器，负责：
    - 协调 Domain 层服务
    - 管理工作流
    - 处理中断
    - 维护会话状态
    """

    def __init__(
        self,
        orchestration_service: Optional[OrchestrationService] = None,
        lifecycle_service: Optional[LifecycleService] = None,
        workflow_chain: Optional[WorkflowChain] = None,
    ):
        """初始化 Alice 智能体

        Args:
            orchestration_service: 编排服务
            lifecycle_service: 生命周期服务
            workflow_chain: 工作流链
        """
        self.orchestration = orchestration_service
        self.lifecycle = lifecycle_service
        self.workflow_chain = workflow_chain

        # 状态管理
        self._status = AgentStatus(state=StatusType.READY)
        self._interrupted = False
        self._request_count = 0

        # 初始化生命周期
        if self.lifecycle:
            self.lifecycle.initialize()

        logger.info("Alice Agent 初始化完成")

    @property
    def status(self) -> AgentStatus:
        """获取当前状态"""
        return self._status

    @property
    def is_interrupted(self) -> bool:
        """是否被中断"""
        return self._interrupted

    @property
    def is_ready(self) -> bool:
        """是否就绪"""
        return self._status.state == StatusType.READY

    def process(self, request: RequestContext) -> Iterator[ApplicationResponse]:
        """处理请求

        Args:
            request: 请求上下文

        Yields:
            应用响应
        """
        self._interrupted = False
        self._request_count += 1

        # 更新状态
        self._status.state = StatusType.THINKING

        try:
            # 创建工作流上下文
            messages = []
            if self.orchestration and self.orchestration.chat_service:
                messages = self.orchestration.chat_service.messages

            workflow_context = WorkflowContext(
                request_context=request,
                user_input=request.user_input,
                messages=messages,
                interrupted=self._interrupted,
            )

            # 执行工作流链
            if self.workflow_chain:
                yield from self.workflow_chain.process(workflow_context)
            else:
                yield ErrorResponse(
                    content="No workflow chain configured",
                    code="NO_WORKFLOW_CHAIN",
                )

        except Exception as e:
            logger.error(f"处理请求时发生错误: {e}", exc_info=True)
            yield ErrorResponse(
                content=f"Request processing failed: {str(e)}",
                code="PROCESSING_ERROR",
            )

        finally:
            # 恢复状态
            self._status.state = StatusType.READY

    def chat(self, user_input: str, **kwargs) -> Iterator[ApplicationResponse]:
        """处理聊天请求

        Args:
            user_input: 用户输入
            **kwargs: 额外参数

        Yields:
            应用响应
        """
        from ..dto import ChatRequest

        request = ChatRequest(input=user_input, **kwargs)
        context = RequestContext.from_chat_request(request)

        yield from self.process(context)

    def interrupt(self) -> None:
        """中断当前执行"""
        logger.info("收到中断信号")
        self._interrupted = True

        # 传播中断到工作流
        if self.workflow_chain:
            self.workflow_chain.cleanup_all()

        # 传播中断到编排服务
        if self.orchestration:
            if self.orchestration.execution_service:
                self.orchestration.execution_service.interrupt()

    def get_status(self) -> AgentStatus:
        """获取详细状态

        Returns:
            代理状态
        """
        memory_summary = {}
        skills_count = 0

        if self.orchestration:
            if self.orchestration.memory_manager:
                memory_summary = self.orchestration.memory_manager.get_memory_summary()
            if self.orchestration.skill_registry:
                skills_count = self.orchestration.skill_registry.get_skill_count()

        model_name = ""
        if self.orchestration and self.orchestration.chat_service:
            model_name = self.orchestration.chat_service.provider.model_name

        return AgentStatus(
            state=self._status.state,
            model_name=model_name,
            total_requests=self._request_count,
            memory_summary=memory_summary,
            skills_count=skills_count,
        )

    def refresh_skills(self) -> int:
        """刷新技能注册表

        Returns:
            注册的技能数量
        """
        if self.orchestration and self.orchestration.skill_registry:
            return self.orchestration.skill_registry.refresh()
        return 0

    def manage_memory(self) -> dict:
        """管理内存（滚动和提炼）

        Returns:
            操作结果
        """
        if self.orchestration and self.orchestration.memory_manager:
            return self.orchestration.memory_manager.manage_memory()
        return {"status": "skipped", "reason": "no memory manager"}

    def clear_working_memory(self) -> None:
        """清空工作内存"""
        if self.orchestration and self.orchestration.memory_manager:
            self.orchestration.memory_manager.clear_working_memory()

    def shutdown(self) -> None:
        """关闭代理"""
        logger.info("正在关闭 Alice Agent...")

        # 清理工作流
        if self.workflow_chain:
            self.workflow_chain.cleanup_all()

        # 关闭生命周期
        if self.lifecycle:
            self.lifecycle.shutdown()

        self._status.state = StatusType.DONE
        logger.info("Alice Agent 已关闭")


__all__ = ["AliceAgent"]
