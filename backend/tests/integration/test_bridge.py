"""
Bridge 通信集成测试

测试 Rust TUI 与 Python Backend 之间的通信协议
"""

import json
from unittest.mock import patch

import pytest

from backend.alice.application.dto.responses import (
    ExecutingToolResponse,
    RuntimeEventResponse,
    RuntimeEventType,
    StatusResponse,
    StatusType as ResponseStatusType,
    response_to_dict,
)
from backend.alice.infrastructure.bridge.legacy_compatibility_serializer import (
    serialize_application_response,
    serialize_canonical_event,
    serialize_error_message,
    serialize_status_message,
)
from backend.alice.infrastructure.bridge.canonical_bridge import (
    CanonicalBridgeEvent,
    CanonicalEventType,
)
from backend.alice.infrastructure.bridge.server import BridgeServer, main_with_agent
from backend.alice.infrastructure.bridge.transport import TransportProtocol
from backend.alice.infrastructure.bridge.protocol.messages import (
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
    InterruptMessage,
    MessageType,
    StatusType,
    FrontendRequest,
    INTERRUPT_SIGNAL,
)


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

    def test_runtime_unknown_event_projects_to_none(self):
        """旧协议不支持的事件不应伪造新顶层消息类型"""
        data = serialize_application_response(
            RuntimeEventResponse(
                event_type=RuntimeEventType.TOOL_RESULT,
                payload={"tool_call_id": "call_1", "content": "ok"},
            )
        )

        assert data is None

    def test_canonical_tool_call_started_projects_to_status_message(self):
        """canonical tool_call_started 事件必须投影为 legacy status 消息"""
        data = serialize_canonical_event(
            CanonicalBridgeEvent(
                event_type=CanonicalEventType.TOOL_CALL_STARTED,
                payload={"tool_name": "run_python"},
            )
        )

        assert data == {"type": "status", "content": "executing_tool"}

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


class TestBridgeServerOutputCompatibility:
    """BridgeServer 输出必须统一走 legacy 兼容收口。"""

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
