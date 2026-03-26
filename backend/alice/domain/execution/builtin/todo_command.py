"""
Todo 命令处理器

处理内置 todo 指令，在宿主机更新任务清单文件
"""

import logging
import os

logger = logging.getLogger(__name__)


class TodoCommandHandler:
    """Todo 命令处理器

    处理 todo 指令，管理任务清单文件
    """

    def __init__(self):
        pass

    def handle_write(self, content: str, target_path: str) -> str:
        """处理 todo 写入操作

        Args:
            content: 要写入的任务清单内容
            target_path: 目标文件路径

        Returns:
            str: 操作结果消息
        """
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content.strip())

            logger.info(f"已更新任务清单文件: {target_path}")
            return "已成功更新宿主机任务清单 (memory/todo.md)。"

        except Exception as e:
            logger.error(f"更新任务清单失败: {e}")
            return f"更新任务清单失败: {str(e)}"

    def handle_read(self, target_path: str) -> str:
        """处理 todo 读取操作

        Args:
            target_path: 目标文件路径

        Returns:
            str: 文件内容
        """
        try:
            if os.path.exists(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    return f.read()
            return "任务清单文件不存在。"
        except Exception as e:
            logger.error(f"读取任务清单失败: {e}")
            return f"读取任务清单失败: {str(e)}"

    def handle_append(self, item: str, target_path: str) -> str:
        """处理 todo 追加操作

        Args:
            item: 要追加的任务项
            target_path: 目标文件路径

        Returns:
            str: 操作结果消息
        """
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # 读取现有内容
            existing_content = ""
            if os.path.exists(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            # 追加新任务
            with open(target_path, "w", encoding="utf-8") as f:
                if existing_content:
                    f.write(existing_content.rstrip() + "\n")
                f.write(f"- [ ] {item}\n")

            logger.info(f"已追加任务到任务清单: {item}")
            return f"已添加任务: {item}"

        except Exception as e:
            logger.error(f"追加任务失败: {e}")
            return f"追加任务失败: {str(e)}"


__all__ = [
    "TodoCommandHandler",
]
