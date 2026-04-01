from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.alice.application.runtime import RuntimeContextBuilder, TimeProvider
from backend.alice.application.workflow.function_calling_orchestrator import FunctionCallingOrchestrator
from backend.alice.domain.execution.models.execution_result import ExecutionResult
from backend.alice.domain.execution.models.tool_calling import (
    ToolArgumentValidationError,
    ToolExecutionResult,
    ToolInvocation,
    ToolResultPayload,
)
from backend.alice.domain.execution.services.execution_service import ExecutionService, SkillSnapshotManager
from backend.alice.domain.execution.services.tool_registry import ToolRegistry
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.skills.models import Skill, SkillMetadata


class _FixedTimeProvider(TimeProvider):
    def now(self):
        from backend.alice.application.runtime import LocalTimeContext

        return LocalTimeContext(
            iso="2026-04-01T12:00:00+08:00",
            timezone="CST",
            source="local",
        )


@pytest.mark.unit
def test_runtime_context_builder_splits_history_and_current_question() -> None:
    memory_manager = MagicMock()
    memory_manager.get_working_content.return_value = "working"
    memory_manager.get_stm_content.return_value = "short"
    memory_manager.get_ltm_content.return_value = "long"

    skill = Skill(
        metadata=SkillMetadata(name="demo", description="demo skill"),
        path=Path("skills/demo/SKILL.md"),
        content="body",
        yaml_content="name: demo",
    )
    skill_registry = MagicMock()
    skill_registry.get_all_skills.return_value = {"demo": skill}
    skill_registry.list_skills_summary.return_value = "### 可用技能列表\n- **demo**: demo skill"

    tool_registry = ToolRegistry(skill_registry=skill_registry)
    builder = RuntimeContextBuilder(time_provider=_FixedTimeProvider())

    runtime_context = builder.build(
        system_prompt="You are Alice",
        current_question="current question",
        messages=[
            ChatMessage.system("system"),
            ChatMessage.user("old question"),
            ChatMessage.assistant("old answer"),
        ],
        request_metadata={
            "session_id": "s1",
            "trace_id": "t1",
            "request_id": "r1",
            "task_id": "task1",
            "span_id": "span1",
            "enable_thinking": True,
            "stream": True,
        },
        memory_manager=memory_manager,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )

    payload = runtime_context.to_dict()
    assert payload["user"]["current_question"] == "current question"
    assert payload["user"]["history_context"]["messages"][0]["content"] == "old question"
    assert payload["user"]["local_time"]["source"] == "local"
    assert payload["memory_snapshot"]["working"] == "working"
    assert payload["skill_snapshot"]["skills"][0]["name"] == "demo"
    assert "builtin_system_tools" in payload["tools"]
    assert payload["request_metadata"]["trace_id"] == "t1"

    request_envelope = builder.build_request_envelope(
        runtime_context=runtime_context,
        messages=[
            ChatMessage.system("system"),
            ChatMessage.user("old question"),
            ChatMessage.assistant("old answer"),
        ],
    )
    envelope_payload = request_envelope.to_dict()
    assert envelope_payload["system"]["prompt"] == "You are Alice"
    assert envelope_payload["messages"][0]["content"] == "old question"
    assert envelope_payload["messages"][-1]["content"] == "current question"
    assert envelope_payload["model_context"]["memory_snapshot"]["working"] == "working"
    assert envelope_payload["request_metadata"]["span_id"] == "span1"


@pytest.mark.unit
def test_skill_snapshot_manager_reads_registry_and_cache() -> None:
    skill_registry = MagicMock()
    skill = MagicMock()
    skill.to_dict.return_value = {"name": "demo", "description": "demo skill"}
    skill_registry.get_all_skills.return_value = {"demo": skill}
    skill_registry.refresh.return_value = 1
    skill_registry.get_skill.return_value = None

    skill_cache = MagicMock()
    skill_cache.read_skill_file.return_value = "cached content"

    manager = SkillSnapshotManager(skill_registry, skill_cache)

    assert manager.skills["demo"]["name"] == "demo"
    assert manager.read_skill_file("demo/SKILL.md") == "cached content"
    assert manager.refresh() == 1
    skill_cache.clear_cache.assert_called_once()


