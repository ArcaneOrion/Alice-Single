"""
Stream Manager

流式数据管理器，使用滑动窗口预判代码块状态，确保 UI 分流精确。
从 tui_bridge.py 的 StreamManager 重构而来。
"""

import logging
import re
from typing import Optional

from .protocol.messages import OutputMessage

logger = logging.getLogger(__name__)


# 标记定义：代码块/思考区域的起始和结束标记
MARKER_PAIRS = [
    ("```python", "```"),
    ("```bash", "```"),
    ("```", "```"),
    ("<thought>", "</thought>"),
    ("<reasoning>", "</reasoning>"),
    ("<thinking>", "</thinking>"),
    ("</think>", "</think>"),
    ("<python>", "</python>"),
]

# 裸关键词：行首或空白后的关键词，表示代码/命令
NAKED_KEYWORDS = ["python ", "cat ", "ls ", "grep ", "mkdir "]

# 消息类型常量
MSG_TYPE_THINKING = "thinking"
MSG_TYPE_CONTENT = "content"


class StreamManager:
    """
    流式数据管理器。

    使用滑动窗口机制预判代码块状态，确保 UI 分流精确。

    特性：
    - 智能识别代码块标记
    - 滑动窗口延迟检测
    - 防止缓冲区溢出
    - 支持多种标记格式
    """

    def __init__(
        self,
        max_buffer_size: int = 10 * 1024 * 1024,
        window_size: int = 20,
    ):
        """
        初始化流管理器。

        Args:
            max_buffer_size: 最大缓冲区大小（默认 10MB）
            window_size: 滑动预判窗口大小（字符数）
        """
        self.buffer = ""
        self.in_code_block = False
        self.current_end_tag = "```"
        self.current_start_tag_len = 3
        self.max_buffer_size = max_buffer_size
        self.window_size = window_size

    def process_chunk(self, chunk_text: str) -> list[OutputMessage]:
        """
        处理新到达的文本块。

        Args:
            chunk_text: 新的文本块

        Returns:
            list[OutputMessage]: 待发送的消息列表
        """
        self.buffer += chunk_text

        # P0 修复: 防止缓冲区无限增长导致 OOM
        if len(self.buffer) > self.max_buffer_size:
            logger.warning(
                f"StreamManager 缓冲区超限 "
                f"({len(self.buffer)} > {self.max_buffer_size})，"
                f"强制冲刷"
            )
            output = self._try_dispatch(is_final=True)
            self.buffer = ""
            self.in_code_block = False
            return output

        return self._try_dispatch()

    def _try_dispatch(self, is_final: bool = False) -> list[OutputMessage]:
        """
        尝试分发数据。

        如果非最后一次，则保留窗口余量以供预判。

        Args:
            is_final: 是否为最后一次处理

        Returns:
            list[OutputMessage]: 待发送的消息列表
        """
        output_msgs: list[OutputMessage] = []
        just_entered_code_block = False

        while True:
            if not self.buffer:
                break

            if not self.in_code_block:
                # 非代码块状态：查找起始标记
                start_idx, found_marker = self._find_start_marker()

                if start_idx == -1:
                    # 未找到标记
                    if not is_final:
                        # 智能前缀保留（滑动延迟检测）
                        hold_back = self._calculate_hold_back()

                        safe_len = len(self.buffer) - hold_back
                        if safe_len > 0:
                            output_msgs.append({
                                "type": MSG_TYPE_CONTENT,
                                "content": self.buffer[:safe_len]
                            })
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        # 最后一次，全部输出
                        output_msgs.append({
                            "type": MSG_TYPE_CONTENT,
                            "content": self.buffer
                        })
                        self.buffer = ""
                        break
                else:
                    # 发现起始标记
                    if start_idx > 0:
                        output_msgs.append({
                            "type": MSG_TYPE_CONTENT,
                            "content": self.buffer[:start_idx]
                        })

                    self.in_code_block = True
                    self.current_end_tag = found_marker[1]
                    self.current_start_tag_len = len(found_marker[0])
                    just_entered_code_block = True
                    self.buffer = self.buffer[start_idx:]
            else:
                # 代码块状态：查找结束标记
                search_offset = self.current_start_tag_len if just_entered_code_block else 0
                end_idx = self.buffer.find(self.current_end_tag, search_offset)

                if end_idx == -1:
                    # 未找到结束标记
                    if not is_final:
                        # 保留结束标签的前缀
                        hold_back = self._calculate_end_tag_hold_back()

                        safe_len = len(self.buffer) - hold_back
                        if safe_len > 0:
                            output_msgs.append({
                                "type": MSG_TYPE_THINKING,
                                "content": self.buffer[:safe_len]
                            })
                            self.buffer = self.buffer[safe_len:]
                        break
                    else:
                        # 最后一次，全部输出
                        output_msgs.append({
                            "type": MSG_TYPE_THINKING,
                            "content": self.buffer
                        })
                        self.buffer = ""
                        break
                else:
                    # 发现结束标记
                    thinking_end = end_idx + len(self.current_end_tag)
                    output_msgs.append({
                        "type": MSG_TYPE_THINKING,
                        "content": self.buffer[:thinking_end]
                    })
                    self.buffer = self.buffer[thinking_end:]
                    self.in_code_block = False
                    just_entered_code_block = False

        return output_msgs

    def _find_start_marker(self) -> tuple[int, Optional[tuple[str, str]]]:
        """
        查找起始标记。

        Returns:
            tuple[int, Optional[tuple[str, str]]]: (位置, (起始标记, 结束标记))
        """
        start_idx = -1
        found_marker = None

        # 1. 优先匹配显式标记
        for start_tag, end_tag in MARKER_PAIRS:
            idx = self.buffer.find(start_tag)
            if idx != -1 and (start_idx == -1 or idx < start_idx):
                start_idx = idx
                found_marker = (start_tag, end_tag)

        # 2. 匹配裸关键词
        for kw in NAKED_KEYWORDS:
            # 使用正则检测行首或特定位置的关键词
            kw_match = re.search(r'(?:^|\n)' + re.escape(kw), self.buffer)
            if kw_match:
                idx = kw_match.start()
                if start_idx == -1 or idx < start_idx:
                    start_idx = idx
                    # 裸关键词使用双换行作为结束
                    found_marker = (kw_match.group(), "\n\n")

        return start_idx, found_marker

    def _calculate_hold_back(self) -> int:
        """
        计算智能前缀保留长度。

        Returns:
            int: 需要保留的字符数
        """
        hold_back = self.window_size

        # 检查所有起始标记的前缀
        for start_tag, _ in MARKER_PAIRS:
            for i in range(len(start_tag) - 1, 0, -1):
                if self.buffer.endswith(start_tag[:i]):
                    hold_back = max(hold_back, i)
                    break

        # 检查裸关键词的前缀
        for kw in NAKED_KEYWORDS:
            for i in range(len(kw) - 1, 0, -1):
                if self.buffer.endswith(kw[:i]):
                    hold_back = max(hold_back, i)
                    break

        return hold_back

    def _calculate_end_tag_hold_back(self) -> int:
        """
        计算结束标签的前缀保留长度。

        Returns:
            int: 需要保留的字符数
        """
        hold_back = 0
        for i in range(len(self.current_end_tag) - 1, 0, -1):
            if self.buffer.endswith(self.current_end_tag[:i]):
                hold_back = i
                break
        return hold_back

    def flush(self) -> list[OutputMessage]:
        """
        强制冲刷所有剩余数据。

        Returns:
            list[OutputMessage]: 待发送的消息列表
        """
        return self._try_dispatch(is_final=True)

    def reset(self) -> None:
        """重置管理器状态。"""
        self.buffer = ""
        self.in_code_block = False
        self.current_end_tag = "```"
        self.current_start_tag_len = 3


__all__ = [
    "StreamManager",
    "MSG_TYPE_THINKING",
    "MSG_TYPE_CONTENT",
]
