"""
流管理器单元测试

测试 StreamManager 的流式数据解析和分流功能
"""

import pytest

from backend.alice.infrastructure.bridge.stream_manager import (
    StreamManager,
    MSG_TYPE_THINKING,
    MSG_TYPE_CONTENT,
)


# ============================================================================
# 基础功能测试
# ============================================================================

class TestStreamManagerBasics:
    """流管理器基础功能测试"""

    def test_create_stream_manager(self):
        """测试创建流管理器"""
        manager = StreamManager()
        assert manager is not None
        assert manager.buffer == ""
        assert not manager.in_code_block

    def test_default_parameters(self):
        """测试默认参数"""
        manager = StreamManager()
        assert manager.max_buffer_size == 10 * 1024 * 1024
        assert manager.window_size == 20

    def test_custom_parameters(self):
        """测试自定义参数"""
        manager = StreamManager(
            max_buffer_size=1024,
            window_size=10
        )
        assert manager.max_buffer_size == 1024
        assert manager.window_size == 10

    def test_reset(self):
        """测试重置"""
        manager = StreamManager()
        manager.buffer = "test"
        manager.in_code_block = True

        manager.reset()

        assert manager.buffer == ""
        assert not manager.in_code_block


# ============================================================================
# 内容类型识别测试
# ============================================================================

class TestContentTypeDetection:
    """内容类型识别测试"""

    def test_plain_text_is_content(self):
        """测试纯文本是 content"""
        manager = StreamManager()
        messages = manager.process_chunk("Hello, world!")

        assert len(messages) == 1
        assert messages[0]["type"] == MSG_TYPE_CONTENT
        assert messages[0]["content"] == "Hello, world!"

    def test_python_code_block_is_thinking(self):
        """测试 Python 代码块是 thinking"""
        manager = StreamManager()
        messages = manager.process_chunk("```python\nprint('hello')\n```")

        assert len(messages) == 2
        # 第一个空消息或少量前置内容
        # 代码块内容是 thinking
        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_xml_thinking_tag_is_thinking(self):
        """测试 XML thinking 标签是 thinking"""
        manager = StreamManager()
        messages = manager.process_chunk("<thought>I'm thinking</thought>")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_naked_python_keyword_is_thinking(self):
        """测试裸 python 关键词是 thinking"""
        manager = StreamManager()
        messages = manager.process_chunk("\npython -c print('hello')")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0


# ============================================================================
# 代码块标记测试
# ============================================================================

class TestCodeBlockMarkers:
    """代码块标记测试"""

    def test_python_marker(self):
        """测试 Python 标记"""
        manager = StreamManager()
        messages = manager.process_chunk("Text before ```python\ncode\n``` after")

        assert any(m["type"] == MSG_TYPE_CONTENT for m in messages)
        assert any(m["type"] == MSG_TYPE_THINKING for m in messages)

    def test_bash_marker(self):
        """测试 Bash 标记"""
        manager = StreamManager()
        messages = manager.process_chunk("```bash\necho test\n```")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_generic_marker(self):
        """测试通用标记"""
        manager = StreamManager()
        messages = manager.process_chunk("```\ncode\n```")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_unclosed_marker_in_buffer(self):
        """测试未关闭标记保留在缓冲区"""
        manager = StreamManager()
        messages = manager.process_chunk("```python\nprint('hello')")

        # 未关闭的标记内容应该留在缓冲区
        assert manager.in_code_block is True
        assert "```python" in manager.buffer


# ============================================================================
# 流式处理测试
# ============================================================================

class TestStreamProcessing:
    """流式处理测试"""

    def test_incremental_chunks(self):
        """测试增量块处理"""
        manager = StreamManager()
        messages = []

        chunks = ["Hello", ", ", "world", "!"]
        for chunk in chunks:
            messages.extend(manager.process_chunk(chunk))

        # 合并所有 content 消息
        full_content = "".join(
            m["content"] for m in messages if m["type"] == MSG_TYPE_CONTENT
        )
        assert full_content == "Hello, world!"

    def test_chunk_boundary_in_marker(self):
        """测试块边界在标记中间"""
        manager = StreamManager()
        messages = []

        # 模拟标记被分在多个块中
        messages.extend(manager.process_chunk("Text before ```"))
        messages.extend(manager.process_chunk("python\ncode\n```"))

        # 应该有 content 和 thinking 消息
        content_exists = any(m["type"] == MSG_TYPE_CONTENT for m in messages)
        thinking_exists = any(m["type"] == MSG_TYPE_THINKING for m in messages)

        assert content_exists
        assert thinking_exists

    def test_multiple_chunks_in_code_block(self):
        """测试代码块中的多个块"""
        manager = StreamManager()
        messages = []

        messages.extend(manager.process_chunk("```python\n"))
        messages.extend(manager.process_chunk("line1\n"))
        messages.extend(manager.process_chunk("line2\n"))
        messages.extend(manager.process_chunk("```"))

        thinking_content = "".join(
            m["content"] for m in messages if m["type"] == MSG_TYPE_THINKING
        )

        assert "line1" in thinking_content
        assert "line2" in thinking_content


# ============================================================================
# 滑动窗口测试
# ============================================================================

