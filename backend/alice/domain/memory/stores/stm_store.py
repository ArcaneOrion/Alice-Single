"""
Short-Term Memory Store

短期记忆实现，7天滚动存储。
超过7天的记忆会被自动提炼到长期记忆。
"""

import re
from datetime import datetime, timedelta, date
from typing import Optional

from backend.alice.core.interfaces.memory_store import MemoryEntry
from backend.alice.domain.memory.stores.base import BaseMemoryStore
from backend.alice.domain.memory.repository.file_repository import FileRepository


class STMStore(BaseMemoryStore):
    """短期记忆存储

    按日期分节存储记忆，默认保留7天。
    超过7天的记忆可以被提炼到长期记忆。
    """

    DEFAULT_DAYS_TO_KEEP = 7
    DATE_HEADER_PATTERN = re.compile(r'^## (\d{4}-\d{2}-\d{2})')

    def __init__(self, file_path: str, days_to_keep: int = DEFAULT_DAYS_TO_KEEP):
        """初始化短期记忆存储

        Args:
            file_path: 短期记忆文件路径
            days_to_keep: 保留天数
        """
        super().__init__(file_path)
        self.days_to_keep = days_to_keep
        self.repository = FileRepository(file_path)

    def add(self, entry: MemoryEntry) -> None:
        """添加内存条目

        自动添加到当前日期的小节。

        Args:
            entry: 内存条目
        """
        content = self.repository.read()
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        time_str = entry.timestamp.strftime("%H:%M")

        # 检查是否存在日期小节
        has_date_header = f"## {date_str}" in content

        # 构建新条目
        new_entry = f"\n## {date_str}\n" if not has_date_header else ""
        new_entry += f"- [{time_str}] {entry.content}\n"

        self.repository.append(new_entry)

    def get(self, key: str) -> Optional[MemoryEntry]:
        """获取内存条目

        Args:
            key: 格式为 "YYYY-MM-DD:HH:MM:content_hash" 或仅 "YYYY-MM-DD"

        Returns:
            内存条目或 None
        """
        content = self.repository.read()
        sections = self._parse_sections(content)

        if ":" in key:
            # 尝试解析完整键
            parts = key.split(":")
            if len(parts) >= 2:
                date_key = parts[0]
                section = sections.get(date_key)
                if section:
                    for line in section:
                        if f"[{parts[1]}]" in line:
                            return MemoryEntry(
                                content=line.strip(),
                                timestamp=datetime.fromisoformat(f"{date_key} {parts[1]}"),
                            )

        # 按日期查找
        section = sections.get(key)
        if section:
            combined = "\n".join(section)
            return MemoryEntry(
                content=combined,
                timestamp=datetime.strptime(key, "%Y-%m-%d"),
                metadata={"type": "date_section"},
            )

        return None

    def list(self, limit: int = 100) -> list[MemoryEntry]:
        """列出内存条目

        Args:
            limit: 最大返回数量

        Returns:
            内存条目列表
        """
        content = self.repository.read()
        sections = self._parse_sections(content)

        entries = []
        for date_str, lines in sorted(sections.items())[-limit:]:
            combined = "\n".join(lines)
            entries.append(
                MemoryEntry(
                    content=combined,
                    timestamp=datetime.strptime(date_str, "%Y-%m-%d"),
                    metadata={"type": "date_section", "date": date_str},
                )
            )

        return entries

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索内存条目

        Args:
            query: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的内存条目列表
        """
        content = self.repository.read()
        sections = self._parse_sections(content)

        query_lower = query.lower()
        results = []

        for date_str, lines in sorted(sections.items(), reverse=True):
            for line in lines:
                if query_lower in line.lower():
                    # 提取时间戳
                    time_match = re.search(r'\[(\d{2}:\d{2})\]', line)
                    timestamp = datetime.strptime(
                        f"{date_str} {time_match.group(1)}", "%Y-%m-%d %H:%M"
                    ) if time_match else datetime.strptime(date_str, "%Y-%m-%d")

                    results.append(
                        MemoryEntry(
                            content=line.strip(),
                            timestamp=timestamp,
                        )
                    )

                    if len(results) >= limit:
                        return results

        return results

    def delete(self, key: str) -> bool:
        """删除指定日期的内存

        Args:
            key: 日期字符串 (YYYY-MM-DD)

        Returns:
            是否删除成功
        """
        content = self.repository.read()
        sections = self._parse_sections(content)

        if key not in sections:
            return False

        # 重建内容，排除指定日期
        lines = content.split("\n")
        new_lines = []
        skip_until_next = False

        for line in lines:
            if self.DATE_HEADER_PATTERN.match(line):
                date_match = self.DATE_HEADER_PATTERN.match(line).group(1)
                if date_match == key:
                    skip_until_next = True
                    continue
                else:
                    skip_until_next = False

            if not skip_until_next:
                new_lines.append(line)

        self.repository.write("\n".join(new_lines))
        return True

    def clear(self) -> None:
        """清空所有条目"""
        self.repository.write("# Alice 的短期记忆 (最近 7 天)\n\n")

    def get_expired_sections(self, days: Optional[int] = None) -> dict[str, list[str]]:
        """获取过期的日期小节

        Args:
            days: 过期天数，默认使用初始化时的 days_to_keep

        Returns:
            过期日期小节字典 {date: [lines]}
        """
        days = days or self.days_to_keep
        content = self.repository.read()
        sections = self._parse_sections(content)

        today = date.today()
        expiry_limit = today - timedelta(days=days)

        expired = {}
        for date_str, lines in sections.items():
            section_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if section_date < expiry_limit:
                expired[date_str] = lines

        return expired

    def remove_sections(self, dates: list[str]) -> None:
        """移除指定日期的小节

        Args:
            dates: 要移除的日期列表
        """
        content = self.repository.read()
        sections = self._parse_sections(content)

        lines = content.split("\n")
        new_lines = []
        skip_until_next = False

        for line in lines:
            if self.DATE_HEADER_PATTERN.match(line):
                date_match = self.DATE_HEADER_PATTERN.match(line).group(1)
                if date_match in dates:
                    skip_until_next = True
                    continue
                else:
                    skip_until_next = False

            if not skip_until_next:
                new_lines.append(line)

        self.repository.write("\n".join(new_lines))

    def get_content_text(self) -> str:
        """获取短期记忆的文本内容（用于注入到 LLM）"""
        content = self.repository.read()
        if not content.strip():
            return "暂无近期记忆。"
        return content

    def _parse_sections(self, content: str) -> dict[str, list[str]]:
        """解析内容为日期小节

        Args:
            content: 文件内容

        Returns:
            日期小节字典 {date: [lines]}
        """
        sections = {}
        current_date = None

        for line in content.split("\n"):
            match = self.DATE_HEADER_PATTERN.match(line)
            if match:
                current_date = match.group(1)
                sections[current_date] = [line]
            elif current_date:
                sections[current_date].append(line)

        return sections


__all__ = ["STMStore"]
