"""聊天工作流。"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Iterator, Optional
from uuid import uuid4

from .base_workflow import Workflow, WorkflowContext
from .function_calling_orchestrator import FunctionCallingOrchestrator
from ..runtime import RequestEnvelope
from ..dto import (
    ApplicationResponse,
    RequestContext,
    RuntimeEventResponse,
    RuntimeEventType,
    StatusType,
    StructuredRuntimeOutput,
    StructuredToolCall,
    StructuredToolResult,
)
from backend.alice.domain.execution.services.tool_registry import ToolRegistry
from backend.alice.domain.llm.services.stream_service import (
    StreamService,
    build_tool_kwargs,
)

logger = logging.getLogger(__name__)


def _extract_workflow_logging_context(context: WorkflowContext) -> dict:
    request_context = context.request_context
    metadata = request_context.metadata if isinstance(request_context.metadata, dict) else {}
    session_id = str(metadata.get("session_id") or "")
    trace_id = str(metadata.get("trace_id") or metadata.get("request_id") or "")
    request_id = str(metadata.get("request_id") or trace_id)
    task_id = str(metadata.get("task_id") or request_id or session_id)
    span_id = str(metadata.get("span_id") or f"workflow.{uuid4().hex[:12]}")

    return {
        "trace_id": trace_id,
        "task_id": task_id,
        "request_id": request_id,
        "session_id": session_id,
        "span_id": span_id,
        "component": "chat_workflow",
        "phase": "idle",
        "request_type": request_context.request_type.value,
        "workflow": "chat_workflow",
    }


class ChatWorkflow(Workflow):
    """聊天工作流。"""

    def __init__(
        self,
        chat_service=None,
        execution_service=None,
        stream_service: StreamService | None = None,
        tool_registry: Optional[ToolRegistry] = None,
        function_calling_orchestrator: FunctionCallingOrchestrator | None = None,
        max_iterations: int = 10,
    ):
        self.chat_service = chat_service
        self.execution_service = execution_service
        self.stream_service = stream_service or (
            StreamService(provider=chat_service.provider) if chat_service is not None else None
        )
        self.tool_registry = tool_registry or ToolRegistry()
        self.function_calling_orchestrator = function_calling_orchestrator or (
            FunctionCallingOrchestrator(execution_service, self.tool_registry)
            if execution_service is not None
            else None
        )
        self.max_iterations = max_iterations

    @property
    def name(self) -> str:
        return "ChatWorkflow"

    def can_handle(self, context: RequestContext) -> bool:
        return context.request_type.value == "chat"

    def execute(self, context: WorkflowContext) -> Iterator[ApplicationResponse]:
        base_log_context = _extract_workflow_logging_context(context)
        message_id_root = str(base_log_context.get("request_id") or uuid4().hex)

        def log_transition(
            phase: str,
            message: str,
            *,
            iteration_no: int | None = None,
            level: str = "info",
            legacy_event_type: str = "",
            data: Optional[dict] = None,
            error: Optional[dict] = None,
            with_exc_info: bool = False,
        ) -> None:
            log_context = dict(base_log_context)
            log_context["phase"] = phase
            span_parts = [str(base_log_context.get("span_id") or "workflow")]
            if iteration_no is not None:
                span_parts.append(f"iter{iteration_no}")
            span_parts.append(phase)
            log_context["span_id"] = ".".join(span_parts)

            payload_data = dict(data or {})
            if iteration_no is not None and "iteration" not in payload_data:
                payload_data["iteration"] = iteration_no
            if legacy_event_type:
                payload_data["legacy_event_type"] = legacy_event_type
            payload_data.setdefault("timing", {"duration_ms": 0})

            extra = {
                "event_type": "workflow.state_transition",
                "log_category": "tasks",
                "task_id": log_context["task_id"],
                "context": log_context,
                "data": payload_data,
            }
            if error is not None:
                extra["error"] = error

            if level == "warning":
                logger.warning(message, extra=extra)
            elif level == "error":
                logger.error(message, exc_info=with_exc_info, extra=extra)
            else:
                logger.info(message, extra=extra)

        def normalize_tool_call_payload(payload: dict[str, Any]) -> StructuredToolCall:
            return StructuredToolCall.from_dict(payload)

        def structured_tool_calls(tool_call_state: dict[int, StructuredToolCall]) -> list[StructuredToolCall]:
            return [tool_call_state[index] for index in sorted(tool_call_state)]

        def build_runtime_output(
            *,
            iteration_no: int,
            status: str,
            content: str,
            reasoning: str,
            usage_payload: dict[str, Any],
            tool_call_state: dict[int, StructuredToolCall],
            tool_results: list[StructuredToolResult],
        ) -> StructuredRuntimeOutput:
            metadata = {
                "iteration": iteration_no,
                "trace_id": base_log_context.get("trace_id") or "",
                "request_id": base_log_context.get("request_id") or "",
                "task_id": base_log_context.get("task_id") or "",
                "session_id": base_log_context.get("session_id") or "",
                "span_id": base_log_context.get("span_id") or "",
            }
            return StructuredRuntimeOutput(
                message_id=f"{message_id_root}.iter{iteration_no}",
                status=status,
                reasoning=reasoning,
                content=content,
                tool_calls=structured_tool_calls(tool_call_state),
                tool_results=list(tool_results),
                usage=dict(usage_payload),
                metadata=metadata,
            )

        def emit_runtime_event(
            *,
            iteration_no: int,
            event_type: RuntimeEventType,
            payload: dict[str, Any],
            status: str,
            content: str,
            reasoning: str,
            usage_payload: dict[str, Any],
            tool_call_state: dict[int, StructuredToolCall],
            tool_results: list[StructuredToolResult],
        ) -> RuntimeEventResponse:
            return RuntimeEventResponse(
                event_type=event_type,
                payload=dict(payload),
                runtime_output=build_runtime_output(
                    iteration_no=iteration_no,
                    status=status,
                    content=content,
                    reasoning=reasoning,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=tool_results,
                ),
            )

        if not self.chat_service:
            yield emit_runtime_event(
                iteration_no=0,
                event_type=RuntimeEventType.ERROR_RAISED,
                payload={"content": "Chat service not available", "code": "NO_SERVICE"},
                status=StatusType.ERROR.value,
                content="",
                reasoning="",
                usage_payload={},
                tool_call_state={},
                tool_results=[],
            )
            return

        if not self.stream_service:
            yield emit_runtime_event(
                iteration_no=0,
                event_type=RuntimeEventType.ERROR_RAISED,
                payload={"content": "Stream service not available", "code": "NO_STREAM_SERVICE"},
                status=StatusType.ERROR.value,
                content="",
                reasoning="",
                usage_payload={},
                tool_call_state={},
                tool_results=[],
            )
            return

        self.chat_service.add_user_message(context.user_input)
        tools = self.tool_registry.list_openai_tools()

        request_metadata = context.request_context.metadata if isinstance(context.request_context.metadata, dict) else {}
        active_runtime_context = getattr(context, "runtime_context", None)
        active_request_envelope = getattr(context, "request_envelope", None)
        chat_service = self.chat_service
        runtime_context_payload = (
            active_runtime_context.to_dict()
            if active_runtime_context is not None
            else dict(request_metadata.get("runtime_context") or {})
        )

        request_context_provider_metadata = {
            "trace_id": str(request_metadata.get("trace_id") or request_metadata.get("request_id") or ""),
            "request_id": str(request_metadata.get("request_id") or request_metadata.get("trace_id") or ""),
            "task_id": str(
                request_metadata.get("task_id")
                or request_metadata.get("request_id")
                or request_metadata.get("session_id")
                or ""
            ),
            "session_id": str(request_metadata.get("session_id") or ""),
            "span_id": str(request_metadata.get("span_id") or ""),
        }

        def build_provider_metadata(iteration_request_envelope: RequestEnvelope | None) -> dict[str, Any]:
            if iteration_request_envelope is None:
                return request_context_provider_metadata
            envelope_metadata = iteration_request_envelope.request_metadata.to_dict()
            return {
                "trace_id": str(envelope_metadata.get("trace_id") or request_context_provider_metadata["trace_id"]),
                "request_id": str(envelope_metadata.get("request_id") or request_context_provider_metadata["request_id"]),
                "task_id": str(envelope_metadata.get("task_id") or request_context_provider_metadata["task_id"]),
                "session_id": str(
                    envelope_metadata.get("session_id") or request_context_provider_metadata["session_id"]
                ),
                "span_id": str(envelope_metadata.get("span_id") or request_context_provider_metadata["span_id"]),
            }

        def build_iteration_request_envelope() -> RequestEnvelope | None:
            iteration_messages = [message.to_dict() for message in chat_service.messages if message.role != "system"]
            if active_request_envelope is not None:
                return active_request_envelope.with_messages(iteration_messages)
            if active_runtime_context is None:
                return None
            return RequestEnvelope(
                system_prompt=active_runtime_context.system_prompt,
                messages=iteration_messages,
                model_context={
                    "local_time": active_runtime_context.local_time.to_dict() if active_runtime_context.local_time else {},
                    "memory_snapshot": active_runtime_context.memory_snapshot.to_dict(),
                    "skill_snapshot": active_runtime_context.skill_snapshot.to_dict(),
                },
                tools={category: list(items) for category, items in active_runtime_context.tools.items()},
                request_metadata=active_runtime_context.request_metadata,
                tool_history=list(active_runtime_context.tool_history),
            )


        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            iteration_started_at = time.monotonic()
            full_content = ""
            full_thinking = ""
            usage_payload: dict[str, Any] = {}
            tool_call_state: dict[int, StructuredToolCall] = {}
            runtime_tool_results: list[StructuredToolResult] = []
            runtime_event_count = 0

            log_transition(
                phase="iteration_start",
                message="Chat workflow iteration started",
                iteration_no=iteration,
                legacy_event_type="iteration_start",
                data={"max_iterations": self.max_iterations},
            )
            if context.interrupted:
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow interrupted",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "interrupted",
                        "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                    },
                )
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.INTERRUPT_ACK,
                    payload={},
                    status=StatusType.INTERRUPTED.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )
                return

            yield emit_runtime_event(
                iteration_no=iteration,
                event_type=RuntimeEventType.STATUS_CHANGED,
                payload={"status": StatusType.THINKING.value},
                status=StatusType.THINKING.value,
                content=full_content,
                reasoning=full_thinking,
                usage_payload=usage_payload,
                tool_call_state=tool_call_state,
                tool_results=runtime_tool_results,
            )

            try:
                iteration_request_envelope = build_iteration_request_envelope()
                request_envelope_payload = (
                    iteration_request_envelope.to_dict()
                    if iteration_request_envelope is not None
                    else None
                )
                request_messages = self.chat_service.build_request_messages(
                    runtime_context_payload,
                    request_envelope=iteration_request_envelope,
                )
                provider_request_metadata = build_provider_metadata(iteration_request_envelope)
                request_kwargs = build_tool_kwargs(
                    self.chat_service.provider,
                    tools,
                    metadata=provider_request_metadata,
                    request_envelope=request_envelope_payload,
                )
                log_transition(
                    phase="waiting_for_model",
                    message="Chat workflow waiting for model stream",
                    iteration_no=iteration,
                    data={"message_count": len(request_messages)},
                )
            except Exception as e:
                log_transition(
                    phase="iteration_end",
                    message="Chat request failed",
                    iteration_no=iteration,
                    level="error",
                    with_exc_info=True,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "chat_error",
                        "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.ERROR_RAISED,
                    payload={"content": f"Chat request failed: {e}", "code": "CHAT_ERROR"},
                    status=StatusType.ERROR.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )
                return

            log_transition(
                phase="parsing_stream",
                message="Chat workflow started parsing model stream",
                iteration_no=iteration,
            )

            try:
                runtime_events = self.stream_service.stream_runtime(
                    request_messages,
                    should_stop=lambda: context.interrupted,
                    **request_kwargs,
                )
                for runtime_event in runtime_events:
                    runtime_event_count += 1
                    event_name = str(runtime_event.get("event_type") or "")
                    payload = dict(runtime_event.get("payload") or {})

                    if event_name == RuntimeEventType.USAGE_UPDATED.value:
                        usage_payload = dict(payload.get("usage") or {})
                        yield emit_runtime_event(
                            iteration_no=iteration,
                            event_type=RuntimeEventType.USAGE_UPDATED,
                            payload=payload,
                            status=StatusType.STREAMING.value,
                            content=full_content,
                            reasoning=full_thinking,
                            usage_payload=usage_payload,
                            tool_call_state=tool_call_state,
                            tool_results=runtime_tool_results,
                        )
                        continue

                    if event_name == RuntimeEventType.REASONING_DELTA.value:
                        full_thinking += str(payload.get("content") or "")
                        yield emit_runtime_event(
                            iteration_no=iteration,
                            event_type=RuntimeEventType.REASONING_DELTA,
                            payload=payload,
                            status=StatusType.STREAMING.value,
                            content=full_content,
                            reasoning=full_thinking,
                            usage_payload=usage_payload,
                            tool_call_state=tool_call_state,
                            tool_results=runtime_tool_results,
                        )
                        continue

                    if event_name == RuntimeEventType.CONTENT_DELTA.value:
                        full_content += str(payload.get("content") or "")
                        yield emit_runtime_event(
                            iteration_no=iteration,
                            event_type=RuntimeEventType.CONTENT_DELTA,
                            payload=payload,
                            status=StatusType.STREAMING.value,
                            content=full_content,
                            reasoning=full_thinking,
                            usage_payload=usage_payload,
                            tool_call_state=tool_call_state,
                            tool_results=runtime_tool_results,
                        )
                        continue

                    if event_name in {
                        RuntimeEventType.TOOL_CALL_STARTED.value,
                        RuntimeEventType.TOOL_CALL_ARGUMENT_DELTA.value,
                        RuntimeEventType.TOOL_CALL_COMPLETED.value,
                    }:
                        normalized_tool_call = normalize_tool_call_payload(payload)
                        tool_call_state[normalized_tool_call.index] = normalized_tool_call
                        yield emit_runtime_event(
                            iteration_no=iteration,
                            event_type=RuntimeEventType(event_name),
                            payload=payload,
                            status=StatusType.EXECUTING_TOOL.value,
                            content=full_content,
                            reasoning=full_thinking,
                            usage_payload=usage_payload,
                            tool_call_state=tool_call_state,
                            tool_results=runtime_tool_results,
                        )
                        continue

                    if event_name == RuntimeEventType.INTERRUPT_ACK.value:
                        log_transition(
                            phase="iteration_end",
                            message="Chat workflow interrupted during stream",
                            iteration_no=iteration,
                            legacy_event_type="iteration_end",
                            data={
                                "end_reason": "interrupted_during_stream",
                                "runtime_event_count": runtime_event_count,
                                "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                            },
                        )
                        yield emit_runtime_event(
                            iteration_no=iteration,
                            event_type=RuntimeEventType.INTERRUPT_ACK,
                            payload={},
                            status=StatusType.INTERRUPTED.value,
                            content=full_content,
                            reasoning=full_thinking,
                            usage_payload=usage_payload,
                            tool_call_state=tool_call_state,
                            tool_results=runtime_tool_results,
                        )
                        return

                    if event_name == RuntimeEventType.MESSAGE_COMPLETED.value:
                        full_content = str(payload.get("content") or full_content)
                        full_thinking = str(payload.get("reasoning") or full_thinking)
                        usage_payload = dict(payload.get("usage") or usage_payload)
                        for tool_call in payload.get("tool_calls") or []:
                            normalized_tool_call = normalize_tool_call_payload(dict(tool_call))
                            tool_call_state[normalized_tool_call.index] = normalized_tool_call
                        yield emit_runtime_event(
                            iteration_no=iteration,
                            event_type=RuntimeEventType.MESSAGE_COMPLETED,
                            payload={
                                "content": full_content,
                                "reasoning": full_thinking,
                                "usage": dict(usage_payload),
                                "tool_calls": [
                                    tool_call.to_dict()
                                    for tool_call in structured_tool_calls(tool_call_state)
                                ],
                            },
                            status=(
                                StatusType.EXECUTING_TOOL.value
                                if tool_call_state
                                else StatusType.DONE.value
                            ),
                            content=full_content,
                            reasoning=full_thinking,
                            usage_payload=usage_payload,
                            tool_call_state=tool_call_state,
                            tool_results=runtime_tool_results,
                        )
                        continue
            except Exception as e:
                log_transition(
                    phase="iteration_end",
                    message="Chat request failed",
                    iteration_no=iteration,
                    level="error",
                    with_exc_info=True,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "chat_error",
                        "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.ERROR_RAISED,
                    payload={"content": f"Chat request failed: {e}", "code": "CHAT_ERROR"},
                    status=StatusType.ERROR.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )
                return

            tool_calls = [tool_call.to_dict() for tool_call in structured_tool_calls(tool_call_state)]
            tool_names = sorted(
                {
                    str((tool_call.get("function") or {}).get("name") or "")
                    for tool_call in tool_calls
                    if (tool_call.get("function") or {}).get("name")
                }
            )

            log_transition(
                phase="tool_detection",
                message="Tool detection completed",
                iteration_no=iteration,
                legacy_event_type="tool_detection",
                data={
                    "runtime_event_count": runtime_event_count,
                    "content_length": len(full_content),
                    "thinking_length": len(full_thinking),
                    "tool_call_count": len(tool_calls),
                    "tool_names": tool_names,
                    "usage": dict(usage_payload),
                },
            )

            if not tool_calls:
                self.chat_service.add_assistant_message(full_content)
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow iteration completed",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "completed_without_tool",
                        "tool_call_count": 0,
                        "content_length": len(full_content),
                        "thinking_length": len(full_thinking),
                        "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                    },
                )
                return

            if self.function_calling_orchestrator is None:
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.ERROR_RAISED,
                    payload={
                        "content": "Function calling orchestrator not available",
                        "code": "NO_ORCHESTRATOR",
                    },
                    status=StatusType.ERROR.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )
                return

            log_transition(
                phase="executing_tools",
                message="Chat workflow executing detected tools",
                iteration_no=iteration,
                data={
                    "tool_call_count": len(tool_calls),
                    "tool_names": tool_names,
                },
            )

            try:
                orchestration_result = self.function_calling_orchestrator.execute_tool_calls(
                    tool_calls,
                    assistant_content=full_content,
                    log_context={
                        **base_log_context,
                        "span_id": f"{base_log_context['span_id']}.iter{iteration}",
                    },
                )
            except Exception as e:
                log_transition(
                    phase="iteration_end",
                    message="Tool orchestration failed",
                    iteration_no=iteration,
                    level="error",
                    with_exc_info=True,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "tool_orchestration_error",
                        "tool_call_count": len(tool_calls),
                        "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                    },
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.ERROR_RAISED,
                    payload={"content": f"Tool orchestration failed: {e}", "code": "TOOL_ERROR"},
                    status=StatusType.ERROR.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )
                return

            self.chat_service.add_message(orchestration_result.assistant_message)
            for tool_message in orchestration_result.tool_messages:
                self.chat_service.add_message(tool_message)

            for execution_result in orchestration_result.execution_results:
                tool_result_payload = {
                    "tool_call_id": execution_result.invocation.id or f"tool-call-{execution_result.invocation.index}",
                    "type": execution_result.invocation.type,
                    "content": execution_result.tool_message_content(),
                    "status": execution_result.payload.status,
                    "metadata": dict(execution_result.payload.metadata or {}),
                }
                runtime_tool_results.append(
                    StructuredToolResult(
                        tool_call_id=str(tool_result_payload["tool_call_id"]),
                        tool_type=str(tool_result_payload["type"]),
                        content=str(tool_result_payload["content"]),
                        status=str(tool_result_payload["status"]),
                        metadata=dict(tool_result_payload["metadata"]),
                    )
                )
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.TOOL_RESULT,
                    payload=tool_result_payload,
                    status=StatusType.EXECUTING_TOOL.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )

            if context.interrupted:
                log_transition(
                    phase="iteration_end",
                    message="Chat workflow interrupted during tool execution",
                    iteration_no=iteration,
                    legacy_event_type="iteration_end",
                    data={
                        "end_reason": "interrupted_during_tool_execution",
                        "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                    },
                )
                yield emit_runtime_event(
                    iteration_no=iteration,
                    event_type=RuntimeEventType.INTERRUPT_ACK,
                    payload={},
                    status=StatusType.INTERRUPTED.value,
                    content=full_content,
                    reasoning=full_thinking,
                    usage_payload=usage_payload,
                    tool_call_state=tool_call_state,
                    tool_results=runtime_tool_results,
                )
                return

            log_transition(
                phase="iteration_end",
                message="Chat workflow iteration completed",
                iteration_no=iteration,
                legacy_event_type="iteration_end",
                data={
                    "end_reason": "tools_executed",
                    "tool_call_count": len(tool_calls),
                    "tool_result_count": len(orchestration_result.execution_results),
                    "tool_names": tool_names,
                    "timing": {"duration_ms": int((time.monotonic() - iteration_started_at) * 1000)},
                },
            )

        log_transition(
            phase="max_iterations",
            message="Reached max chat workflow iterations",
            level="warning",
            legacy_event_type="max_iterations_warning",
            data={
                "iteration": iteration,
                "max_iterations": self.max_iterations,
            },
        )
        yield emit_runtime_event(
            iteration_no=iteration,
            event_type=RuntimeEventType.ERROR_RAISED,
            payload={"content": "达到最大迭代次数，可能存在无限循环", "code": "MAX_ITERATIONS"},
            status=StatusType.ERROR.value,
            content="",
            reasoning="",
            usage_payload={},
            tool_call_state={},
            tool_results=[],
        )


__all__ = ["ChatWorkflow"]
