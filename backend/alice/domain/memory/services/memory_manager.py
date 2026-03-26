"""
Memory Manager

内存管理器，协调各层内存的存储和检索。
提供统一的内存管理接口。
"""

from datetime import datetime
from typing import Optional

from backend.alice.domain.memory.stores.working_store import WorkingMemoryStore
from backend.alice.domain.memory.stores.stm_store import STMStore
from backend.alice.domain.memory.stores.ltm_store import LTMStore
from backend.alice.domain.memory.services.distiller import Distiller
from backend.alice.core.interfaces.memory_store import MemoryEntry, RoundEntry
from backend.alice.domain.llm.services.client_provider import ClientProvider


class MemoryManager:
    """内存管理器

    协调工作内存、短期记忆和长期记忆的存储和检索。
    处理内存滚动、提炼等管理任务。
    """

    def __init__(
        self,
        working_memory_path: str,
        stm_path: str,
        ltm_path: str,
        llm_provider: Optional[ClientProvider] = None,
        max_working_rounds: int = 30,
        stm_days_to_keep: int = 7,
    ):
        """初始化内存管理器

        Args:
            working_memory_path: 工作内存文件路径
            stm_path: 短期记忆文件路径
            ltm_path: 长期记忆文件路径
            llm_provider: LLM 提供者（用于提炼）
            max_working_rounds: 工作内存最大轮数
            stm_days_to_keep: 短期记忆保留天数
        """
        self.working_store = WorkingMemoryStore(
            file_path=working_memory_path,
            max_rounds=max_working_rounds,
        )
        self.stm_store = STMStore(
            file_path=stm_path,
            days_to_keep=stm_days_to_keep,
        )
        self.ltm_store = LTMStore(file_path=ltm_path)

        self.llm_provider = llm_provider
        self.distiller = Distiller(llm_provider) if llm_provider else None

    def add_working_round(self, round_entry: RoundEntry) -> None:
        """添加工作内存对话轮次

        Args:
            round_entry: 对话轮次
        """
        self.working_store.add_round(round_entry)

    def add_stm_entry(self, content: str, timestamp: Optional[datetime] = None) -> None:
        """添加短期记忆条目

        Args:
            content: 内容
            timestamp: 时间戳
        """
        timestamp = timestamp or datetime.now()
        entry = MemoryEntry(content=content, timestamp=timestamp)
        self.stm_store.add(entry)

    def add_ltm_entry(self, content: str, timestamp: Optional[datetime] = None) -> None:
        """添加长期记忆条目

        Args:
            content: 内容
            timestamp: 时间戳
        """
        timestamp = timestamp or datetime.now()
        self.ltm_store.add_to_lessons(content, timestamp)

    def get_working_content(self) -> str:
        """获取工作内存文本内容

        Returns:
            工作内存文本
        """
        return self.working_store.get_content_text()

    def get_stm_content(self) -> str:
        """获取短期记忆文本内容

        Returns:
            短期记忆文本
        """
        return self.stm_store.get_content_text()

    def get_ltm_content(self) -> str:
        """获取长期记忆文本内容

        Returns:
            长期记忆文本
        """
        return self.ltm_store.get_content_text()

    def get_recent_rounds(self, count: int) -> list[RoundEntry]:
        """获取最近的对话轮次

        Args:
            count: 获取数量

        Returns:
            对话轮次列表
        """
        return self.working_store.get_recent_rounds(count)

    def search_stm(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索短期记忆

        Args:
            query: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的记忆条目
        """
        return self.stm_store.search(query, limit)

    def search_ltm(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """搜索长期记忆

        Args:
            query: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的记忆条目
        """
        return self.ltm_store.search(query, limit)

    def manage_memory(self) -> dict[str, any]:
        """管理短期记忆滚动和长期记忆提炼

        检查过期记忆并调用提炼服务。

        Returns:
            操作结果字典
        """
        if not self.distiller:
            return {"status": "skipped", "reason": "no distiller available"}

        expired_sections = self.stm_store.get_expired_sections()

        if not expired_sections:
            return {"status": "ok", "message": "no expired sections"}

        # 构建过期内容
        pruned_content = ""
        for date_str, lines in expired_sections.items():
            pruned_content += f"\n## {date_str}\n"
            pruned_content += "\n".join(lines) + "\n"

        # 调用提炼服务
        result = self.distiller.distill_stm(pruned_content)

        if result["success"] and result["summary"] and "无重要更新" not in result["summary"]:
            # 写入长期记忆
            self.ltm_store.add_distilled_memory(result["summary"])
            result["ltm_updated"] = True

        # 移除过期短期记忆
        self.stm_store.remove_sections(list(expired_sections.keys()))
        result["stm_cleaned"] = True

        return result

    def trim_working_memory(self, max_rounds: Optional[int] = None) -> None:
        """裁剪工作内存

        Args:
            max_rounds: 最大轮数，默认使用初始化时的值
        """
        if max_rounds is None:
            max_rounds = self.working_store.max_rounds
        self.working_store.trim_to_max_rounds(max_rounds)

    def clear_working_memory(self) -> None:
        """清空工作内存"""
        self.working_store.clear()

    def clear_stm(self) -> None:
        """清空短期记忆"""
        self.stm_store.clear()

    def clear_ltm(self) -> None:
        """清空长期记忆"""
        self.ltm_store.clear()

    def get_memory_summary(self) -> dict[str, any]:
        """获取内存摘要信息

        Returns:
            内存摘要字典
        """
        return {
            "working_memory_rounds": len(self.working_store.get_recent_rounds(1000)),
            "stm_sections": len(self.stm_store.list(1000)),
            "ltm_entries": len(self.ltm_store.list(1000)),
        }


__all__ = ["MemoryManager"]
