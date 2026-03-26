"""
Mock Stream 数据

用于测试流式数据处理
"""

from typing import Iterator, Optional

from backend.alice.infrastructure.bridge.stream_manager import MSG_TYPE_THINKING, MSG_TYPE_CONTENT


class MockStreamData:
    """预定义的流式数据场景"""

    @staticmethod
    def simple_text() -> Iterator[str]:
        """简单文本流"""
        yield "Hello"
        yield ", "
        yield "world"
        yield "!"

    @staticmethod
    def with_code_block() -> Iterator[str]:
        """带代码块的流"""
        yield "Here is the code:\n"
        yield "```python"
        yield "\nprint('hello')"
        yield "\n```"
        yield "\nDone!"

    @staticmethod
    def with_xml_thinking() -> Iterator[str]:
        """带 XML 思考标记的流"""
        yield "<thought>"
        yield "I need to think..."
        yield "</thought>"
        yield "The answer is 42."

    @staticmethod
    def with_python_keyword() -> Iterator[str]:
        """带裸 python 关键词的流"""
        yield "Let me run:\n"
        yield "python "
        yield "-c \"print('test')\""
        yield "\nComplete."

    @staticmethod
    def mixed_content() -> Iterator[str]:
        """混合内容流"""
        yield "First, "
        yield "```bash"
        yield "\necho hello"
        yield "\n```"
        yield ", then "
        yield "<thinking>"
        yield "analyze..."
        yield "</thinking>"
        yield ", finally done."

    @staticmethod
    def multi_line_code() -> Iterator[str]:
        """多行代码块"""
        yield "```python\n"
        yield "def hello():\n"
        yield "    print('world')\n"
        yield "\nhello()\n"
        yield "```"

    @staticmethod
    def incomplete_marker() -> Iterator[str]:
        """不完整标记（测试缓冲）"""
        yield "Text before"
        yield " ```p"
        yield "ython"
        yield "\nprint('test')"
        yield "\n```"
        yield " after"

    @staticmethod
    def large_chunk() -> Iterator[str]:
        """大数据块"""
        yield "A" * 1000
        yield "B" * 1000
        yield "C" * 1000


class StreamTestHelper:
    """流测试辅助工具"""

    @staticmethod
    def chunks_to_string(chunks: Iterator[str]) -> str:
        """将块组合成字符串"""
        return "".join(chunks)

    @staticmethod
    def count_messages_by_type(messages: list) -> dict[str, int]:
        """按类型统计消息数量"""
        counts = {MSG_TYPE_CONTENT: 0, MSG_TYPE_THINKING: 0}
        for msg in messages:
            msg_type = msg.get("type", "")
            if msg_type in counts:
                counts[msg_type] += 1
        return counts

    @staticmethod
    def get_content_by_type(messages: list, msg_type: str) -> str:
        """获取指定类型的所有内容"""
        return "".join(m.get("content", "") for m in messages if m.get("type") == msg_type)

    @staticmethod
    def assert_message_sequence(
        messages: list,
        expected_types: list[str],
        exact: bool = True
    ) -> bool:
        """断言消息类型序列"""
        actual_types = [m.get("type") for m in messages]
        if exact:
            return actual_types == expected_types

        # 检查包含关系
        expected_idx = 0
        for actual_type in actual_types:
            if expected_idx < len(expected_types) and actual_type == expected_types[expected_idx]:
                expected_idx += 1
        return expected_idx == len(expected_types)


class MockStreamChunk:
    """单个流块"""

    def __init__(
        self,
        content: str = "",
        is_code: bool = False,
        is_thinking: bool = False
    ):
        self.content = content
        self.is_code = is_code
        self.is_thinking = is_thinking

    def __repr__(self):
        return f"MockStreamChunk(content={self.content[:20]!r}, is_code={self.is_code}, is_thinking={self.is_thinking})"


class StreamScenarioBuilder:
    """流场景构建器"""

    def __init__(self):
        self._chunks: list[str] = []

    def add_text(self, text: str) -> "StreamScenarioBuilder":
        """添加文本"""
        self._chunks.append(text)
        return self

    def add_code_block(self, lang: str = "python", code: str = "print('hello')") -> "StreamScenarioBuilder":
        """添加代码块"""
        self._chunks.append(f"```{lang}\n")
        self._chunks.append(code)
        self._chunks.append("\n```")
        return self

    def add_xml_tag(self, tag: str, content: str = "") -> "StreamScenarioBuilder":
        """添加 XML 标签"""
        self._chunks.append(f"<{tag}>")
        if content:
            self._chunks.append(content)
        self._chunks.append(f"</{tag}>")
        return self

    def add_naked_keyword(self, keyword: str, args: str = "") -> "StreamScenarioBuilder":
        """添加裸关键词"""
        self._chunks.append(f"\n{keyword} {args}\n")
        return self

    def build(self) -> Iterator[str]:
        """构建流迭代器"""
        return iter(self._chunks)

    def build_as_list(self) -> list[str]:
        """构建为列表"""
        return self._chunks


__all__ = [
    "MockStreamData",
    "StreamTestHelper",
    "MockStreamChunk",
    "StreamScenarioBuilder",
]
