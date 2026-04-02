"""
Bridge 通信集成测试

测试 Rust TUI 与 Python Backend 之间的通信协议
"""

import io
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from backend.alice.application.dto.responses import (
    ContentResponse,
    DoneResponse,
    ExecutingToolResponse,
    RuntimeEventResponse,
    RuntimeEventType,
    StatusResponse,
    TokensResponse,
    response_to_dict,
)
from backend.alice.application.dto.responses import (
    StatusType as ResponseStatusType,
)
from backend.alice.cli.main import TUIBridge
from backend.alice.core.config.settings import LoggingConfig
from backend.alice.core.logging.configure import configure_logging
from backend.alice.infrastructure.bridge.canonical_bridge import (
    CanonicalBridgeEvent,
    CanonicalEventType,
)
from backend.alice.infrastructure.bridge.legacy_compatibility_serializer import (
    serialize_application_response,
    serialize_canonical_event,
    serialize_error_message,
    serialize_status_message,
)
from backend.alice.infrastructure.bridge.protocol.messages import (
    INTERRUPT_SIGNAL,
    ContentMessage,
    ErrorMessage,
    FrontendRequest,
    InterruptMessage,
    MessageType,
    StatusMessage,
    StatusType,
    ThinkingMessage,
    TokensMessage,
)
from backend.alice.infrastructure.bridge.server import (
    BridgeServer,
    create_bridge_server,
    main_with_agent,
)
from backend.alice.infrastructure.bridge.transport import StdioTransport, TransportProtocol


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@contextmanager
def _preserve_root_logger_state():
    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = list(root_logger.handlers)
    original_filters = list(root_logger.filters)
    try:
        yield root_logger
    finally:
        current_handlers = list(root_logger.handlers)
        for handler in current_handlers:
            if handler not in original_handlers:
                handler.close()
        root_logger.handlers[:] = original_handlers
        root_logger.filters[:] = original_filters
        root_logger.setLevel(original_level)


# ============================================================================
# 消息序列化测试
# ============================================================================

class TestMessageSerialization:
    """消息序列化测试"""

    def test_status_message_serialization(self):
        """测试状态消息序列化"""
        msg = StatusMessage(content=StatusType.READY)

        data = {
            "type": MessageType.STATUS,
            "content": StatusType.READY
        }

        assert msg.type == data["type"]
        assert msg.content == data["content"]

    def test_thinking_message_serialization(self):
        """测试思考消息序列化"""
        msg = ThinkingMessage(content="Thinking...")

        assert msg.type == MessageType.THINKING
        assert msg.content == "Thinking..."

    def test_content_message_serialization(self):
        """测试正文消息序列化"""
        msg = ContentMessage(content="Hello, world!")

        assert msg.type == MessageType.CONTENT
        assert msg.content == "Hello, world!"

    def test_tokens_message_serialization(self):
        """测试 Token 消息序列化"""
        msg = TokensMessage(total=100, prompt=50, completion=50)

        assert msg.type == MessageType.TOKENS
        assert msg.total == 100
        assert msg.prompt == 50
        assert msg.completion == 50

    def test_error_message_serialization(self):
        """测试错误消息序列化"""
        msg = ErrorMessage(content="Something went wrong", code="ERR_001")

        assert msg.type == MessageType.ERROR
        assert msg.content == "Something went wrong"
        assert msg.code == "ERR_001"

    def test_interrupt_message_serialization(self):
        """测试中断消息序列化"""
        msg = InterruptMessage()

        assert msg.type == MessageType.INTERRUPT


# ============================================================================
# 消息反序列化测试
# ============================================================================

