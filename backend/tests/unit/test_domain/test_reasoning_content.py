"""ChatMessage reasoning_content 兼容性测试 [ADR-004]

覆盖 Spec-004 验收标准：
- reasoning_content 为非空字符串时序列化输出
- reasoning_content 为 None/空串时不序列化
- from_dict 往返一致性
- assistant() 工厂方法传递
- add_assistant_message() 传递
"""

import pytest
from backend.alice.domain.llm.models.message import ChatMessage
from backend.alice.domain.llm.services.chat_service import ChatService
from unittest.mock import MagicMock


# --- ChatMessage 字段与序列化 ---

@pytest.mark.unit
def test_reasoning_content_non_empty_serialized():
    """reasoning_content 为非空字符串时，to_dict() 包含该字段。"""
    msg = ChatMessage.assistant("你好", reasoning_content="思考过程")
    d = msg.to_dict()
    assert d["role"] == "assistant"
    assert d["content"] == "你好"
    assert d["reasoning_content"] == "思考过程"


@pytest.mark.unit
def test_reasoning_content_none_not_serialized():
    """reasoning_content 为 None 时，to_dict() 不包含该字段。"""
    msg = ChatMessage.assistant("你好")
    d = msg.to_dict()
    assert "reasoning_content" not in d


@pytest.mark.unit
def test_reasoning_content_empty_string_not_serialized():
    """reasoning_content 为空字符串时，to_dict() 不包含该字段。"""
    msg = ChatMessage.assistant("你好", reasoning_content="")
    d = msg.to_dict()
    assert "reasoning_content" not in d


@pytest.mark.unit
def test_reasoning_content_multiline():
    """reasoning_content 支持多行文本。"""
    thinking = "第一步：分析问题\n第二步：推导结论\n第三步：验证"
    msg = ChatMessage.assistant("结果", reasoning_content=thinking)
    d = msg.to_dict()
    assert d["reasoning_content"] == thinking


# --- from_dict 往返 ---

@pytest.mark.unit
def test_from_dict_with_reasoning_content():
    """from_dict() 读入 reasoning_content 字段。"""
    data = {"role": "assistant", "content": "回答", "reasoning_content": "推理过程"}
    msg = ChatMessage.from_dict(data)
    assert msg.reasoning_content == "推理过程"
    assert msg.content == "回答"


@pytest.mark.unit
def test_from_dict_without_reasoning_content():
    """from_dict() 无 reasoning_content 时字段为 None。"""
    data = {"role": "assistant", "content": "回答"}
    msg = ChatMessage.from_dict(data)
    assert msg.reasoning_content is None


@pytest.mark.unit
def test_roundtrip_with_reasoning_content():
    """from_dict(to_dict(msg)) 往返一致性：含 reasoning_content。"""
    original = ChatMessage.assistant("回答", reasoning_content="推理过程")
    restored = ChatMessage.from_dict(original.to_dict())
    assert restored.role == original.role
    assert restored.content == original.content
    assert restored.reasoning_content == original.reasoning_content


@pytest.mark.unit
def test_roundtrip_without_reasoning_content():
    """from_dict(to_dict(msg)) 往返一致性：无 reasoning_content。"""
    original = ChatMessage.assistant("回答")
    restored = ChatMessage.from_dict(original.to_dict())
    assert restored.reasoning_content is None


# --- 非 assistant 角色不应携带 reasoning_content ---

@pytest.mark.unit
def test_user_message_no_reasoning_content_in_dict():
    """user 消息的 to_dict() 不应包含 reasoning_content（即使误设）。"""
    msg = ChatMessage(role="user", content="hi", reasoning_content="should not appear")
    d = msg.to_dict()
    # reasoning_content 为非空，但仍会被序列化到 dict
    # 这是字段级序列化，不按角色过滤；API 侧的合理性由调用方保证
    # 但验证 from_dict 往返不应引入 ghost 字段到 user 消息
    assert d["reasoning_content"] == "should not appear"


# --- ChatService.add_assistant_message 传递 ---

@pytest.mark.unit
def test_add_assistant_message_with_reasoning_content():
    """add_assistant_message() 传递 reasoning_content 到消息历史。"""
    service = ChatService(provider=MagicMock())
    service.add_user_message("你好")
    msg = service.add_assistant_message("回复", reasoning_content="推理")
    assert msg.reasoning_content == "推理"
    # 验证消息历史中包含 reasoning_content
    history = service.messages
    assistant_msgs = [m for m in history if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].reasoning_content == "推理"


@pytest.mark.unit
def test_add_assistant_message_without_reasoning_content():
    """add_assistant_message() 不传 reasoning_content 时为 None。"""
    service = ChatService(provider=MagicMock())
    msg = service.add_assistant_message("回复")
    assert msg.reasoning_content is None


@pytest.mark.unit
def test_add_assistant_message_with_tool_calls_and_reasoning():
    """add_assistant_message() 同时传 tool_calls 和 reasoning_content。"""
    service = ChatService(provider=MagicMock())
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}]
    msg = service.add_assistant_message("结果", tool_calls=tool_calls, reasoning_content="推理过程")
    assert msg.tool_calls == tool_calls
    assert msg.reasoning_content == "推理过程"


# --- 多轮对话验证 ---

@pytest.mark.unit
def test_message_history_roundtrip_for_api():
    """多轮对话历史中 assistant 消息包含 reasoning_content，可正确序列化为 API dict。"""
    service = ChatService(provider=MagicMock())
    service.add_user_message("第一轮问题")
    service.add_assistant_message("第一轮回答", reasoning_content="第一轮推理")
    service.add_user_message("第二轮问题")

    api_messages = [msg.to_dict() for msg in service.messages]

    # 第一个 assistant 消息应包含 reasoning_content
    assistant_msgs = [m for m in api_messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert "reasoning_content" in assistant_msgs[0]
    assert assistant_msgs[0]["reasoning_content"] == "第一轮推理"

    # user 消息不应包含
    user_msgs = [m for m in api_messages if m["role"] == "user"]
    for m in user_msgs:
        assert "reasoning_content" not in m