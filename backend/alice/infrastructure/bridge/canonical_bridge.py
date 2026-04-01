"""Backend-only canonical bridge model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CanonicalStatus(str, Enum):
    """后端内部统一状态枚举。"""

    READY = "ready"
    THINKING = "thinking"
    STREAMING = "streaming"
    EXECUTING_TOOL = "executing_tool"
    DONE = "done"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class CanonicalEventType(str, Enum):
    """后端内部统一 runtime 事件类型。"""

    STATUS_CHANGED = "status_changed"
    REASONING_DELTA = "reasoning_delta"
    CONTENT_DELTA = "content_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_ARGUMENT_DELTA = "tool_call_argument_delta"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_RESULT = "tool_result"
    USAGE_UPDATED = "usage_updated"
    MESSAGE_COMPLETED = "message_completed"
    ERROR_RAISED = "error_raised"
    INTERRUPT_ACK = "interrupt_ack"


@dataclass(frozen=True)
class CanonicalToolCall:
    """结构化工具调用。"""

    index: int = 0
    id: str = ""
    type: str = "function"
    function_name: str = ""
    function_arguments: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "id": self.id,
            "type": self.type,
            "function_name": self.function_name,
            "function_arguments": self.function_arguments,
        }


@dataclass(frozen=True)
class CanonicalToolResult:
    """结构化工具执行结果。"""

    tool_call_id: str = ""
    tool_type: str = ""
    content: str = ""
    status: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "tool_type": self.tool_type,
            "content": self.content,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CanonicalRuntimeOutput:
    """后端内部 canonical structured runtime 输出。"""

    message_id: str = ""
    status: str = ""
    reasoning: str = ""
    content: str = ""
    tool_calls: list[CanonicalToolCall] = field(default_factory=list)
    tool_results: list[CanonicalToolResult] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "status": self.status,
            "reasoning": self.reasoning,
            "content": self.content,
            "tool_calls": [tool_call.to_dict() for tool_call in self.tool_calls],
            "tool_results": [tool_result.to_dict() for tool_result in self.tool_results],
            "usage": dict(self.usage),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CanonicalBridgeEvent:
    """后端内部 canonical bridge 事件。"""

    event_type: CanonicalEventType = CanonicalEventType.STATUS_CHANGED
    payload: dict[str, Any] = field(default_factory=dict)
    runtime_output: CanonicalRuntimeOutput | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "event_type": self.event_type.value,
            "payload": dict(self.payload),
        }
        if self.runtime_output is not None:
            result["runtime_output"] = self.runtime_output.to_dict()
        return result


__all__ = [
    "CanonicalStatus",
    "CanonicalEventType",
    "CanonicalToolCall",
    "CanonicalToolResult",
    "CanonicalRuntimeOutput",
    "CanonicalBridgeEvent",
]
