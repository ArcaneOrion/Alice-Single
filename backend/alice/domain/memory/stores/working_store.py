"""
Working Memory Store

工作内存实现，管理即时对话背景。
采用 FIFO 淘汰策略，保留最近 N 轮对话。
"""

import os
import re
from datetime import datetime
from typing import Optional

from backend.alice.core.interfaces.memory_store import MemoryEntry, RoundEntry
from backend.alice.domain.memory.stores.base import BaseWorkingMemoryStore
from backend.alice.domain.memory.models.round_entry import RoundEntry as RoundEntryModel
from backend.alice.domain.memory.repository.file_repository import FileRepository


class WorkingMemoryStore(BaseWorkingMemoryStore):
    """工作内存存储

    管理即时对话背景，保留最近的 N 轮对话。
    代码块会被过滤掉以减少存储空间。
    """

    ROUND_SEPARATOR = "--- ROUND ---"
    MAX_ROUNDS_DEFAULT = 30

    def __init__(self, file_path: str, max_rounds: int = MAX_ROUNDS_DEFAULT):
        """初始化工作内存存储

        Args:
            file_path: 工作内存文件路径
            max_rounds: 最大保留轮数
        """
        super().__init__(file_path)
        self.max_rounds = max_rounds
        self.repository = FileRepository(file_path)

    def add_round(self, round_entry: RoundEntry) -> None:
        """添加对话轮次

        Args:
            round_entry: 对话轮次条目
        """
        # 过滤代码块
        filtered_entry = self._filter_code_blocks(round_entry)

        # 读取现有内容
        content = self.repository.read()

        # 解析现有轮次
        rounds = self._parse_rounds(content)

        # 添加新轮次
        rounds.append(filtered_entry)

        # 裁剪到最大轮数
        if len(rounds) > self.max_rounds:
            rounds = rounds[-self.max_rounds:]

        # 写回文件
        self._write_rounds(rounds)

    def get_recent_rounds(self, count: int) -> list[RoundEntry]:
        """获取最近的对话轮次

        Args:
            count: 获取轮数

        Returns:
            对话轮次列表
        """
        content = self.repository.read()
        rounds = self._parse_rounds(content)
        return rounds[-count:] if count < len(rounds) else rounds

    def trim_to_max_rounds(self, max_rounds: int) -> None:
        """裁剪到最大轮数

        Args:
            max_rounds: 最大轮数
        """
        content = self.repository.read()
        rounds = self._parse_rounds(content)

        if len(rounds) > max_rounds:
            self._write_rounds(rounds[-max_rounds:])

    def add(self, entry: MemoryEntry) -> None:
        """添加内存条目（作为单轮对话处理）"""
        round_entry = RoundEntry(
            user_input=entry.content,
            timestamp=entry.timestamp,
        )
        self.add_round(round_entry)

    def get(self, key: str) -> Optional[MemoryEntry]:
        """获取内存条目（按时间戳查找）"""
        content = self.repository.read()
        rounds = self._parse_rounds(content)

        for round_entry in rounds:
            if round_entry.timestamp and round_entry.timestamp.isoformat() == key:
                return MemoryEntry(
                    content=round_entry.user_input,
                    timestamp=round_entry.timestamp,
                    metadata={"type": "round"},
                )
        return None

    def list(self, limit: int = 100) -> list[MemoryEntry]:
        """列出内存条目"""
        content = self.repository.read()
        rounds = self._parse_rounds(content)

        entries = []
        for round_entry in rounds[-limit:]:
            content_text = f"{round_entry.user_input}\n{round_entry.assistant_response}"
            entries.append(
                MemoryEntry(
                    content=content_text.strip(),
                    timestamp=round_entry.timestamp or datetime.now(),
                    metadata={"type": "round"},
                )
            )
        return entries

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索内存条目"""
        all_entries = self.list(limit=1000)
        query_lower = query.lower()

        results = []
        for entry in all_entries:
            if query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def delete(self, key: str) -> bool:
        """删除指定轮次（按时间戳）"""
        content = self.repository.read()
        rounds = self._parse_rounds(content)

        filtered_rounds = [
            r for r in rounds
            if not (r.timestamp and r.timestamp.isoformat() == key)
        ]

        if len(filtered_rounds) == len(rounds):
            return False

        self._write_rounds(filtered_rounds)
        return True

    def clear(self) -> None:
        """清空所有条目"""
        self.repository.write("# Alice 的即时对话背景 (Working Memory)\n\n")

    def get_content_text(self) -> str:
        """获取工作内存的文本内容（用于注入到 LLM）"""
        content = self.repository.read()
        if not content.strip():
            return "暂无即时对话背景。"
        return content

    def _filter_code_blocks(self, round_entry: RoundEntry) -> RoundEntry:
        """过滤代码块

        Args:
            round_entry: 原始对话轮次

        Returns:
            过滤后的对话轮次
        """
        return RoundEntry(
            user_input=self._remove_code_blocks(round_entry.user_input),
            assistant_thinking=self._remove_code_blocks(round_entry.assistant_thinking),
            assistant_response=self._remove_code_blocks(round_entry.assistant_response),
            timestamp=round_entry.timestamp,
        )

    @staticmethod
    def _remove_code_blocks(text: str) -> str:
        """移除文本中的代码块"""
        if not text:
            return ""
        return re.sub(r'```[\s\S]*?```', '', text).strip()

    def _parse_rounds(self, content: str) -> list[RoundEntry]:
        """解析文件内容为轮次列表"""
        if not content.strip():
            return []

        parts = re.split(r'^--- ROUND ---\n', content, flags=re.MULTILINE)
        rounds = []

        for part in parts:
            part = part.strip()
            if part:
                rounds.append(RoundEntryModel.from_markdown(part))

        return rounds

    def _write_rounds(self, rounds: list[RoundEntry]) -> None:
        """将轮次列表写入文件"""
        lines = ["# Alice 的即时对话背景 (Working Memory)\n\n"]

        for round_entry in rounds:
            lines.append(RoundEntryModel.to_markdown(round_entry))
            lines.append("")

        self.repository.write("\n".join(lines))


__all__ = ["WorkingMemoryStore"]
