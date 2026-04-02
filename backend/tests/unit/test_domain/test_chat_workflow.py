from unittest.mock import MagicMock
from typing import cast

import pytest

from backend.alice.application.dto.requests import RequestContext, RequestType
from backend.alice.application.dto.responses import RuntimeEventResponse, RuntimeEventType, ResponseType, StatusType
from backend.alice.application.runtime.models import RequestEnvelope, RequestMetadata
from backend.alice.application.workflow.base_workflow import WorkflowContext
from backend.alice.application.workflow.chat_workflow import ChatWorkflow
from backend.alice.domain.execution.models.execution_result import ExecutionResult
from backend.alice.domain.execution.models.tool_calling import ToolExecutionResult, ToolInvocation, ToolResultPayload
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.models.stream_chunk import StreamChunk, TokenUsageUpdate, ToolCallDelta
from backend.alice.domain.llm.providers.base import BaseLLMProvider
from backend.alice.domain.llm.services.chat_service import ChatService


class _ToolCallStreamProvider(BaseLLMProvider):
    def __init__(self) -> None:
        super().__init__("gpt-4o-mini")
        self.captured_messages = None
        self.captured_kwargs = None
        self._stream_calls = 0
        self._first_chunks = [
            StreamChunk(content="Hello "),
            StreamChunk(
                content="world",
                tool_calls=[
                    ToolCallDelta(index=0, id="call_1", type="function", function_name="run_bash"),
                ],
            ),
            StreamChunk(
                tool_calls=[
                    ToolCallDelta(index=0, function_arguments='{"command": "echo hello'),
                ],
            ),
            StreamChunk(
                tool_calls=[
                    ToolCallDelta(index=0, function_arguments=' world"}'),
                ],
                usage=TokenUsageUpdate(prompt_tokens=3, completion_tokens=5, total_tokens=8),
                is_complete=True,
            ),
        ]
        self._second_chunks = [
            StreamChunk(content="Tool finished"),
            StreamChunk(
                usage=TokenUsageUpdate(prompt_tokens=4, completion_tokens=2, total_tokens=6),
                is_complete=True,
            ),
        ]

    def _make_chat_request(self, messages, stream: bool = False, **kwargs):
        _ = messages, stream, kwargs
        return None

    def _extract_stream_chunks(self, response):
        _ = response
        self._stream_calls += 1
        chunks = self._first_chunks if self._stream_calls == 1 else self._second_chunks
        yield from chunks

    def stream_chat(self, messages, **kwargs):
        self.captured_messages = list(messages)
        self.captured_kwargs = dict(kwargs)
        self._stream_calls += 1
        chunks = self._first_chunks if self._stream_calls == 1 else self._second_chunks
        yield from chunks


