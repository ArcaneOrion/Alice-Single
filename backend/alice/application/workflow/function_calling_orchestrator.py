"""Function calling 编排器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.alice.domain.execution.models.execution_result import ExecutionResult
from backend.alice.domain.execution.models.tool_calling import (
    ToolArgumentValidationError,
    ToolExecutionResult,
    ToolInvocation,
    ToolResultPayload,
    UnknownToolError,
)
from backend.alice.domain.execution.services.execution_service import ExecutionService
from backend.alice.domain.execution.services.tool_registry import ToolRegistry
from backend.alice.domain.llm.models.message import ChatMessage


@dataclass(frozen=True)
class FunctionCallingOrchestrationResult:
    assistant_message: ChatMessage
    tool_messages: list[ChatMessage]
    execution_results: list[ToolExecutionResult]


class FunctionCallingOrchestrator:
    """负责解析、执行并回注结构化工具调用。"""

    def __init__(
        self,
        execution_service: ExecutionService,
        tool_registry: ToolRegistry,
    ) -> None:
        self.execution_service = execution_service
        self.tool_registry = tool_registry

    def execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        assistant_content: str = "",
        log_context: dict[str, Any] | None = None,
    ) -> FunctionCallingOrchestrationResult:
        invocations = [ToolInvocation.from_tool_call(tool_call) for tool_call in tool_calls]
        assistant_message = ChatMessage.assistant(
            assistant_content,
            tool_calls=[invocation.to_assistant_tool_call() for invocation in invocations],
        )

        execution_results: list[ToolExecutionResult] = []
        tool_messages: list[ChatMessage] = []

        for tool_index, invocation in enumerate(invocations, start=1):
            tool_log_context = dict(log_context or {})
            span_root = str(tool_log_context.get("span_id") or "workflow")
            tool_log_context["component"] = "function_calling_orchestrator"
            tool_log_context["phase"] = "tool_execution"
            tool_log_context["span_id"] = f"{span_root}.tool{tool_index}"
            tool_log_context["tool_name"] = invocation.name
            tool_log_context["tool_call_id"] = invocation.id

            try:
                self.tool_registry.require_tool(invocation.name)
                execution_result = self.execution_service.execute_tool_call(
                    invocation,
                    log_context=tool_log_context,
                )
            except Exception as exc:
                error_type = "execution_error"
                if isinstance(exc, UnknownToolError):
                    error_type = exc.error_type
                elif isinstance(exc, ToolArgumentValidationError):
                    error_type = exc.error_type
                fallback = ExecutionResult.error_result(str(exc))
                execution_result = ToolExecutionResult(
                    invocation=invocation,
                    payload=ToolResultPayload(
                        tool_name=invocation.name,
                        success=False,
                        output=fallback.output,
                        error=fallback.error,
                        exit_code=fallback.exit_code,
                        status=fallback.status.value,
                        metadata={
                            **dict(fallback.metadata or {}),
                            "error_type": error_type,
                        },
                    ),
                    execution_result=ExecutionResult(
                        success=fallback.success,
                        output=fallback.output,
                        status=fallback.status,
                        error=fallback.error,
                        exit_code=fallback.exit_code,
                        execution_time=fallback.execution_time,
                        timestamp=fallback.timestamp,
                        metadata={
                            **dict(fallback.metadata or {}),
                            "error_type": error_type,
                        },
                    ),
                )

            execution_results.append(execution_result)
            tool_messages.append(
                ChatMessage.tool(
                    content=execution_result.tool_message_content(),
                    tool_call_id=invocation.id or f"tool-call-{invocation.index}",
                )
            )

        return FunctionCallingOrchestrationResult(
            assistant_message=assistant_message,
            tool_messages=tool_messages,
            execution_results=execution_results,
        )


__all__ = [
    "FunctionCallingOrchestrator",
    "FunctionCallingOrchestrationResult",
]
