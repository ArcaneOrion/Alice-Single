"""
技能注册表

管理技能的注册与查找
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from pathlib import Path
from abc import ABC, abstractmethod


@dataclass
class SkillSpec:
    """技能规范"""
    name: str
    description: str
    path: Path
    version: str = "1.0.0"
    license: str = ""
    allowed_tools: List[str] = None
    metadata: Dict = None
    content: str = ""  # SKILL.md 内容

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = []
        if self.metadata is None:
            self.metadata = {}


class SkillRegistry(ABC):
    """技能注册表接口"""

    @abstractmethod
    def register(self, spec: SkillSpec) -> None:
        """注册技能"""
        ...

    @abstractmethod
    def unregister(self, name: str) -> None:
        """注销技能"""
        ...

    @abstractmethod
    def get(self, name: str) -> Optional[SkillSpec]:
        """获取技能规范"""
        ...

    @abstractmethod
    def list_all(self) -> List[SkillSpec]:
        """列出所有技能"""
        ...

    @abstractmethod
    def search(self, query: str) -> List[SkillSpec]:
        """搜索技能"""
        ...


class InMemorySkillRegistry(SkillRegistry):
    """内存技能注册表实现"""

    def __init__(self):
        self._skills: Dict[str, SkillSpec] = {}

    def register(self, spec: SkillSpec) -> None:
        """注册技能"""
        self._skills[spec.name] = spec

    def unregister(self, name: str) -> None:
        """注销技能"""
        if name in self._skills:
            del self._skills[name]

    def get(self, name: str) -> Optional[SkillSpec]:
        """获取技能规范"""
        return self._skills.get(name)

    def list_all(self) -> List[SkillSpec]:
        """列出所有技能"""
        return list(self._skills.values())

    def search(self, query: str) -> List[SkillSpec]:
        """搜索技能"""
        query_lower = query.lower()
        results = []
        for spec in self._skills.values():
            if (query_lower in spec.name.lower() or
                query_lower in spec.description.lower()):
                results.append(spec)
        return results

    def get_skill_content(self, name: str) -> Optional[str]:
        """获取技能内容"""
        spec = self.get(name)
        return spec.content if spec else None

    def refresh_from_directory(self, directory: Path) -> int:
        """从目录刷新技能注册表"""
        import os
        from ..interfaces.skill_loader import SkillMetadata

        count = 0
        if not directory.exists():
            return count

        for item in directory.iterdir():
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    # 解析 SKILL.md
                    metadata = self._parse_skill_md(skill_md)
                    if metadata:
                        spec = SkillSpec(
                            name=metadata.name,
                            description=metadata.description,
                            path=item,
                            version=metadata.version,
                            license=metadata.license,
                            allowed_tools=metadata.allowed_tools,
                            metadata=metadata.metadata
                        )
                        self.register(spec)
                        count += 1

        return count

    def _parse_skill_md(self, path: Path) -> Optional[SkillSpec]:
        """解析 SKILL.md 文件"""
        import re
        from ..interfaces.skill_loader import SkillMetadata

        try:
            content = path.read_text(encoding="utf-8")

            # 解析 YAML 前置元数据
            yaml_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if yaml_match:
                yaml_content = yaml_match.group(1)
                metadata = self._parse_yaml_metadata(yaml_content)
                return metadata
        except Exception:
            pass

        return None

    def _parse_yaml_metadata(self, yaml_content: str) -> Optional[SkillSpec]:
        """解析 YAML 元数据"""
        from ..interfaces.skill_loader import SkillMetadata

        metadata = {}
        for line in yaml_content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

        return SkillMetadata(
            name=metadata.get('name', ''),
            description=metadata.get('description', ''),
            version=metadata.get('license', '1.0.0'),
            license=metadata.get('license', ''),
        )

    def clear(self) -> None:
        """清空所有技能"""
        self._skills.clear()


# 全局技能注册表实例
_global_skill_registry: Optional[InMemorySkillRegistry] = None


def get_skill_registry() -> InMemorySkillRegistry:
    """获取全局技能注册表实例"""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = InMemorySkillRegistry()
    return _global_skill_registry