class TestMessageDeserialization:
    """消息反序列化测试"""

    def test_parse_json_status_message(self):
        """测试解析 JSON 状态消息"""
        json_str = '{"type": "status", "content": "ready"}'
        data = json.loads(json_str)

        assert data["type"] == "status"
        assert data["content"] == "ready"

    def test_parse_json_thinking_message(self):
        """测试解析 JSON 思考消息"""
        json_str = '{"type": "thinking", "content": "I am thinking"}'
        data = json.loads(json_str)

        assert data["type"] == "thinking"
        assert data["content"] == "I am thinking"

    def test_parse_json_content_message(self):
        """测试解析 JSON 正文消息"""
        json_str = '{"type": "content", "content": "Response text"}'
        data = json.loads(json_str)

        assert data["type"] == "content"
        assert data["content"] == "Response text"

    def test_parse_json_tokens_message(self):
        """测试解析 JSON Token 消息"""
        json_str = '{"type": "tokens", "total": 200, "prompt": 100, "completion": 100}'
        data = json.loads(json_str)

        assert data["type"] == "tokens"
        assert data["total"] == 200

    def test_parse_json_error_message(self):
        """测试解析 JSON 错误消息"""
        json_str = '{"type": "error", "content": "Error occurred", "code": "E001"}'
        data = json.loads(json_str)

        assert data["type"] == "error"
        assert data["content"] == "Error occurred"
        assert data["code"] == "E001"


# ============================================================================
# 消息类型枚举测试
# ============================================================================

class TestMessageTypeEnum:
    """消息类型枚举测试"""

    def test_message_type_values(self):
        """测试消息类型值"""
        assert MessageType.STATUS == "status"
        assert MessageType.THINKING == "thinking"
        assert MessageType.CONTENT == "content"
        assert MessageType.TOKENS == "tokens"
        assert MessageType.ERROR == "error"
        assert MessageType.INTERRUPT == "interrupt"

    def test_status_type_values(self):
        """测试状态类型值"""
        assert StatusType.READY == "ready"
        assert StatusType.THINKING == "thinking"
        assert StatusType.EXECUTING_TOOL == "executing_tool"
        assert StatusType.DONE == "done"


# ============================================================================
# 前端请求测试
# ============================================================================

class TestFrontendRequest:
    """前端请求测试"""

    def test_create_frontend_request(self):
        """测试创建前端请求"""
        request = FrontendRequest(input="Hello, Alice!")

        assert request.input == "Hello, Alice!"

    def test_empty_frontend_request(self):
        """测试空前端请求"""
        request = FrontendRequest()

        assert request.input == ""

    def test_parse_json_frontend_request(self):
        """测试解析 JSON 前端请求"""
        json_str = '{"input": "Tell me a joke"}'
        data = json.loads(json_str)

        request = FrontendRequest(input=data.get("input", ""))

        assert request.input == "Tell me a joke"


# ============================================================================
# 中断信号测试
# ============================================================================

class TestInterruptSignal:
    """中断信号测试"""

    def test_interrupt_signal_constant(self):
        """测试中断信号常量"""
        assert INTERRUPT_SIGNAL == "__INTERRUPT__"

    def test_interrupt_signal_detection(self):
        """测试中断信号检测"""
        user_input = "__INTERRUPT__"

        assert user_input == INTERRUPT_SIGNAL

    def test_normal_input_not_interrupt(self):
        """测试正常输入不是中断"""
        user_input = "Hello, Alice!"

        assert user_input != INTERRUPT_SIGNAL


# ============================================================================
# 流式输出测试
# ============================================================================

class TestStreamOutput:
    """流式输出测试"""

    def test_write_status_message_to_stdout(self, capsys):
        """测试写入状态消息到 stdout"""
        msg = StatusMessage(content=StatusType.READY)

        # 模拟写入
        output = json.dumps({"type": msg.type, "content": msg.content})
        print(output, flush=True)

        captured = capsys.readouterr()
        assert '"type": "status"' in captured.out

    def test_write_content_chunk_to_stdout(self, capsys):
        """测试写入内容块到 stdout"""
        msg = ContentMessage(content="Hello")

        output = json.dumps({"type": msg.type, "content": msg.content})
        print(output, flush=True)

        captured = capsys.readouterr()
        assert '"content": "Hello"' in captured.out

    def test_multiple_messages_sequence(self, capsys):
        """测试多消息序列"""
        messages = [
            StatusMessage(content=StatusType.THINKING),
            ThinkingMessage(content="Thinking..."),
            ContentMessage(content="Answer"),
            TokensMessage(total=100, prompt=50, completion=50),
            StatusMessage(content=StatusType.DONE),
        ]

        outputs = []
        for msg in messages:
            if isinstance(msg, TokensMessage):
                output = json.dumps(
                    {
                        "type": msg.type,
                        "total": msg.total,
                        "prompt": msg.prompt,
                        "completion": msg.completion,
                    }
                )
            else:
                output = json.dumps({"type": msg.type, "content": msg.content})
            outputs.append(output)
            print(output, flush=True)

        captured = capsys.readouterr()
        for output in outputs:
            assert output in captured.out


