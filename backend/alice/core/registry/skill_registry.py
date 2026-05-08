"""
技能注册表

管理技能的注册与查找
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.alice.domain.skills.services.skill_registry import (
    SkillRegistry as RuntimeSkillRegistry,
)

from ..interfaces.skill_loader import SkillSourceFactory


@dataclass
class SkillSpec:
    """技能规范"""

    name: str
    description: str
    path: Path
    version: str = "1.0.0"
    license: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    content: str = ""  # SKILL.md 内容

    def __post_init__(self):
        pass


@dataclass
class SkillSourceSpec:
    """运行时技能来源规范。"""

    name: str
    factory: SkillSourceFactory
    description: str = ""


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
    def get(self, name: str) -> SkillSpec | None:
        """获取技能规范"""
        ...

    @abstractmethod
    def list_all(self) -> list[SkillSpec]:
        """列出所有技能"""
        ...

    @abstractmethod
    def search(self, query: str) -> list[SkillSpec]:
        """搜索技能"""
        ...

    @abstractmethod
    def register_source(self, spec: SkillSourceSpec) -> None:
        """注册运行时技能来源。"""
        ...

    @abstractmethod
    def get_source(self, name: str) -> SkillSourceSpec | None:
        """获取运行时技能来源。"""
        ...

    @abstractmethod
    def create_runtime_registry(self, name: str = "default", **kwargs: Any) -> RuntimeSkillRegistry:
        """创建运行时技能注册表。"""
        ...


class InMemorySkillRegistry(SkillRegistry):
    """内存技能注册表实现"""

    def __init__(self):
        self._skills: dict[str, SkillSpec] = {}
        self._sources: dict[str, SkillSourceSpec] = {}
        self.register_source(
            SkillSourceSpec(
                name="default",
                factory=lambda skills_dirs=None, project_root=None, **_: RuntimeSkillRegistry(
                    skills_dirs=skills_dirs or [
                        str((project_root or Path(".")) / "backend/alice/skills"),
                        str((project_root or Path(".")) / ".alice/skills"),
                    ]
                ),
                description="默认运行时技能注册表",
            )
        )

    def register(self, spec: SkillSpec) -> None:
        """注册技能"""
        self._skills[spec.name] = spec

    def unregister(self, name: str) -> None:
        """注销技能"""
        if name in self._skills:
            del self._skills[name]

    def get(self, name: str) -> SkillSpec | None:
        """获取技能规范"""
        return self._skills.get(name)

    def list_all(self) -> list[SkillSpec]:
        """列出所有技能"""
        return list(self._skills.values())

    def search(self, query: str) -> list[SkillSpec]:
        """搜索技能"""
        query_lower = query.lower()
        results = []
        for spec in self._skills.values():
            if query_lower in spec.name.lower() or query_lower in spec.description.lower():
                results.append(spec)
        return results

    def register_source(self, spec: SkillSourceSpec) -> None:
        """注册运行时技能来源。"""
        self._sources[spec.name] = spec

    def get_source(self, name: str) -> SkillSourceSpec | None:
        """获取运行时技能来源。"""
        return self._sources.get(name)

    def create_runtime_registry(self, name: str = "default", **kwargs: Any) -> RuntimeSkillRegistry:
        """创建运行时技能注册表。"""
        spec = self.get_source(name)
        if spec is None:
            raise ValueError(f"未注册的技能来源: {name}")
        runtime_registry = spec.factory(**kwargs)
        if not isinstance(runtime_registry, RuntimeSkillRegistry):
            raise TypeError("技能来源工厂必须返回 domain SkillRegistry")
        return runtime_registry

    def get_skill_content(self, name: str) -> str | None:
        """获取技能内容"""
        spec = self.get(name)
        return spec.content if spec else None

    def refresh_from_directory(self, directory: Path) -> int:
        """从目录刷新技能注册表"""
        import re

        count = 0
        if not directory.exists():
            return count

        for item in directory.iterdir():
            if not item.is_dir():
                continue
            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
            except Exception:
                continue
            yaml_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if not yaml_match:
                continue
            metadata = self._parse_yaml_metadata(yaml_match.group(1))
            if metadata is None:
                continue
            self.register(
                SkillSpec(
                    name=metadata.name,
                    description=metadata.description,
                    path=item,
                    version=metadata.version,
                    license=metadata.license,
                    allowed_tools=metadata.allowed_tools,
                    metadata=metadata.metadata,
                    content=content,
                )
            )
            count += 1

        return count

    def _parse_yaml_metadata(self, yaml_content: str):
        """解析 YAML 元数据"""
        from ..interfaces.skill_loader import SkillMetadata

        metadata = {}
        for line in yaml_content.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return SkillMetadata(
            name=metadata.get("name", ""),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0.0"),
            license=metadata.get("license", ""),
        )

    def clear(self) -> None:
        """清空所有技能"""
        self._skills.clear()
        self._sources.clear()
        self.register_source(
            SkillSourceSpec(
                name="default",
                factory=lambda skills_dirs=None, project_root=None, **_: RuntimeSkillRegistry(
                    skills_dirs=skills_dirs or [
                        str((project_root or Path(".")) / "backend/alice/skills"),
                        str((project_root or Path(".")) / ".alice/skills"),
                    ]
                ),
                description="默认运行时技能注册表",
            )
        )


_global_skill_registry: InMemorySkillRegistry | None = None


def get_skill_registry() -> InMemorySkillRegistry:
    """获取全局技能注册表实例"""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = InMemorySkillRegistry()
    return _global_skill_registry