@pytest.mark.unit
def test_execution_service_set_snapshot_manager_updates_toolkit_handler() -> None:
    executor = MagicMock()
    service = ExecutionService(executor=executor)
    snapshot_manager = MagicMock()

    service.set_snapshot_manager(snapshot_manager)

    assert service.snapshot_manager is snapshot_manager
    assert service._toolkit_handler.snapshot_manager is snapshot_manager


@pytest.mark.unit
def test_tool_registry_snapshot_exposes_four_categories_and_openai_tools() -> None:
    skill = Skill(
        metadata=SkillMetadata(name="demo", description="demo skill"),
        path=Path("skills/demo/SKILL.md"),
        content="body",
        yaml_content="name: demo",
    )
    skill_registry = MagicMock()
    skill_registry.get_all_skills.return_value = {"demo": skill}

    registry = ToolRegistry(skill_registry=skill_registry)

    snapshot = registry.snapshot_dict()
    assert set(snapshot) == {
        "builtin_system_tools",
        "skills",
        "terminal_commands",
        "code_execution",
    }
    assert len(snapshot["builtin_system_tools"]) == 4
    assert any(tool["tool_id"] == "skill:demo" for tool in snapshot["skills"])
    assert snapshot["terminal_commands"][0]["tool_id"] == "run_bash"
    assert snapshot["code_execution"][0]["tool_id"] == "run_python"

    openai_tools = registry.list_openai_tools()
    assert [tool["function"]["name"] for tool in openai_tools] == ["run_bash", "run_python"]


@pytest.mark.unit
def test_tool_registry_validates_arguments_from_schema_single_source() -> None:
    registry = ToolRegistry()

    assert registry.validate_tool_arguments("run_bash", '{"command": "echo hi"}') == {"command": "echo hi"}

    with pytest.raises(ToolArgumentValidationError, match="run_bash 包含未定义参数: extra"):
        registry.validate_tool_arguments("run_bash", '{"command": "echo hi", "extra": true}')

    with pytest.raises(ToolArgumentValidationError, match="run_python.code 必须是 string"):
        registry.validate_tool_arguments("run_python", '{"code": 1}')


@pytest.mark.unit
def test_execution_service_uses_tool_registry_schema_validation() -> None:
    executor = MagicMock()
    service = ExecutionService(executor=executor, tool_registry=ToolRegistry())

    invocation = ToolInvocation(
        id="call_schema",
        name="run_bash",
        arguments='{"command": "echo hi", "extra": true}',
    )

    with pytest.raises(ToolArgumentValidationError, match="run_bash 包含未定义参数: extra"):
        service.execute_tool_call(invocation)

    executor.execute.assert_not_called()


@pytest.mark.unit
def test_function_calling_orchestrator_executes_registered_tool_call() -> None:
    registry = ToolRegistry()
    execution_service = MagicMock()
    invocation = ToolInvocation(id="call_1", name="run_bash", arguments='{"command": "echo hi"}')
    tool_result = ToolExecutionResult(
        invocation=invocation,
        payload=ToolResultPayload(
            tool_name="run_bash",
            success=True,
            output="hi",
            status="success",
        ),
        execution_result=ExecutionResult.success_result("hi"),
    )
    execution_service.execute_tool_call.return_value = tool_result

    orchestrator = FunctionCallingOrchestrator(execution_service=execution_service, tool_registry=registry)

    result = orchestrator.execute_tool_calls(
        [
            {
                "id": "call_1",
                "type": "function",
                "index": 0,
                "function": {
                    "name": "run_bash",
                    "arguments": '{"command": "echo hi"}',
                },
            }
        ],
        assistant_content="running tool",
        log_context={"span_id": "workflow.span", "trace_id": "trace-1"},
    )

    assert result.assistant_message.role == "assistant"
    assert result.assistant_message.content == "running tool"
    assert result.assistant_message.tool_calls == [invocation.to_assistant_tool_call()]
    assert len(result.execution_results) == 1
    assert result.execution_results[0].payload.success is True
    assert result.tool_messages[0].role == "tool"
    assert result.tool_messages[0].tool_call_id == "call_1"
    assert '"tool_name": "run_bash"' in result.tool_messages[0].content
    execution_service.execute_tool_call.assert_called_once()
    called_invocation = execution_service.execute_tool_call.call_args.args[0]
    called_log_context = execution_service.execute_tool_call.call_args.kwargs["log_context"]
    assert called_invocation == invocation
    assert called_log_context["component"] == "function_calling_orchestrator"
    assert called_log_context["phase"] == "tool_execution"
    assert called_log_context["span_id"] == "workflow.span.tool1"
    assert called_log_context["tool_name"] == "run_bash"
    assert called_log_context["tool_call_id"] == "call_1"


