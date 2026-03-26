"""
技能模型
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .skill_metadata import SkillMetadata


@dataclass
class Skill:
    """技能定义

    包含技能的元数据、路径、内容和状态信息。
    """
    metadata: SkillMetadata
    path: Path
    content: str = ""
    is_cached: bool = False
    yaml_content: str = ""
    script_path: Path | None = None

    @property
    def name(self) -> str:
        """获取技能名称"""
        return self.metadata.name

    @property
    def description(self) -> str:
        """获取技能描述"""
        return self.metadata.description

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于兼容旧代码）"""
        return {
            "name": self.name,
            "description": self.description,
            "yaml": self.yaml_content,
            "path": str(self.path),
            "metadata": self.metadata.to_dict()
        }

    def get_summary(self) -> str:
        """获取技能摘要文本"""
        return f"[技能: {self.name}] 功能: {self.description}"


__all__ = ["Skill"]
