"""
Memory 命令处理器

处理内置 memory 指令，在宿主机更新记忆文件
"""

import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryCommandHandler:
    """Memory 命令处理器

    处理 memory 指令，支持短期记忆(STM)和长期记忆(LTM)的写入
    """

    def __init__(self):
        self.date_format = "%Y-%m-%d"
        self.time_format = "%H:%M"

    def handle_write(self, content: str, target_path: str, target: str = "stm") -> str:
        """处理 memory 写入操作

        Args:
            content: 要写入的记忆内容
            target_path: 目标文件路径
            target: 目标类型 ("stm" 或 "ltm")

        Returns:
            str: 操作结果消息
        """
        now = datetime.now()
        date_str = now.strftime(self.date_format)
        time_str = now.strftime(self.time_format)

        # 确保目录存在
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # 清洗内容，避免重复的日期前缀
        clean_content = content.strip()
        if re.match(r'^\[?\d{4}-\d{2}-\d{2}\]?', clean_content):
            entry_prefix = ""
        else:
            entry_prefix = f"[{date_str}] "

        try:
            if target == "stm":
                return self._write_to_stm(target_path, date_str, time_str, clean_content, entry_prefix)
            else:
                return self._write_to_ltm(target_path, date_str, clean_content, entry_prefix)

        except Exception as e:
            logger.error(f"写入记忆失败: {e}")
            return f"更新记忆失败: {str(e)}"

    def _write_to_stm(
        self,
        target_path: str,
        date_str: str,
        time_str: str,
        clean_content: str,
        entry_prefix: str
    ) -> str:
        """写入短期记忆"""
        # 确保文件存在
        if not os.path.exists(target_path):
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("# Alice 的短期记忆 (最近 7 天)\n\n")

        # 检查是否已有日期标题
        with open(target_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        has_date_header = any(line.strip() == f"## {date_str}" for line in lines)

        # 追加内容
        with open(target_path, "a", encoding="utf-8") as f:
            if not has_date_header:
                f.write(f"\n## {date_str}\n")
            f.write(f"- [{time_str}] {entry_prefix}{clean_content}\n")

        return "已成功更新短期记忆。"

    def _write_to_ltm(
        self,
        target_path: str,
        date_str: str,
        clean_content: str,
        entry_prefix: str
    ) -> str:
        """写入长期记忆（经验教训部分）"""
        # 确保文件存在
        if not os.path.exists(target_path):
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("# Alice 的长期记忆\n")

        with open(target_path, "r", encoding="utf-8") as f:
            full_text = f.read()

        lessons_header = "## 经验教训"
        entry = f"- {entry_prefix}{clean_content}\n"

        if lessons_header in full_text:
            # 插入到标题下方
            parts = full_text.split(lessons_header)
            new_content = parts[0] + lessons_header + "\n" + entry + parts[1].lstrip()
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        else:
            # 追加新标题和内容
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(f"\n{lessons_header}\n{entry}")

        return "已成功更新长期记忆经验教训。"

    def handle_read(self, target_path: str) -> str:
        """处理 memory 读取操作

        Args:
            target_path: 目标文件路径

        Returns:
            str: 文件内容
        """
        try:
            if os.path.exists(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    return f.read()
            return "记忆文件不存在。"
        except Exception as e:
            logger.error(f"读取记忆失败: {e}")
            return f"读取记忆失败: {str(e)}"


__all__ = [
    "MemoryCommandHandler",
]
