"""流式响应解析器

从 tui_bridge.py 的 StreamManager 提取并重构。
使用缓冲区预判代码块状态，确保 UI 分流精确。
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class StreamMessageType(str, Enum):
    """流消息类型"""

    CONTENT = "content"
    THINKING = "thinking"
    STATUS = "status"
    ERROR = "error"
    TOKENS = "tokens"


@dataclass
class ParsedStreamMessage:
    """解析后的流消息

    Attributes:
        type: 消息类型
        content: 消息内容
    """

    type: StreamMessageType
    content: str

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {"type": self.type.value, "content": self.content}


@dataclass
class StreamParserConfig:
    """流解析器配置

    Attributes:
        max_buffer_size: 最大缓冲区大小（字节）
        window_size: 滑动预判窗口大小（字符）
        markers: 起始和结束标记对
        naked_keywords: 裸关键词列表
    """

    max_buffer_size: int = 10 * 1024 * 1024  # 10MB
    window_size: int = 20
    markers: list[tuple[str, str]] = field(default_factory=lambda: [
        ("```python", "```"),
        ("```bash", "```"),
        ("```", "```"),
        ("<thought>", "</thought>"),
        ("<reasoning>", "</reasoning>"),
        ("<thinking>", "</thinking>"),
        ("", ""),  # 空字符串
        ("<python>", "</python>"),
    ])
    naked_keywords: list[str] = field(default_factory=lambda: [
        "python ",
        "cat ",
        "ls ",
        "grep ",
        "mkdir ",
    ])


class StreamParser:
    """流式响应解析器

    从 LLM 流式响应中解析出正文和思考内容。
    使用滑动窗口机制预判标记边界，避免代码块被错误分割。
    """

    def __init__(self, config: StreamParserConfig | None = None):
        """初始化解析器

        Args:
            config: 解析器配置
        """
        self.config = config or StreamParserConfig()
        self.buffer = ""
        self.in_code_block = False
        self.current_end_tag = "```"
        self.current_start_tag_len = 3
        self._logger = logging.getLogger(__name__)

    def process_chunk(self, chunk_text: str) -> list[ParsedStreamMessage]:
        """处理新到达的文本块

        Args:
            chunk_text: 新的文本内容

        Returns:
            解析后的消息列表
        """
        self.buffer += chunk_text

        # P0 修复: 防止缓冲区无限增长导致 OOM
        if len(self.buffer) > self.config.max_buffer_size:
            self._logger.warning(
                f"StreamParser 缓冲区超限 ({len(self.buffer)} > {self.config.max_buffer_size})，强制冲刷"
            )
            output = self._try_dispatch(is_final=True)
            self.buffer = ""
            self.in_code_block = False
            return output

        return self._try_dispatch()

    def _try_dispatch(self, is_final: bool = False) -> list[ParsedStreamMessage]:
        """尝试分发数据

        Args:
            is_final: 是否为最后一次调用

        Returns:
            解析后的消息列表
        """
        output_msgs: list[ParsedStreamMessage] = []
        just_entered_code_block = False

        while True:
            if not self.buffer:
                break

            if not self.in_code_block:
                # 搜索标记
                start_idx, found_marker = self._find_marker()

                if start_idx == -1:
                    if not is_final:
                        # 智能前缀保留（滑动延迟检测）
                        safe_len = self._calculate_safe_length()
                        if safe_len > 0:
                            output_msgs.append(
                                ParsedStreamMessage(type=StreamMessageType.CONTENT, content=self.buffer[:safe_len])
                            )
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        output_msgs.append(
                            ParsedStreamMessage(type=StreamMessageType.CONTENT, content=self.buffer)
                        )
                        self.buffer = ""
                        break
                else:
                    # 发现起始标记，处理之前的正文
                    if start_idx > 0:
                        output_msgs.append(
                            ParsedStreamMessage(type=StreamMessageType.CONTENT, content=self.buffer[:start_idx])
                        )

                    self.in_code_block = True
                    self.current_end_tag = found_marker[1]
                    self.current_start_tag_len = len(found_marker[0])
                    just_entered_code_block = True
                    self.buffer = self.buffer[start_idx:]
            else:
                # 已经在隔离块中，寻找结束标记
                search_offset = self.current_start_tag_len if just_entered_code_block else 0
                end_idx = self.buffer.find(self.current_end_tag, search_offset)

                if end_idx == -1:
                    if not is_final:
                        # 保留结束标签的前缀
                        hold_back = self._calculate_end_tag_hold_back()
                        safe_len = len(self.buffer) - hold_back
                        if safe_len > 0:
                            output_msgs.append(
                                ParsedStreamMessage(type=StreamMessageType.THINKING, content=self.buffer[:safe_len])
                            )
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        output_msgs.append(
                            ParsedStreamMessage(type=StreamMessageType.THINKING, content=self.buffer)
                        )
                        self.buffer = ""
                        break
                else:
                    # 发现结束标记，闭合思考块
                    thinking_end = end_idx + len(self.current_end_tag)
                    output_msgs.append(
                        ParsedStreamMessage(type=StreamMessageType.THINKING, content=self.buffer[:thinking_end])
                    )
                    self.buffer = self.buffer[thinking_end:]
                    self.in_code_block = False
                    just_entered_code_block = False

        return output_msgs

    def _find_marker(self) -> tuple[int, tuple[str, str] | None]:
        """查找最早的标记

        Returns:
            (起始索引, (起始标签, 结束标签)) 或 (-1, None)
        """
        start_idx = -1
        found_marker = None

        # 1. 优先匹配显式标记
        for start_tag, end_tag in self.config.markers:
            if not start_tag:
                continue
            idx = self.buffer.find(start_tag)
            if idx != -1 and (start_idx == -1 or idx < start_idx):
                start_idx = idx
                found_marker = (start_tag, end_tag)

        # 2. 匹配裸关键词
        for kw in self.config.naked_keywords:
            kw_match = re.search(r"(?:^|\n)" + re.escape(kw), self.buffer)
            if kw_match:
                idx = kw_match.start()
                if start_idx == -1 or idx < start_idx:
                    start_idx = idx
                    found_marker = (kw_match.group(), "\n\n")

        return start_idx, found_marker

    def _calculate_safe_length(self) -> int:
        """计算安全的输出长度（保留前缀以避免截断标记）"""
        hold_back = self.config.window_size

        for start_tag, _ in self.config.markers:
            if not start_tag:
                continue
            for i in range(len(start_tag) - 1, 0, -1):
                if self.buffer.endswith(start_tag[:i]):
                    hold_back = max(hold_back, i)
                    break

        # 额外检查裸关键词的前缀
        for kw in self.config.naked_keywords:
            for i in range(len(kw) - 1, 0, -1):
                if self.buffer.endswith(kw[:i]):
                    hold_back = max(hold_back, i)
                    break

        safe_len = len(self.buffer) - hold_back
        return max(0, safe_len)

    def _calculate_end_tag_hold_back(self) -> int:
        """计算结束标签的保留长度"""
        hold_back = 0
        for i in range(len(self.current_end_tag) - 1, 0, -1):
            if self.buffer.endswith(self.current_end_tag[:i]):
                hold_back = i
                break
        return hold_back

    def flush(self) -> list[ParsedStreamMessage]:
        """强制冲刷所有剩余数据

        Returns:
            解析后的消息列表
        """
        return self._try_dispatch(is_final=True)

    def reset(self) -> None:
        """重置解析器状态"""
        self.buffer = ""
        self.in_code_block = False
        self.current_end_tag = "```"
        self.current_start_tag_len = 3

    @property
    def buffer_size(self) -> int:
        """获取当前缓冲区大小"""
        return len(self.buffer)

    @property
    def is_in_block(self) -> bool:
        """是否在代码/思考块中"""
        return self.in_code_block


__all__ = [
    "StreamParser",
    "StreamParserConfig",
    "StreamMessageType",
    "ParsedStreamMessage",
]