# ============================================================================
# 协议兼容性测试
# ============================================================================

class TestLegacyCompatibilitySerializer:
    """legacy compatibility serializer 回归测试"""

    def test_executing_tool_response_projects_to_status_message(self):
        """ExecutingToolResponse 必须投影为 legacy status 消息"""
        data = response_to_dict(ExecutingToolResponse(tool_type="bash", command_preview="ls"))

        assert data == {"type": "status", "content": "executing_tool"}

    def test_runtime_tool_call_started_projects_to_status_message(self):
        """tool_call_started 事件必须投影为 executing_tool 状态"""
        data = response_to_dict(
            RuntimeEventResponse(
                event_type=RuntimeEventType.TOOL_CALL_STARTED,
                payload={"tool_name": "run_bash"},
            )
        )

        assert data == {"type": "status", "content": "executing_tool"}

    def test_status_response_executing_tool_projects_to_status_message(self):
        """StatusResponse 也必须通过 compatibility serializer 投影"""
        data = serialize_application_response(
            StatusResponse(status=ResponseStatusType.EXECUTING_TOOL)
        )

        assert data == {"type": "status", "content": "executing_tool"}

    def test_status_response_streaming_projects_to_thinking(self):
        """streaming 状态必须向旧协议归一化为 thinking"""
        data = serialize_application_response(
            StatusResponse(status=ResponseStatusType.STREAMING)
        )

        assert data == {"type": "status", "content": "thinking"}

    def test_runtime_unknown_event_projects_to_none(self, caplog):
        """旧协议不支持的事件不应伪造新顶层消息类型"""
        with caplog.at_level(logging.INFO):
            data = serialize_application_response(
                RuntimeEventResponse(
                    event_type=RuntimeEventType.TOOL_RESULT,
                    payload={"tool_call_id": "call_1", "content": "ok"},
                )
            )

        assert data is None
        dropped = next(
            record
            for record in caplog.records
            if getattr(record, "event_type", "") == "bridge.event_dropped_by_legacy_projection"
        )
        assert dropped.data == {
            "source_kind": "canonical_event",
            "dropped_event_type": "tool_result",
            "reason": "unsupported_canonical_event",
            "payload_keys": ["content", "tool_call_id"],
        }

    def test_canonical_tool_call_started_projects_to_status_message(self, caplog):
        """canonical tool_call_started 事件必须投影为 legacy status 消息"""
        with caplog.at_level(logging.INFO):
            data = serialize_canonical_event(
                CanonicalBridgeEvent(
                    event_type=CanonicalEventType.TOOL_CALL_STARTED,
                    payload={"tool_name": "run_python"},
                )
            )

        assert data == {"type": "status", "content": "executing_tool"}
        used = next(
            record
            for record in caplog.records
            if getattr(record, "event_type", "") == "bridge.compatibility_serializer_used"
        )
        assert used.data == {
            "source_kind": "canonical_event",
            "canonical_event_type": "tool_call_started",
            "legacy_message_type": "status",
            "legacy_status": "executing_tool",
        }

    def test_streaming_status_normalizes_to_thinking(self):
        """streaming 必须保持向旧前端归一化为 thinking"""
        data = serialize_status_message("streaming")

        assert data == {"type": "status", "content": "thinking"}

    def test_status_response_shape_stays_legacy_compatible(self):
        """compatibility serializer 输出必须维持旧状态结构"""
        data = serialize_application_response(
            StatusResponse(status=ResponseStatusType.EXECUTING_TOOL)
        )

        assert data == {"type": "status", "content": "executing_tool"}


