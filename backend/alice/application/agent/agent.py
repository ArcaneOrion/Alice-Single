"""
Alice Agent - 应用层主协调器

协调 Domain 层服务，实现应用编排逻辑。
"""

import logging
import time
import traceback
from typing import Iterator, Optional
from uuid import uuid4

from ..dto import (
    ApplicationResponse,
    RequestContext,
    ErrorResponse,
    AgentStatus,
    StatusType,
)
from ..workflow import WorkflowChain, WorkflowContext
from ..services import OrchestrationService, LifecycleService
from ..runtime import RuntimeContextBuilder


logger = logging.getLogger(__name__)


def _ensure_request_correlation_ids(request: RequestContext) -> dict:
    """确保请求携带完整链路标识并回写 metadata。"""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    metadata = dict(metadata)

    session_id = metadata.get("session_id") or ""
    trace_id = metadata.get("trace_id") or metadata.get("request_id") or uuid4().hex
    request_id = metadata.get("request_id") or trace_id
    task_id = metadata.get("task_id") or request_id or session_id or trace_id
    span_id = metadata.get("span_id") or f"agent.{uuid4().hex[:12]}"

    metadata["session_id"] = session_id
    metadata["trace_id"] = trace_id
    metadata["request_id"] = request_id
    metadata["task_id"] = task_id
    metadata["span_id"] = span_id
    request.metadata = metadata
    return metadata


def _extract_request_logging_context(request: RequestContext, phase: str) -> dict:
    """提取请求日志上下文（兼容缺省字段）"""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    session_id = str(metadata.get("session_id") or "")
    trace_id = str(metadata.get("trace_id") or metadata.get("request_id") or "")
    request_id = str(metadata.get("request_id") or trace_id)
    task_id = str(metadata.get("task_id") or request_id or session_id)
    span_id = str(metadata.get("span_id") or "")

    return {
        "trace_id": trace_id,
        "task_id": task_id,
        "request_id": request_id,
        "session_id": session_id,
        "span_id": span_id,
        "component": "agent",
        "phase": phase,
        "request_type": request.request_type.value,
    }


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
        self._active_log_context: dict | None = None
        self._active_workflow_context: WorkflowContext | None = None
        self._runtime_context_builder = RuntimeContextBuilder()

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
        started_at = time.monotonic()
        _ensure_request_correlation_ids(request)
        log_context = _extract_request_logging_context(request, phase="request_received")
        self._active_log_context = dict(log_context)

        logger.info(
            "Agent task started",
            extra={
                "event_type": "task.started",
                "log_category": "tasks",
                "context": log_context,
                "task_id": log_context["task_id"],
                "data": {
                    "request_count": self._request_count,
                    "user_input_length": len(request.user_input),
                    "legacy_event_type": "task_start",
                    "timing": {"duration_ms": 0},
                },
            },
        )

        # 更新状态
        self._status.state = StatusType.THINKING

        try:
            # 创建工作流上下文
            messages = []
            if self.orchestration and self.orchestration.chat_service:
                messages = self.orchestration.chat_service.messages

            runtime_context = self._runtime_context_builder.build(
                system_prompt=(
                    self.orchestration.chat_service.system_prompt
                    if self.orchestration and self.orchestration.chat_service
                    else ""
                ),
                current_question=request.user_input,
                messages=messages,
                request_metadata=request.metadata,
                memory_manager=self.orchestration.memory_manager if self.orchestration else None,
                skill_registry=self.orchestration.skill_registry if self.orchestration else None,
                tool_registry=self.orchestration.tool_registry if self.orchestration else None,
            )
            request_envelope = self._runtime_context_builder.build_request_envelope(
                runtime_context=runtime_context,
                messages=messages,
            )
            workflow_context = WorkflowContext(
                request_context=request,
                user_input=request.user_input,
                messages=messages,
                interrupted=self._interrupted,
                metadata=dict(request.metadata or {}),
                runtime_context=runtime_context,
                request_envelope=request_envelope,
            )
            self._active_workflow_context = workflow_context

            # 执行工作流链
            if self.workflow_chain:
                yield from self.workflow_chain.process(workflow_context)
                duration_ms = int((time.monotonic() - started_at) * 1000)
                if self._interrupted:
                    logger.warning(
                        "Agent task interrupted",
                        extra={
                            "event_type": "task.failed",
                            "log_category": "tasks",
                            "context": _extract_request_logging_context(
                                request, phase="interrupted"
                            ),
                            "task_id": log_context["task_id"],
                            "data": {
                                "interrupted": True,
                                "legacy_event_type": "interrupt_received",
                                "timing": {"duration_ms": duration_ms},
                            },
                            "error": {
                                "type": "INTERRUPTED",
                                "message": "Task interrupted by user",
                            },
                        },
                    )
                else:
                    logger.info(
                        "Agent task completed",
                        extra={
                            "event_type": "task.completed",
                            "log_category": "tasks",
                            "context": _extract_request_logging_context(
                                request, phase="completed"
                            ),
                            "task_id": log_context["task_id"],
                            "data": {
                                "interrupted": False,
                                "legacy_event_type": "task_complete",
                                "timing": {"duration_ms": duration_ms},
                            },
                        },
                    )
            else:
                logger.error(
                    "No workflow chain configured",
                    extra={
                        "event_type": "task.failed",
                        "log_category": "tasks",
                        "context": _extract_request_logging_context(
                            request, phase="failed"
                        ),
                        "task_id": log_context["task_id"],
                        "data": {
                            "error_code": "NO_WORKFLOW_CHAIN",
                            "legacy_event_type": "task_error",
                            "timing": {
                                "duration_ms": int((time.monotonic() - started_at) * 1000)
                            },
                        },
                        "error": {
                            "type": "NO_WORKFLOW_CHAIN",
                            "message": "No workflow chain configured",
                        },
                    },
                )
                yield ErrorResponse(
                    content="No workflow chain configured",
                    code="NO_WORKFLOW_CHAIN",
                )

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(
                "Request processing failed",
                exc_info=True,
                extra={
                    "event_type": "task.failed",
                    "log_category": "tasks",
                    "context": _extract_request_logging_context(request, phase="failed"),
                    "task_id": log_context["task_id"],
                    "data": {
                        "legacy_event_type": "task_error",
                        "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                    },
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": error_trace,
                    },
                },
            )
            yield ErrorResponse(
                content=f"Request processing failed: {str(e)}",
                code="PROCESSING_ERROR",
            )

        finally:
            # 恢复状态
            self._status.state = StatusType.READY
            self._active_log_context = None
            self._active_workflow_context = None

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
        active_context = dict(self._active_log_context or {})
        active_context.setdefault("trace_id", "")
        active_context.setdefault("request_id", "")
        active_context.setdefault("task_id", "")
        active_context.setdefault("session_id", "")
        active_context["span_id"] = (
            f"{active_context.get('span_id')}.interrupt"
            if active_context.get("span_id")
            else f"agent.interrupt.{uuid4().hex[:8]}"
        )
        active_context["component"] = "agent"
        active_context["phase"] = "interrupt_requested"

        logger.info(
            "Agent interrupt received",
            extra={
                "event_type": "workflow.state_transition",
                "log_category": "tasks",
                "context": active_context,
                "task_id": active_context["task_id"],
                "data": {
                    "status": self._status.state.value,
                    "legacy_event_type": "interrupt_received",
                    "timing": {"duration_ms": 0},
                },
            },
        )
        self._interrupted = True
        if self._active_workflow_context is not None:
            self._active_workflow_context.interrupted = True

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
