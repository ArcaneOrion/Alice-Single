"""
内存模型单元测试

测试内存相关的数据模型
"""

import pytest
from datetime import datetime, timedelta

from backend.alice.core.interfaces.memory_store import (
    MemoryEntry,
    RoundEntry,
)


# ============================================================================
# MemoryEntry 测试
# ============================================================================

class TestMemoryEntry:
    """MemoryEntry 模型测试"""

    def test_create_memory_entry(self):
        """测试创建内存条目"""
        entry = MemoryEntry(
            content="Test content",
            timestamp=datetime.now(),
            metadata={"source": "test"}
        )

        assert entry.content == "Test content"
        assert isinstance(entry.timestamp, datetime)
        assert entry.metadata["source"] == "test"

    def test_metadata_defaults_to_empty_dict(self):
        """测试元数据默认为空字典"""
        entry = MemoryEntry(
            content="Test",
            timestamp=datetime.now()
        )

        assert entry.metadata == {}

    def test_metadata_with_none(self):
        """测试元数据为 None 时转为空字典"""
        entry = MemoryEntry(
            content="Test",
            timestamp=datetime.now(),
            metadata=None
        )

        assert entry.metadata == {}


# ============================================================================
# RoundEntry 测试
# ============================================================================

class TestRoundEntry:
    """RoundEntry 模型测试"""

    def test_create_round_entry(self):
        """测试创建对话轮次"""
        entry = RoundEntry(
            user_input="Hello",
            assistant_thinking="Thinking...",
            assistant_response="Hi there!",
            timestamp=datetime.now()
        )

        assert entry.user_input == "Hello"
        assert entry.assistant_thinking == "Thinking..."
        assert entry.assistant_response == "Hi there!"

    def test_timestamp_defaults_to_now(self):
        """测试时间戳默认为当前时间"""
        before = datetime.now()
        entry = RoundEntry(
            user_input="Test",
            assistant_response="Response"
        )
        after = datetime.now()

        assert before <= entry.timestamp <= after

    def test_default_thinking_is_empty(self):
        """测试默认思考为空"""
        entry = RoundEntry(
            user_input="Test",
            assistant_response="Response"
        )

        assert entry.assistant_thinking == ""

    def test_all_fields_present(self):
        """测试所有字段存在"""
        entry = RoundEntry(
            user_input="What is AI?",
            assistant_thinking="AI is artificial intelligence",
            assistant_response="AI stands for Artificial Intelligence",
            timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        assert entry.user_input == "What is AI?"
        assert entry.assistant_thinking == "AI is artificial intelligence"
        assert entry.assistant_response == "AI stands for Artificial Intelligence"
        assert entry.timestamp == datetime(2024, 1, 1, 12, 0, 0)


# ============================================================================
# 序列化测试
# ============================================================================

class TestSerialization:
    """序列化测试"""

    def test_memory_entry_to_dict(self):
        """测试内存条目转字典"""
        entry = MemoryEntry(
            content="Test",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            metadata={"key": "value"}
        )

        data = {
            "content": entry.content,
            "timestamp": entry.timestamp.isoformat(),
            "metadata": entry.metadata
        }

        assert data["content"] == "Test"
        assert "2024-01-01" in data["timestamp"]
        assert data["metadata"]["key"] == "value"

    def test_round_entry_to_dict(self):
        """测试对话轮次转字典"""
        entry = RoundEntry(
            user_input="Hello",
            assistant_thinking="Hi",
            assistant_response="Hello!",
            timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        data = {
            "user_input": entry.user_input,
            "assistant_thinking": entry.assistant_thinking,
            "assistant_response": entry.assistant_response,
            "timestamp": entry.timestamp.isoformat()
        }

        assert data["user_input"] == "Hello"
        assert data["assistant_thinking"] == "Hi"
        assert data["assistant_response"] == "Hello!"


__all__ = []
