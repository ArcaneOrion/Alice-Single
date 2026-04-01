"""Phase-2 runtime context builder。"""

from __future__ import annotations

from typing import Any

from ...domain.llm.models.message import ChatMessage

from .models import (
    HistoryContext,
    MemorySnapshot,
    RequestMetadata,
    RuntimeContext,
    SkillSnapshot,
    SkillSnapshotItem,
)
from .time_provider import TimeProvider


class RuntimeContextBuilder:
    """统一组装 phase-2 runtime context。"""

    def __init__(self, time_provider: TimeProvider | None = None) -> None:
        self.time_provider = time_provider or TimeProvider()

    def build(
        self,
        *,
        system_prompt: str,
        current_question: str,
        messages: list[ChatMessage] | None = None,
        request_metadata: dict[str, Any] | None = None,
        memory_manager=None,
        skill_registry=None,
        tool_registry=None,
        tool_history: list[dict[str, Any]] | None = None,
    ) -> RuntimeContext:
        metadata = dict(request_metadata or {})
        history_messages = self._history_messages(messages or [])

        return RuntimeContext(
            system_prompt=system_prompt or "",
            history_context=HistoryContext(messages=history_messages),
            current_question=current_question or "",
            local_time=self.time_provider.now(),
            memory_snapshot=self._memory_snapshot(memory_manager),
            skill_snapshot=self._skill_snapshot(skill_registry),
            tools=self._tool_snapshot(tool_registry),
            request_metadata=RequestMetadata(
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
                        "runtime_context",
                    }
                },
            ),
            tool_history=list(tool_history or []),
        )

    @staticmethod
    def _history_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            history.append(message.to_dict())
        return history

    @staticmethod
    def _memory_snapshot(memory_manager) -> MemorySnapshot:
        if memory_manager is None:
            return MemorySnapshot()
        return MemorySnapshot(
            working=str(memory_manager.get_working_content() or ""),
            short_term=str(memory_manager.get_stm_content() or ""),
            long_term=str(memory_manager.get_ltm_content() or ""),
        )

    @staticmethod
    def _skill_snapshot(skill_registry) -> SkillSnapshot:
        if skill_registry is None:
            return SkillSnapshot()
        skills = []
        for name, skill in sorted(skill_registry.get_all_skills().items()):
            skill_metadata = getattr(skill, "metadata", None)
            metadata = skill_metadata.to_dict() if skill_metadata is not None else {}
            skills.append(
                SkillSnapshotItem(
                    name=name,
                    description=getattr(skill, "description", "") or "",
                    path=str(getattr(skill, "path", "") or ""),
                    metadata=dict(metadata),
                )
            )
        return SkillSnapshot(
            skills=skills,
            summary=skill_registry.list_skills_summary(),
        )

    @staticmethod
    def _tool_snapshot(tool_registry) -> dict[str, list[dict[str, Any]]]:
        if tool_registry is None:
            return {}
        snapshot_dict = getattr(tool_registry, "snapshot_dict", None)
        if callable(snapshot_dict):
            payload = snapshot_dict()
            if isinstance(payload, dict):
                return {
                    str(category): list(items) if isinstance(items, list) else []
                    for category, items in payload.items()
                }
        return {}


__all__ = ["RuntimeContextBuilder"]
