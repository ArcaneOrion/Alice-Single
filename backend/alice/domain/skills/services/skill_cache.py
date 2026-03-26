"""
技能缓存服务

提供技能文件内容的缓存管理功能。
"""

import logging
from pathlib import Path
from typing import Any

from ..loaders import CacheSkillLoader

logger = logging.getLogger(__name__)


class SkillCache:
    """技能缓存管理器

    封装 CacheSkillLoader 的缓存功能，
    提供简洁的缓存操作接口。
    """

    def __init__(self, loader: CacheSkillLoader | None = None):
        """初始化缓存管理器

        Args:
            loader: 技能加载器实例，如果为 None 则创建默认实例
        """
        self.loader = loader or CacheSkillLoader()

    def read_skill_file(self, relative_path: str) -> str | None:
        """读取技能文件内容（带缓存）

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件内容字符串，如果文件不存在返回 None
        """
        return self.loader.read_skill_file(relative_path)

    def read_skill_markdown(self, skill_name: str) -> str | None:
        """读取技能的 SKILL.md 内容

        Args:
            skill_name: 技能名称

        Returns:
            SKILL.md 内容，如果不存在返回 None
        """
        return self.read_skill_file(f"{skill_name}/SKILL.md")

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self.loader.clear_cache()
        logger.info("技能缓存已清空")

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含缓存统计信息的字典
        """
        return self.loader.get_cache_stats()

    def is_cached(self, relative_path: str) -> bool:
        """检查文件是否已缓存

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            如果文件已缓存返回 True
        """
        stats = self.get_cache_stats()
        full_path = str(self.loader.skills_dir / relative_path)
        return full_path in stats.get("cache_keys", [])


__all__ = ["SkillCache"]
