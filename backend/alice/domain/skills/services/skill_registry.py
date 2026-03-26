"""
技能注册服务

提供技能的注册、查询和管理功能。
"""

import logging
from pathlib import Path
from typing import Any

from ..models import Skill, SkillMetadata
from ..loaders import CacheSkillLoader

logger = logging.getLogger(__name__)


class SkillRegistry:
    """技能注册表

    管理所有已注册的技能，提供查询和列表功能。
    """

    def __init__(self, loader: CacheSkillLoader | None = None):
        """初始化注册表

        Args:
            loader: 技能加载器实例，如果为 None 则创建默认实例
        """
        self.loader = loader or CacheSkillLoader()
        self._refreshed = False

    def refresh(self) -> int:
        """刷新技能注册表

        Returns:
            注册的技能数量
        """
        self.loader.refresh()
        self._refreshed = True
        count = len(self.loader.get_all_skills())
        logger.info(f"技能注册表已刷新，共 {count} 个技能")
        return count

    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能

        Args:
            name: 技能名称

        Returns:
            Skill 实例，如果不存在返回 None
        """
        if not self._refreshed:
            self.refresh()
        return self.loader.get_skill(name)

    def list_skills(self) -> list[str]:
        """列出所有技能名称

        Returns:
            技能名称列表（排序后）
        """
        if not self._refreshed:
            self.refresh()
        return sorted(self.loader.list_skills())

    def get_all_skills(self) -> dict[str, Skill]:
        """获取所有已注册的技能

        Returns:
            技能名称到技能对象的字典
        """
        if not self._refreshed:
            self.refresh()
        return self.loader.get_all_skills()

    def get_skill_info(self, name: str) -> str | None:
        """获取技能的详细信息文本

        Args:
            name: 技能名称

        Returns:
            技能信息文本，如果技能不存在返回 None
        """
        skill = self.get_skill(name)
        if not skill:
            return None

        yaml_content = skill.yaml_content.strip()
        if yaml_content:
            return (
                f"### 技能 '{name}' 配置信息\n"
                f"```yaml\n---\n{yaml_content}\n---\n```\n"
                f"*(路径: {skill.path})*"
            )
        return f"技能 '{name}' 注册信息不完整，缺少元数据。"

    def list_skills_summary(self) -> str:
        """生成技能列表摘要文本

        Returns:
            格式化的技能列表文本
        """
        skills = self.get_all_skills()
        if not skills:
            return "当前未注册任何技能。"

        lines = []
        for name in sorted(skills.keys()):
            skill = skills[name]
            lines.append(f"- **{name}**: {skill.description}")

        return "### 可用技能列表\n" + "\n".join(lines)

    def has_skill(self, name: str) -> bool:
        """检查技能是否存在

        Args:
            name: 技能名称

        Returns:
            如果技能存在返回 True
        """
        if not self._refreshed:
            self.refresh()
        return name in self.loader.list_skills()

    def get_skill_count(self) -> int:
        """获取已注册技能数量

        Returns:
            技能数量
        """
        if not self._refreshed:
            self.refresh()
        return len(self.loader.list_skills())


__all__ = ["SkillRegistry"]
