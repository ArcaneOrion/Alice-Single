"""Backend-only canonical bridge model backed by application DTOs."""

from backend.alice.application.dto.responses import (
    RuntimeEventType as CanonicalEventType,
    RuntimeEventResponse as CanonicalBridgeEvent,
    StatusType as CanonicalStatus,
    StructuredRuntimeOutput as CanonicalRuntimeOutput,
    StructuredToolCall as CanonicalToolCall,
    StructuredToolResult as CanonicalToolResult,
)

__all__ = [
    "CanonicalStatus",
    "CanonicalEventType",
    "CanonicalToolCall",
    "CanonicalToolResult",
    "CanonicalRuntimeOutput",
    "CanonicalBridgeEvent",
]
