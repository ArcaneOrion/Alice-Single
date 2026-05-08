"""
缓存技能加载器

提供带 mtime 验证的技能文件缓存读取功能。
"""

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import Skill
from .directory_loader import DirectorySkillLoader

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    content: str
    mtime: float
    skill: Skill | None = None


class CacheSkillLoader(DirectorySkillLoader):
    """缓存技能加载器

    继承自 DirectorySkillLoader，添加 mtime 缓存功能。

    因为 skills/ 目录是绑定挂载到容器的，宿主机和容器共享同一个物理文件。
    通过 mtime 检测可以确保缓存一致性：
    - 容器修改文件 → mtime 变化 → 下次读取时缓存失效
    - 宿主机修改文件 → mtime 变化 → 缓存失效

    性能提升：100-300ms (docker exec) → <10ms (缓存命中)
    """

    def __init__(self, skills_dirs: str | Path | Sequence[str | Path] = "backend/alice/skills"):
        """初始化缓存加载器

        Args:
            skills_dirs: 技能目录路径，可以是单个路径或路径列表
        """
        super().__init__(skills_dirs)
        self._content_cache: dict[str, CacheEntry] = {}

    def read_skill_file(self, relative_path: str) -> str | None:
        """带 mtime 验证的技能文件缓存读取

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件内容字符串，如果文件不存在返回 None
        """
        # 按 skills_dirs 顺序查找文件，先找到的为准
        for skills_dir in self.skills_dirs:
            full_path = skills_dir / relative_path
            full_path_str = str(full_path)

            if not full_path.exists():
                continue

            # 获取当前文件的修改时间
            try:
                current_mtime = os.path.getmtime(full_path)
            except Exception as e:
                logger.error(f"获取文件 mtime 失败 {full_path}: {e}")
                continue

            # 检查缓存是否有效
            cached = self._content_cache.get(full_path_str)
            if cached and cached.mtime == current_mtime:
                # 缓存命中且 mtime 未变，直接返回
                logger.debug(f"缓存命中: {relative_path}")
                return cached.content

            # 缓存失效或未命中，从磁盘重新加载
            try:
                with open(full_path, encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # 更新缓存
                self._content_cache[full_path_str] = CacheEntry(
                    content=content,
                    mtime=current_mtime
                )
                logger.debug(f"缓存更新: {relative_path}")
                return content
            except Exception as e:
                logger.error(f"读取文件失败 {full_path}: {e}")
                continue

        # 所有目录都未找到
        return None

    def load(self, path: Path) -> Skill | None:
        """加载单个技能（带缓存）"""
        path = Path(path)
        path_str = str(path)

        # 获取当前 mtime
        try:
            current_mtime = os.path.getmtime(path)
        except FileNotFoundError:
            return None

        # 检查缓存
        cached = self._content_cache.get(path_str)
        if cached and cached.mtime == current_mtime and cached.skill:
            logger.debug(f"技能缓存命中: {path}")
            return cached.skill

        # 调用父类加载
        skill = super().load(path)
        if skill:
            # 更新缓存
            if path_str in self._content_cache:
                entry = self._content_cache[path_str]
                entry.mtime = current_mtime
                entry.skill = skill
            else:
                self._content_cache[path_str] = CacheEntry(
                    content=skill.content,
                    mtime=current_mtime,
                    skill=skill
                )

        return skill

    def refresh(self) -> None:
        """刷新技能缓存

        清空内容缓存，重新加载技能注册表。
        """
        self._content_cache.clear()
        super().refresh()

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self._content_cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含缓存统计信息的字典
        """
        return {
            "cache_entries": len(self._content_cache),
            "skills_count": len(self._skills),
            "cache_keys": list(self._content_cache.keys())
        }


__all__ = ["CacheSkillLoader", "CacheEntry"]
