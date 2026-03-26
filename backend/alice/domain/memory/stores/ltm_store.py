"""
Long-Term Memory Store

长期记忆实现，永久存储经验教训和用户偏好。
"""

import re
from datetime import datetime
from typing import Optional

from backend.alice.core.interfaces.memory_store import MemoryEntry
from backend.alice.domain.memory.stores.base import BaseMemoryStore
from backend.alice.domain.memory.repository.file_repository import FileRepository


class LTMStore(BaseMemoryStore):
    """长期记忆存储

    永久存储经验教训、用户偏好等重要信息。
    内容按类别组织，支持经验教训自动提炼。
    """

    LESSONS_HEADER = "## 经验教训"
    DATE_PATTERN = re.compile(r'\[(\d{4}-\d{2}-\d{2})\]')

    def __init__(self, file_path: str):
        """初始化长期记忆存储

        Args:
            file_path: 长期记忆文件路径
        """
        super().__init__(file_path)
        self.repository = FileRepository(file_path)

    def add(self, entry: MemoryEntry) -> None:
        """添加内存条目

        默认添加到"经验教训"小节。

        Args:
            entry: 内存条目
        """
        self.add_to_lessons(entry.content, entry.timestamp)

    def add_to_lessons(self, content: str, timestamp: Optional[datetime] = None) -> None:
        """添加到经验教训小节

        Args:
            content: 内容
            timestamp: 时间戳
        """
        timestamp = timestamp or datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")

        full_text = self.repository.read()
        entry = f"- [{date_str}] {content}\n"

        if self.LESSONS_HEADER in full_text:
            # 插入到经验教训标题下方
            parts = full_text.split(self.LESSONS_HEADER)
            new_content = parts[0] + self.LESSONS_HEADER + "\n" + entry + parts[1].lstrip()
            self.repository.write(new_content)
        else:
            # 追加到文件末尾
            self.repository.append(f"\n{self.LESSONS_HEADER}\n{entry}")

    def add_distilled_memory(self, summary: str, timestamp: Optional[datetime] = None) -> None:
        """添加自动提炼的记忆

        Args:
            summary: 提炼的摘要内容
            timestamp: 时间戳
        """
        timestamp = timestamp or datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")

        distilled_entry = f"\n\n### 自动提炼记忆 ({date_str})\n{summary}\n"
        self.repository.append(distilled_entry)

    def get(self, key: str) -> Optional[MemoryEntry]:
        """获取内存条目

        Args:
            key: 查询键

        Returns:
            内存条目或 None
        """
        content = self.repository.read()

        # 尝试按经验教训标题查找
        if key == "lessons":
            lessons = self._extract_lessons(content)
            return MemoryEntry(
                content=lessons,
                timestamp=datetime.now(),
                metadata={"type": "lessons"},
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
        entries = []

        # 解析各个小节
        sections = re.split(r'^## ', content, flags=re.MULTILINE)

        for section in sections[:limit]:
            if section.strip():
                lines = section.strip().split("\n")
                title = lines[0] if lines else "未分类"
                body = "\n".join(lines[1:]) if len(lines) > 1 else ""

                entries.append(
                    MemoryEntry(
                        content=body,
                        timestamp=datetime.now(),
                        metadata={"type": "section", "title": title},
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
        query_lower = query.lower()

        # 按行搜索
        matching_lines = []
        for line in content.split("\n"):
            if query_lower in line.lower():
                matching_lines.append(line.strip())

                if len(matching_lines) >= limit:
                    break

        results = []
        for line in matching_lines:
            # 尝试提取日期
            date_match = self.DATE_PATTERN.search(line)
            timestamp = (
                datetime.strptime(date_match.group(1), "%Y-%m-%d")
                if date_match else datetime.now()
            )

            results.append(
                MemoryEntry(
                    content=line,
                    timestamp=timestamp,
                )
            )

        return results

    def delete(self, key: str) -> bool:
        """删除指定条目

        Args:
            key: 要删除的内容或标识

        Returns:
            是否删除成功
        """
        content = self.repository.read()

        # 按行查找并删除
        lines = content.split("\n")
        new_lines = []

        for line in lines:
            if key not in line:
                new_lines.append(line)

        if len(new_lines) == len(lines):
            return False

        self.repository.write("\n".join(new_lines))
        return True

    def clear(self) -> None:
        """清空所有条目"""
        self.repository.write("# Alice 的长期记忆\n")

    def get_content_text(self) -> str:
        """获取长期记忆的文本内容（用于注入到 LLM）"""
        content = self.repository.read()
        if not content.strip():
            return "暂无长期记忆。"
        return content

    def get_lessons(self) -> str:
        """获取经验教训内容

        Returns:
            经验教训文本
        """
        content = self.repository.read()
        return self._extract_lessons(content)

    @staticmethod
    def _extract_lessons(content: str) -> str:
        """提取经验教训小节内容

        Args:
            content: 完整文件内容

        Returns:
            经验教训内容
        """
        if self.LESSONS_HEADER not in content:
            return ""

        parts = content.split(self.LESSONS_HEADER)
        if len(parts) < 2:
            return ""

        # 提取经验教训小节（直到下一个 ## 标题）
        lessons_section = parts[1]
        next_header = re.search(r'\n## ', lessons_section)

        if next_header:
            return lessons_section[:next_header.start()].strip()

        return lessons_section.strip()


__all__ = ["LTMStore"]
