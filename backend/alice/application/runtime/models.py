"""Phase-2 runtime context 数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class RequestMetadata:
    """请求级链路与执行元数据。"""

    session_id: str = ""
    trace_id: str = ""
    request_id: str = ""
    task_id: str = ""
    span_id: str = ""
    enable_thinking: bool = True
    stream: bool = True
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RequestMetadata":
        metadata = dict(payload or {})
        return cls(
            session_id=str(metadata.get("session_id") or ""),
            trace_id=str(metadata.get("trace_id") or ""),
            request_id=str(metadata.get("request_id") or ""),
            task_id=str(metadata.get("task_id") or ""),
            span_id=str(metadata.get("span_id") or ""),
            enable_thinking=bool(metadata.get("enable_thinking", True)),
            stream=bool(metadata.get("stream", True)),
            extras={
                key: value
                for key, value in metadata.items()
                if key
                not in {
                    "session_id",
                    "trace_id",
                    "request_id",
                    "task_id",
                    "span_id",
                    "enable_thinking",
                    "stream",
                }
            },
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "span_id": self.span_id,
            "enable_thinking": self.enable_thinking,
            "stream": self.stream,
        }
        payload.update(self.extras)
        return payload


@dataclass(frozen=True)
class LocalTimeContext:
    """本地时间上下文。"""

    iso: str
    timezone: str
    source: str = "local"

    def to_dict(self) -> dict[str, str]:
        return {
            "iso": self.iso,
            "timezone": self.timezone,
            "source": self.source,
        }


@dataclass(frozen=True)
class HistoryContext:
    """与当前问题分离的历史上下文。"""

    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"messages": list(self.messages)}


@dataclass(frozen=True)
class MemorySnapshot:
    """结构化记忆快照。"""

    working: str = ""
    short_term: str = ""
    long_term: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "working": self.working,
            "short_term": self.short_term,
            "long_term": self.long_term,
        }


@dataclass(frozen=True)
class SkillSnapshotItem:
    """单个技能快照。"""

    name: str
    description: str
    path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SkillSnapshot:
    """结构化技能快照。"""

    skills: list[SkillSnapshotItem] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skills": [skill.to_dict() for skill in self.skills],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class RuntimeContext:
    """phase-2 canonical runtime context。"""

    system_prompt: str = ""
    history_context: HistoryContext = field(default_factory=HistoryContext)
    current_question: str = ""
    local_time: LocalTimeContext | None = None
    memory_snapshot: MemorySnapshot = field(default_factory=MemorySnapshot)
    skill_snapshot: SkillSnapshot = field(default_factory=SkillSnapshot)
    tools: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    request_metadata: RequestMetadata = field(default_factory=RequestMetadata)
    tool_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "system": {"prompt": self.system_prompt},
            "user": {
                "history_context": self.history_context.to_dict(),
                "current_question": self.current_question,
                "local_time": self.local_time.to_dict() if self.local_time else {},
            },
            "memory_snapshot": self.memory_snapshot.to_dict(),
            "skill_snapshot": self.skill_snapshot.to_dict(),
            "tools": {category: list(items) for category, items in self.tools.items()},
            "request_metadata": self.request_metadata.to_dict(),
            "tool_history": list(self.tool_history),
        }
        return payload


@dataclass(frozen=True)
class RequestEnvelope:
    """Phase-2 canonical request envelope。"""

    system_prompt: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    model_context: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    request_metadata: RequestMetadata = field(default_factory=RequestMetadata)
    tool_history: list[dict[str, Any]] = field(default_factory=list)

    def with_messages(self, messages: list[dict[str, Any]]) -> "RequestEnvelope":
        return replace(self, messages=list(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": {"prompt": self.system_prompt},
            "messages": list(self.messages),
            "model_context": dict(self.model_context),
            "tools": {category: list(items) for category, items in self.tools.items()},
            "request_metadata": self.request_metadata.to_dict(),
            "tool_history": list(self.tool_history),
        }


__all__ = [
    "RequestMetadata",
    "LocalTimeContext",
    "HistoryContext",
    "MemorySnapshot",
    "SkillSnapshotItem",
    "SkillSnapshot",
    "RuntimeContext",
    "RequestEnvelope",
]