class TestMainWithAgentCompatibility:
    """main_with_agent 兼容输出测试"""

    def test_preserve_root_logger_state_restores_handlers_and_level(self, tmp_path: Path):
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)
        original_level = root_logger.level

        with _preserve_root_logger_state():
            configure_logging(
                LoggingConfig(
                    logs_dir=str(tmp_path),
                    file=str(tmp_path / "alice_runtime.log"),
                    dual_write_legacy=False,
                    enable_colors=False,
                ),
                enable_colors=False,
            )
            assert root_logger.level != original_level or list(root_logger.handlers) != original_handlers

        assert root_logger.level == original_level
        assert list(root_logger.handlers) == original_handlers

    def test_main_with_agent_initialization_failure_uses_legacy_error_shape(self, capsys):
        """初始化失败时必须输出旧 error 协议"""

        class FailingAgent:
            def __init__(self, **kwargs):
                _ = kwargs
                raise RuntimeError("boom")

        main_with_agent(agent_class=FailingAgent)

        captured = capsys.readouterr()
        assert json.loads(captured.out.strip()) == serialize_error_message(
            content="Initialization failed: boom"
        )

    def test_main_with_agent_initialization_failure_logs_bridge_error_to_tasks_jsonl(self, tmp_path: Path, capsys):
        """初始化失败时必须保持 legacy error shape，并将 bridge.error 写入 tasks.jsonl。"""

        class FailingAgent:
            def __init__(self, **kwargs):
                _ = kwargs
                raise RuntimeError("boom")

        with _preserve_root_logger_state():
            configure_logging(
                LoggingConfig(
                    logs_dir=str(tmp_path),
                    file=str(tmp_path / "alice_runtime.log"),
                    dual_write_legacy=False,
                    enable_colors=False,
                ),
                enable_colors=False,
            )

            main_with_agent(agent_class=FailingAgent)

        captured = capsys.readouterr()
        assert json.loads(captured.out.strip()) == serialize_error_message(
            content="Initialization failed: boom"
        )

        tasks_records = _read_jsonl(tmp_path / "tasks.jsonl")
        error_record = next(record for record in tasks_records if record["event_type"] == "bridge.error")

        assert error_record["level"] == "ERROR"
        assert error_record["source"]
        assert error_record["context"]["component"] == "bridge_server"
        assert error_record["data"] == {"phase": "initialization"}
        assert error_record["error"]["type"] == "RuntimeError"
        assert error_record["error"]["message"] == "boom"
        assert "RuntimeError: boom" in error_record["error"]["traceback"]

    def test_main_with_agent_runtime_failure_uses_legacy_error_shape(self, capsys):
        """运行失败时必须输出旧 error 协议"""

        class DummyAgent:
            def __init__(self, **kwargs):
                _ = kwargs

        with patch("backend.alice.infrastructure.bridge.server.create_bridge_server") as create_server:
            server = create_server.return_value
            server.run.side_effect = RuntimeError("explode")

            main_with_agent(agent_class=DummyAgent)

        captured = capsys.readouterr()
        assert json.loads(captured.out.strip()) == serialize_error_message(
            content="Runtime Error: explode. 请查看日志输出。"
        )


class _RecordingTransport(TransportProtocol):
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self._running = False
        self._message_callback = None
        self._eof_callback = None
        self._has_pending_interrupt = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def send_message(self, message) -> None:
        self.sent_messages.append(message)

    def send_raw(self, data: str) -> None:
        raise AssertionError(f"unexpected raw send: {data}")

    def set_message_callback(self, callback) -> None:
        self._message_callback = callback

    def set_eof_callback(self, callback) -> None:
        self._eof_callback = callback

    def is_running(self) -> bool:
        return self._running

    def drain_pending_interrupts(self) -> bool:
        found = self._has_pending_interrupt
        self._has_pending_interrupt = False
        return found

    def seed_pending_interrupt(self, pending: bool = True) -> None:
        self._has_pending_interrupt = pending

    def has_pending_interrupt(self) -> bool:
        return self._has_pending_interrupt


