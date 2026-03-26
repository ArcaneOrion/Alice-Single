"""
目录技能加载器

从目录中扫描并加载技能。
"""

import os
import logging
from pathlib import Path
from typing import Any

from .base import BaseSkillLoader
from ..models import Skill, SkillMetadata

logger = logging.getLogger(__name__)


class DirectorySkillLoader(BaseSkillLoader):
    """目录技能加载器

    扫描指定目录，发现所有包含 SKILL.md 的子目录，
    并将其注册为技能。
    """

    def __init__(self, skills_dir: str | Path = "skills"):
        """初始化加载器

        Args:
            skills_dir: 技能目录路径
        """
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}

    def load(self, path: Path) -> Skill | None:
        """加载单个技能

        Args:
            path: SKILL.md 文件路径或技能目录路径

        Returns:
            Skill 实例，如果加载失败返回 None
        """
        path = Path(path)

        # 如果是目录，查找 SKILL.md
        if path.is_dir():
            skill_md = path / "SKILL.md"
        else:
            skill_md = path

        if not skill_md.exists():
            logger.warning(f"技能文件不存在: {skill_md}")
            return None

        try:
            with open(skill_md, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"读取技能文件失败 {skill_md}: {e}")
            return None

        # 解析 YAML frontmatter
        yaml_content, markdown_content = self._parse_skill_markdown(content)

        # 提取技能名称（使用目录名）
        skill_name = skill_md.parent.name

        # 解析元数据
        yaml_dict = self._parse_yaml_dict(yaml_content)
        metadata = SkillMetadata.from_yaml_dict(yaml_dict, skill_name)

        # 创建技能对象
        skill = Skill(
            metadata=metadata,
            path=skill_md,
            content=markdown_content,
            yaml_content=yaml_content
        )

        # 检查是否有脚本文件
        script_path = skill_md.parent / "script.py"
        if script_path.exists():
            skill.script_path = script_path

        logger.debug(f"成功加载技能: {skill_name}")
        return skill

    def load_directory(self, directory: Path | None = None) -> dict[str, Skill]:
        """加载目录中的所有技能

        Args:
            directory: 要扫描的目录，默认使用初始化时的 skills_dir

        Returns:
            技能名称到技能对象的字典
        """
        target_dir = Path(directory) if directory else self.skills_dir

        if not target_dir.exists():
            logger.warning(f"技能目录不存在: {target_dir}")
            return {}

        skills: dict[str, Skill] = {}

        for item in sorted(target_dir.iterdir()):
            if not item.is_dir():
                continue

            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            skill = self.load(skill_md)
            if skill:
                skills[skill.name] = skill

        logger.info(f"从 {target_dir} 加载了 {len(skills)} 个技能")
        return skills

    def refresh(self) -> None:
        """刷新技能缓存

        重新扫描目录并更新内部技能注册表。
        """
        self._skills = self.load_directory()

    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能

        Args:
            name: 技能名称

        Returns:
            Skill 实例，如果不存在返回 None
        """
        if not self._skills:
            self.refresh()

        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """列出所有技能名称

        Returns:
            技能名称列表
        """
        if not self._skills:
            self.refresh()

        return list(self._skills.keys())

    def get_all_skills(self) -> dict[str, Skill]:
        """获取所有已加载的技能

        Returns:
            技能名称到技能对象的字典
        """
        if not self._skills:
            self.refresh()

        return self._skills.copy()


__all__ = ["DirectorySkillLoader"]
