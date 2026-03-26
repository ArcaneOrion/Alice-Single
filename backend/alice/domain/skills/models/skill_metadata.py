"""
技能元数据模型
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillMetadata:
    """技能元数据

    从 SKILL.md 文件的 YAML frontmatter 中解析。
    """
    name: str
    description: str
    version: str = "1.0.0"
    license: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml_dict(cls, yaml_dict: dict[str, Any], skill_name: str) -> "SkillMetadata":
        """从 YAML 字典创建元数据

        Args:
            yaml_dict: 解析后的 YAML 字典
            skill_name: 技能名称（目录名）

        Returns:
            SkillMetadata 实例
        """
        return cls(
            name=skill_name,
            description=yaml_dict.get("description", "无描述"),
            version=yaml_dict.get("version", "1.0.0"),
            license=yaml_dict.get("license", ""),
            allowed_tools=yaml_dict.get("allowed-tools", yaml_dict.get("allowed_tools", [])),
            metadata=yaml_dict.get("metadata", {})
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "license": self.license,
            "allowed_tools": self.allowed_tools,
            "metadata": self.metadata
        }


__all__ = ["SkillMetadata"]