@pytest.mark.unit
def test_function_calling_orchestrator_returns_fallback_for_unregistered_tool() -> None:
    execution_service = MagicMock()
    orchestrator = FunctionCallingOrchestrator(execution_service=execution_service, tool_registry=ToolRegistry())

    result = orchestrator.execute_tool_calls(
        [
            {
                "id": "call_2",
                "type": "function",
                "index": 0,
                "function": {
                    "name": "missing_tool",
                    "arguments": "{}",
                },
            }
        ]
    )

    assert len(result.execution_results) == 1
    assert result.execution_results[0].payload.success is False
    assert result.execution_results[0].payload.error == "未注册的工具: missing_tool"
    assert result.execution_results[0].payload.status == "failure"
    assert result.execution_results[0].payload.metadata["error_type"] == "unknown_tool"
    assert result.execution_results[0].execution_result.metadata["error_type"] == "unknown_tool"
    assert result.tool_messages[0].tool_call_id == "call_2"
    assert '"success": false' in result.tool_messages[0].content
    execution_service.execute_tool_call.assert_not_called()


@pytest.mark.unit
def test_function_calling_orchestrator_returns_fallback_for_invalid_arguments() -> None:
    execution_service = MagicMock()
    execution_service.execute_tool_call.side_effect = ToolArgumentValidationError("run_bash 包含未定义参数: extra")
    orchestrator = FunctionCallingOrchestrator(execution_service=execution_service, tool_registry=ToolRegistry())

    result = orchestrator.execute_tool_calls(
        [
            {
                "id": "call_invalid",
                "type": "function",
                "index": 0,
                "function": {
                    "name": "run_bash",
                    "arguments": '{"command": "echo hi", "extra": true}',
                },
            }
        ]
    )

    assert len(result.execution_results) == 1
    assert result.execution_results[0].payload.success is False
    assert result.execution_results[0].payload.error == "run_bash 包含未定义参数: extra"
    assert result.execution_results[0].payload.metadata["error_type"] == "invalid_arguments"
    assert result.execution_results[0].execution_result.metadata["error_type"] == "invalid_arguments"
    execution_service.execute_tool_call.assert_called_once()


@pytest.mark.unit
def test_function_calling_orchestrator_returns_fallback_when_execution_raises() -> None:
    execution_service = MagicMock()
    execution_service.execute_tool_call.side_effect = RuntimeError("boom")
    orchestrator = FunctionCallingOrchestrator(execution_service=execution_service, tool_registry=ToolRegistry())

    result = orchestrator.execute_tool_calls(
        [
            {
                "id": "call_3",
                "type": "function",
                "index": 0,
                "function": {
                    "name": "run_python",
                    "arguments": '{"code": "print(1)"}',
                },
            }
        ],
        log_context={"span_id": "workflow"},
    )

    assert len(result.execution_results) == 1
    assert result.execution_results[0].payload.success is False
    assert result.execution_results[0].payload.error == "boom"
    assert result.execution_results[0].payload.status == "failure"
    assert result.execution_results[0].payload.metadata["error_type"] == "execution_error"
    assert result.execution_results[0].execution_result.metadata["error_type"] == "execution_error"
    assert result.tool_messages[0].tool_call_id == "call_3"
    execution_service.execute_tool_call.assert_called_once()