class TestBridgeServerOutputCompatibility:
    """BridgeServer 输出必须统一走 legacy 兼容收口。"""

    def test_bridge_server_no_longer_exposes_stream_manager_dependency(self):
        server = BridgeServer(agent=None, transport=_RecordingTransport())

        assert not hasattr(server, "stream_manager_class")

    def test_create_bridge_server_signature_has_no_stream_manager_parameter(self):
        import inspect

        signature = inspect.signature(create_bridge_server)

        assert "stream_manager_class" not in signature.parameters
        assert list(signature.parameters) == ["agent"]

    def test_bridge_package_no_longer_exports_default_stream_manager_class(self):
        import backend.alice.infrastructure.bridge as bridge_module

        assert "DefaultStreamManagerClass" not in bridge_module.__all__

    def test_bridge_package_no_longer_exports_stream_manager(self):
        import backend.alice.infrastructure.bridge as bridge_module

        assert "StreamManager" not in bridge_module.__all__


    def _create_server(self) -> tuple[BridgeServer, _RecordingTransport]:
        transport = _RecordingTransport()
        return BridgeServer(agent=None, transport=transport), transport

    def test_send_raw_message_normalizes_status_shape(self):
        server, transport = self._create_server()

        server.send_raw_message({"type": "status", "content": "streaming"})

        assert transport.sent_messages == [{"type": "status", "content": "thinking"}]

    def test_send_message_normalizes_status_enum_payload(self):
        server, transport = self._create_server()

        server.send_message({"type": MessageType.STATUS, "content": StatusType.EXECUTING_TOOL})

        assert transport.sent_messages == [{
            "type": "status",
            "content": "executing_tool",
        }]

    def test_send_message_normalizes_tokens_payload(self):
        server, transport = self._create_server()

        server.send_message({"type": "tokens", "total": "9", "prompt": "4", "completion": "5"})

        assert transport.sent_messages == [{
            "type": "tokens",
            "total": 9,
            "prompt": 4,
            "completion": 5,
        }]

    def test_send_raw_message_preserves_unknown_type(self):
        server, transport = self._create_server()

        payload = {"type": "interrupt"}
        server.send_raw_message(payload)

        assert transport.sent_messages == [payload]


class TestDualEntryParity:
    """新旧入口对同一响应必须输出一致的 legacy wire。"""

    @staticmethod
    def _legacy_outputs_for_responses(responses):
        return [response_to_dict(response) for response in responses if response_to_dict(response) is not None]

    def test_tui_bridge_send_response_matches_legacy_bridge_projection(self, capsys):
        bridge = TUIBridge()
        responses = [
            ContentResponse(content="hello bridge"),
            RuntimeEventResponse(
                event_type=RuntimeEventType.TOOL_CALL_STARTED,
                payload={"tool_name": "run_bash"},
            ),
            StatusResponse(status=ResponseStatusType.STREAMING),
        ]

        for response in responses:
            bridge._send_response(response)

        captured = capsys.readouterr()
        stdout_messages = [json.loads(line) for line in captured.out.splitlines() if line.strip()]

        assert stdout_messages == self._legacy_outputs_for_responses(responses)

    def test_tui_bridge_status_and_error_match_legacy_bridge_serializers(self, capsys):
        bridge = TUIBridge()

        bridge._send_status("streaming")
        bridge._send_error("boom", code="E1")

        captured = capsys.readouterr()
        stdout_messages = [json.loads(line) for line in captured.out.splitlines() if line.strip()]

        assert stdout_messages == [
            serialize_status_message("streaming"),
            serialize_error_message(content="boom", code="E1"),
        ]