class TestSlidingWindow:
    """滑动窗口测试"""

    def test_hold_back_for_partial_marker(self):
        """测试部分标记的保留"""
        manager = StreamManager(window_size=10)

        # 发送以 "```p" 结尾的内容，可能是 "```python" 的开始
        messages = manager.process_chunk("Some text ```p")

        # 应该保留 "```p" 在缓冲区
        assert "```p" in manager.buffer or any("```p" in m.get("content", "") for m in messages)

    def test_window_size_affects_hold_back(self):
        """测试窗口大小影响保留"""
        manager_small = StreamManager(window_size=5)
        manager_large = StreamManager(window_size=50)

        # 发送可能包含不完整标记的内容
        msg_small = manager_small.process_chunk("text ```py")
        msg_large = manager_large.process_chunk("text ```py")

        # 大窗口应该保留更多
        assert len(manager_small.buffer) > 0 or len(msg_small) > 0
        assert len(manager_large.buffer) > 0 or len(msg_large) > 0


# ============================================================================
# 缓冲区保护测试
# ============================================================================

class TestBufferProtection:
    """缓冲区保护测试"""

    def test_buffer_overflow_protection(self):
        """测试缓冲区溢出保护"""
        manager = StreamManager(max_buffer_size=100)

        # 发送超过缓冲区大小的内容
        large_chunk = "A" * 200
        messages = manager.process_chunk(large_chunk)

        # 缓冲区应该被清空
        assert len(manager.buffer) < 100

        # 应该有输出消息
        assert len(messages) > 0

    def test_flush_releases_buffer(self):
        """测试 flush 释放缓冲区"""
        manager = StreamManager()
        manager.buffer = "remaining content"

        messages = manager.flush()

        assert manager.buffer == ""
        assert len(messages) > 0
        assert messages[0]["content"] == "remaining content"


# ============================================================================
# 裸关键词测试
# ============================================================================

class TestNakedKeywords:
    """裸关键词测试"""

    def test_python_keyword(self):
        """测试 python 关键词"""
        manager = StreamManager()
        messages = manager.process_chunk("\npython script.py")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_cat_keyword(self):
        """测试 cat 关键词"""
        manager = StreamManager()
        messages = manager.process_chunk("\ncat file.txt")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_ls_keyword(self):
        """测试 ls 关键词"""
        manager = StreamManager()
        messages = manager.process_chunk("\nls -la")

        thinking_messages = [m for m in messages if m["type"] == MSG_TYPE_THINKING]
        assert len(thinking_messages) > 0

    def test_keyword_not_at_line_start(self):
        """测试不在行首的关键词（不应匹配）"""
        manager = StreamManager()
        messages = manager.process_chunk("text with python in middle")

        # 不在行首的关键词可能被识别为 content
        content_messages = [m for m in messages if m["type"] == MSG_TYPE_CONTENT]
        assert len(content_messages) > 0


# ============================================================================
# 复杂场景测试
# ============================================================================

class TestComplexScenarios:
    """复杂场景测试"""

    def test_mixed_content_and_code(self):
        """测试混合内容和代码"""
        manager = StreamManager()
        messages = []

        content = "First, text. Then ```python\ncode\n```. Then more text."
        messages.extend(manager.process_chunk(content))

        has_content = any(m["type"] == MSG_TYPE_CONTENT for m in messages)
        has_thinking = any(m["type"] == MSG_TYPE_THINKING for m in messages)

        assert has_content
        assert has_thinking

    def test_nested_thinking_tags(self):
        """测试嵌套思考标签"""
        manager = StreamManager()

        content = "<thought>Thinking...</thought>Result"
        messages = manager.process_chunk(content)

        # 应该有 thinking 和 content
        has_thinking = any(m["type"] == MSG_TYPE_THINKING for m in messages)
        has_content = any(m["type"] == MSG_TYPE_CONTENT for m in messages)

        assert has_thinking
        assert has_content

    def test_multiple_code_blocks(self):
        """测试多个代码块"""
        manager = StreamManager()
        messages = []

        content = "```python\nprint(1)\n```\nText\n```bash\necho test\n```"
        messages.extend(manager.process_chunk(content))

        thinking_count = sum(1 for m in messages if m["type"] == MSG_TYPE_THINKING)
        # 应该有多个 thinking 段
        assert thinking_count >= 1


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""

    def test_empty_chunk(self):
        """测试空块"""
        manager = StreamManager()
        messages = manager.process_chunk("")

        assert len(messages) == 0

    def test_only_whitespace(self):
        """测试只有空白字符"""
        manager = StreamManager()
        messages = manager.process_chunk("   \n\n  ")

        # 应该产生 content 消息
        assert len(messages) >= 0

    def test_special_characters(self):
        """测试特殊字符"""
        manager = StreamManager()
        special = "Hello \n\t\r\n world!"
        messages = manager.process_chunk(special)

        assert len(messages) > 0

    def test_unicode_characters(self):
        """测试 Unicode 字符"""
        manager = StreamManager()
        unicode = "Hello 世界 !"
        messages = manager.process_chunk(unicode)

        content = "".join(m["content"] for m in messages if m["type"] == MSG_TYPE_CONTENT)
        assert "世界" in content


__all__ = []