@pytest.mark.unit
def test_chat_workflow_uses_merged_structured_tool_calls() -> None:
    provider = _ToolCallStreamProvider()
    chat_service = ChatService(provider=provider, system_prompt="You are Alice")
    orchestrator = MagicMock()
    orchestration_result = MagicMock()
    orchestration_result.assistant_message = MagicMock()
    orchestration_result.tool_messages = []
    orchestration_result.execution_results = []
    orchestrator.execute_tool_calls.return_value = orchestration_result

    workflow = ChatWorkflow(
        chat_service=chat_service,
        execution_service=MagicMock(),
        function_calling_orchestrator=orchestrator,
    )

    context = WorkflowContext(
        request_context=RequestContext(
            request_type=RequestType.CHAT,
            metadata={"trace_id": "trace-1", "request_id": "req-1", "task_id": "task-1"},
        ),
        user_input="run something",
    )

    responses = list(workflow.execute(context))

    assert responses
    assert all(isinstance(response, RuntimeEventResponse) for response in responses)
    runtime_responses = cast(list[RuntimeEventResponse], responses)
    assert all(response.response_type == ResponseType.RUNTIME_EVENT for response in runtime_responses)

    event_types = [response.event_type for response in runtime_responses]
    assert event_types == [
        RuntimeEventType.STATUS_CHANGED,
        RuntimeEventType.CONTENT_DELTA,
        RuntimeEventType.TOOL_CALL_STARTED,
        RuntimeEventType.CONTENT_DELTA,
        RuntimeEventType.TOOL_CALL_ARGUMENT_DELTA,
        RuntimeEventType.USAGE_UPDATED,
        RuntimeEventType.TOOL_CALL_ARGUMENT_DELTA,
        RuntimeEventType.TOOL_CALL_COMPLETED,
        RuntimeEventType.STATUS_CHANGED,
        RuntimeEventType.CONTENT_DELTA,
        RuntimeEventType.USAGE_UPDATED,
        RuntimeEventType.MESSAGE_COMPLETED,
    ]

    assert runtime_responses[0].payload == {"status": StatusType.THINKING.value}
    assert runtime_responses[1].payload == {"content": "Hello "}
    assert runtime_responses[2].payload["function"]["name"] == "run_bash"
    assert runtime_responses[3].payload == {"content": "world"}
    assert runtime_responses[4].payload["delta"] == '{"command": "echo hello'
    assert runtime_responses[5].payload["usage"]["total_tokens"] == 8
    assert runtime_responses[6].payload["function"]["arguments"] == '{"command": "echo hello world"}'
    assert runtime_responses[8].payload == {"status": StatusType.THINKING.value}
    assert runtime_responses[9].payload == {"content": "Tool finished"}
    assert runtime_responses[10].payload["usage"]["total_tokens"] == 6
    assert runtime_responses[11].payload["content"] == "Tool finished"
    assert runtime_responses[11].payload["usage"]["total_tokens"] == 6

    final_runtime_output = runtime_responses[11].runtime_output
    assert final_runtime_output is not None
    assert final_runtime_output.status == StatusType.DONE.value
    assert final_runtime_output.content == "Tool finished"
    assert final_runtime_output.usage["total_tokens"] == 6

    orchestrator.execute_tool_calls.assert_called_once()
    tool_calls = orchestrator.execute_tool_calls.call_args.args[0]
    assert tool_calls == [
        {
            "id": "call_1",
            "type": "function",
            "index": 0,
            "function": {
                "name": "run_bash",
                "arguments": '{"command": "echo hello world"}',
            },
        }
    ]
    assert orchestrator.execute_tool_calls.call_args.kwargs["assistant_content"] == "Hello world"

    assert provider.captured_kwargs is not None
    assert provider.captured_kwargs["tool_choice"] == "auto"
    assert len(provider.captured_kwargs["tools"]) == 2


@pytest.mark.unit
def test_chat_workflow_emits_tool_result_metadata_for_failure_types() -> None:
    provider = _ToolCallStreamProvider()
    chat_service = ChatService(provider=provider, system_prompt="You are Alice")
    invocation = ToolInvocation(id="call_1", name="run_bash", arguments='{"command": "echo hello world"}')
    orchestration_result = MagicMock()
    orchestration_result.assistant_message = ChatMessage.assistant(
        "Hello world",
        tool_calls=[invocation.to_assistant_tool_call()],
    )
    orchestration_result.tool_messages = [
        ChatMessage.tool(
            content='{"tool_name": "run_bash", "success": false}',
            tool_call_id="call_1",
        )
    ]
    orchestration_result.execution_results = [
        ToolExecutionResult(
            invocation=invocation,
            payload=ToolResultPayload(
                tool_name="run_bash",
                success=False,
                output="",
                error="run_bash 包含未定义参数: extra",
                status="failure",
                metadata={"error_type": "invalid_arguments"},
            ),
            execution_result=ExecutionResult.error_result("run_bash 包含未定义参数: extra"),
        )
    ]
    orchestrator = MagicMock()
    orchestrator.execute_tool_calls.return_value = orchestration_result

    workflow = ChatWorkflow(
        chat_service=chat_service,
        execution_service=MagicMock(),
        function_calling_orchestrator=orchestrator,
    )

    context = WorkflowContext(
        request_context=RequestContext(
            request_type=RequestType.CHAT,
            metadata={"trace_id": "trace-1", "request_id": "req-1", "task_id": "task-1"},
        ),
        user_input="run something",
    )

    responses = list(workflow.execute(context))
    tool_result_events = [
        response for response in responses
        if isinstance(response, RuntimeEventResponse) and response.event_type == RuntimeEventType.TOOL_RESULT
    ]

    assert len(tool_result_events) == 1
    assert tool_result_events[0].payload["status"] == "failure"
    assert tool_result_events[0].payload["metadata"]["error_type"] == "invalid_arguments"