class TestDualEntrySuccessPathParity:
    """新旧入口在同一成功流 handler 路径上必须输出一致的 legacy wire。"""

    @staticmethod
    def _build_success_path_responses():
        return [
            ContentResponse(content="hello bridge"),
            RuntimeEventResponse(
                event_type=RuntimeEventType.TOOL_CALL_STARTED,
                payload={"tool_name": "run_bash"},
            ),
            TokensResponse(total=9, prompt=4, completion=5),
            DoneResponse(),
        ]

    def test_tui_bridge_process_user_input_matches_bridge_handler_stdout_lines(self, capsys):
        responses = self._build_success_path_responses()

        new_entry_agent = MagicMock()
        new_entry_agent.chat.return_value = responses
        new_entry_bridge = TUIBridge()
        new_entry_bridge.agent = new_entry_agent

        new_entry_bridge._process_user_input("hello")
        new_entry_captured = capsys.readouterr()
        new_entry_lines = [line for line in new_entry_captured.out.splitlines() if line.strip()]
        new_entry_messages = [json.loads(line) for line in new_entry_lines]

        old_entry_agent = MagicMock()
        old_entry_agent.chat.return_value = responses
        stdout_stream = io.StringIO()
        old_entry_transport = StdioTransport(stdout_stream=stdout_stream, enable_utf8=False)
        old_entry_server = BridgeServer(agent=old_entry_agent, transport=old_entry_transport)

        old_entry_server.message_handler.handle_input("hello")

        old_entry_lines = [line for line in stdout_stream.getvalue().splitlines() if line.strip()]
        old_entry_messages = [json.loads(line) for line in old_entry_lines]

        new_entry_agent.chat.assert_called_once_with("hello")
        old_entry_agent.chat.assert_called_once_with("hello")
        assert new_entry_messages == old_entry_messages
        assert new_entry_lines == old_entry_lines


class TestBridgeHandlerCompatibility:
    """Bridge handler 必须复用 agent.chat 与 legacy serializer。"""

    def test_message_handler_forwards_agent_chat_responses(self):
        transport = _RecordingTransport()
        agent = MagicMock()
        agent.chat.return_value = [
            ContentResponse(content="hello bridge"),
            RuntimeEventResponse(
                event_type=RuntimeEventType.TOOL_CALL_STARTED,
                payload={"tool_name": "run_bash"},
            ),
        ]
        server = BridgeServer(agent=agent, transport=transport)

        server.message_handler.handle_input("hello")

        agent.chat.assert_called_once_with("hello")
        assert transport.sent_messages == [
            {"type": "content", "content": "hello bridge"},
            {"type": "status", "content": "executing_tool"},
        ]

    def test_interrupt_handler_propagates_to_agent_interrupt_and_done_ack(self):
        transport = _RecordingTransport()
        transport.seed_pending_interrupt()
        agent = MagicMock()
        server = BridgeServer(agent=agent, transport=transport)

        found = server.interrupt_handler.check_interrupt()
        assert transport.has_pending_interrupt() is False

        assert found is True
        agent.interrupt.assert_called_once_with()
        assert transport.sent_messages == [serialize_status_message("done")]
        assert server.interrupt_handler.interrupt_count == 1


class TestDualEntryInterruptParity:
    """新旧入口在入口层识别 interrupt 后必须输出同一最小 legacy ack。"""

    def test_tui_bridge_prechat_interrupt_matches_legacy_interrupt_handler(self, capsys):
        new_entry_agent = MagicMock()
        new_entry_bridge = TUIBridge()
        new_entry_bridge.agent = new_entry_agent
        new_entry_bridge.input_queue.put(INTERRUPT_SIGNAL)

        new_entry_bridge._process_user_input("hello")
        new_entry_captured = capsys.readouterr()
        new_entry_messages = [
            json.loads(line)
            for line in new_entry_captured.out.splitlines()
            if line.strip()
        ]

        old_entry_transport = _RecordingTransport()
        old_entry_transport.seed_pending_interrupt()
        old_entry_agent = MagicMock()
        old_entry_server = BridgeServer(agent=old_entry_agent, transport=old_entry_transport)

        found = old_entry_server.interrupt_handler.check_interrupt()

        assert found is True
        new_entry_agent.chat.assert_not_called()
        new_entry_agent.interrupt.assert_called_once_with()
        old_entry_agent.interrupt.assert_called_once_with()
        assert new_entry_messages == [serialize_status_message("done")]
        assert old_entry_transport.sent_messages == new_entry_messages


class TestDualEntryFailureParity:
    """新旧入口在同一 handler failure 路径上必须输出一致的 legacy error。"""

    def test_tui_bridge_chat_failure_matches_legacy_message_handler_error(self, capsys):
        new_entry_agent = MagicMock()
        new_entry_agent.chat.side_effect = RuntimeError("boom")
        new_entry_bridge = TUIBridge()
        new_entry_bridge.agent = new_entry_agent

        new_entry_bridge._process_user_input("hello")
        new_entry_captured = capsys.readouterr()
        new_entry_messages = [
            json.loads(line)
            for line in new_entry_captured.out.splitlines()
            if line.strip()
        ]

        old_entry_transport = _RecordingTransport()
        old_entry_agent = MagicMock()
        old_entry_agent.chat.side_effect = RuntimeError("boom")
        old_entry_server = BridgeServer(agent=old_entry_agent, transport=old_entry_transport)

        old_entry_server.message_handler.handle_input("hello")

        new_entry_agent.chat.assert_called_once_with("hello")
        old_entry_agent.chat.assert_called_once_with("hello")
        assert new_entry_messages == [serialize_error_message(content="Processing error: boom")]
        assert old_entry_transport.sent_messages == new_entry_messages


class TestProtocolCompatibility:
    """协议兼容性测试"""

    def test_message_with_unknown_field(self):
        """测试带未知字段的消息（兼容性）"""
        json_str = '{"type": "content", "content": "Hello", "unknown_field": "value"}'
        data = json.loads(json_str)

        assert data["type"] == "content"
        assert data["content"] == "Hello"
        assert data["unknown_field"] == "value"

    def test_message_with_missing_optional_field(self):
        """测试缺少可选字段的消息"""
        json_str = '{"type": "error", "content": "Error"}'
        data = json.loads(json_str)

        assert data["type"] == "error"
        assert data["content"] == "Error"
        assert "code" not in data  # code 是可选的


# ============================================================================
# 消息验证测试
# ============================================================================

class TestMessageValidation:
    """消息验证测试"""

    def test_valid_status_message(self):
        """测试有效状态消息"""
        msg = StatusMessage(content=StatusType.READY)
        assert msg.content in [s.value for s in StatusType]

    def test_invalid_status_content(self):
        """测试无效状态内容"""
        # StatusType 是枚举，只能接受预定义的值
        with pytest.raises(ValueError):
            StatusType("invalid_status")

    def test_tokens_message_non_negative(self):
        """测试 Token 消息非负"""
        msg = TokensMessage(total=100, prompt=50, completion=50)

        assert msg.total >= 0
        assert msg.prompt >= 0
        assert msg.completion >= 0

        # 验证 total = prompt + completion
        assert msg.total == msg.prompt + msg.completion


# ============================================================================
# 编解码测试
# ============================================================================

class TestCodec:
    """编解码测试"""

    def test_encode_unicode_content(self):
        """测试编码 Unicode 内容"""
        msg = ContentMessage(content="Hello 世界 !")

        output = json.dumps({"type": msg.type, "content": msg.content})
        decoded = json.loads(output)

        assert decoded["content"] == "Hello 世界 !"

    def test_encode_special_characters(self):
        """测试编码特殊字符"""
        msg = ContentMessage(content="Line 1\nLine 2\tTabbed")

        output = json.dumps({"type": msg.type, "content": msg.content})
        decoded = json.loads(output)

        assert "\n" in decoded["content"]
        assert "\t" in decoded["content"]

    def test_encode_emoji(self):
        """测试编码表情符号"""
        msg = ContentMessage(content="Hello 😊")

        output = json.dumps({"type": msg.type, "content": msg.content})
        decoded = json.loads(output)

        assert "😊" in decoded["content"]


__all__ = []