@pytest.mark.unit
def test_chat_workflow_prefers_request_envelope_metadata_and_avoids_runtime_context_metadata_duplication() -> None:
    provider = _ToolCallStreamProvider()
    chat_service = ChatService(provider=provider, system_prompt="You are Alice")
    orchestrator = MagicMock()
    orchestration_result = MagicMock()
    orchestration_result.assistant_message = MagicMock()
    orchestration_result.tool_messages = []
    orchestration_result.execution_results = []
    orchestrator.execute_tool_calls.return_value = orchestration_result

    workflow = ChatWorkflow(
        chat_service=chat_service,
        execution_service=MagicMock(),
        function_calling_orchestrator=orchestrator,
    )

    request_envelope = RequestEnvelope(
        system_prompt="You are Alice",
        messages=[],
        model_context={"memory_snapshot": {"working": "notes"}},
        request_metadata=RequestMetadata(
            trace_id="trace-envelope",
            request_id="req-envelope",
            task_id="task-envelope",
            session_id="session-envelope",
            span_id="span-envelope",
        ),
    )
    context = WorkflowContext(
        request_context=RequestContext(
            request_type=RequestType.CHAT,
            metadata={
                "trace_id": "trace-request",
                "request_id": "req-request",
                "task_id": "task-request",
                "session_id": "session-request",
                "span_id": "span-request",
                "runtime_context": {"request_metadata": {"trace_id": "trace-request"}},
            },
        ),
        user_input="run something",
        request_envelope=request_envelope,
    )

    list(workflow.execute(context))

    assert provider.captured_kwargs is not None
    assert provider.captured_kwargs["request_envelope"]["request_metadata"] == {
        "session_id": "session-envelope",
        "trace_id": "trace-envelope",
        "request_id": "req-envelope",
        "task_id": "task-envelope",
        "span_id": "span-envelope",
        "enable_thinking": True,
        "stream": True,
    }
    assert provider.captured_kwargs["metadata"] == {
        "trace_id": "trace-envelope",
        "request_id": "req-envelope",
        "task_id": "task-envelope",
        "session_id": "session-envelope",
        "span_id": "span-envelope",
    }
    assert "runtime_context" not in provider.captured_kwargs["metadata"]


@pytest.mark.unit
def test_chat_workflow_falls_back_to_request_context_metadata_when_request_envelope_metadata_missing() -> None:
    provider = _ToolCallStreamProvider()
    chat_service = ChatService(provider=provider, system_prompt="You are Alice")
    orchestrator = MagicMock()
    orchestration_result = MagicMock()
    orchestration_result.assistant_message = MagicMock()
    orchestration_result.tool_messages = []
    orchestration_result.execution_results = []
    orchestrator.execute_tool_calls.return_value = orchestration_result

    workflow = ChatWorkflow(
        chat_service=chat_service,
        execution_service=MagicMock(),
        function_calling_orchestrator=orchestrator,
    )

    request_envelope = RequestEnvelope(
        system_prompt="You are Alice",
        messages=[],
        request_metadata=RequestMetadata(),
    )
    context = WorkflowContext(
        request_context=RequestContext(
            request_type=RequestType.CHAT,
            metadata={
                "trace_id": "trace-request",
                "request_id": "req-request",
                "task_id": "task-request",
                "session_id": "session-request",
                "span_id": "span-request",
            },
        ),
        user_input="run something",
        request_envelope=request_envelope,
    )

    list(workflow.execute(context))

    assert provider.captured_kwargs is not None
    assert provider.captured_kwargs["request_envelope"]["request_metadata"] == {
        "session_id": "",
        "trace_id": "",
        "request_id": "",
        "task_id": "",
        "span_id": "",
        "enable_thinking": True,
        "stream": True,
    }
    assert provider.captured_kwargs["metadata"] == {
        "trace_id": "trace-request",
        "request_id": "req-request",
        "task_id": "task-request",
        "session_id": "session-request",
        "span_id": "span-request",
    }


@pytest.mark.unit
def test_chat_service_stream_chat_merges_structured_tool_calls() -> None:
    provider = _ToolCallStreamProvider()
    service = ChatService(provider=provider, system_prompt="You are Alice")

    chunks: list[StreamChunk] = []
    response = service.stream_chat("run something", on_chunk=chunks.append)

    assert len(chunks) == 4
    assert response.content == "Hello world"
    assert response.tool_calls == [
        {
            "id": "call_1",
            "type": "function",
            "index": 0,
            "function": {
                "name": "run_bash",
                "arguments": '{"command": "echo hello world"}',
            },
        }
    ]
    assert response.usage is not None
    assert response.usage.total_tokens == 8
    assert service.messages[-1].role == "assistant"
    assert service.messages[-1].tool_calls == response.tool_calls


__all__ = []
