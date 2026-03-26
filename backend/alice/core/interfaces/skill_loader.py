"""
Skill Loader Protocol

定义技能加载器的接口规范
"""

from typing import Protocol
from dataclasses import dataclass
from abc import abstractmethod
from pathlib import Path


@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    description: str
    version: str = "1.0.0"
    license: str = ""
    allowed_tools: list[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Skill:
    """技能定义"""
    metadata: SkillMetadata
    path: Path
    content: str = ""  # SKILL.md 内容
    is_cached: bool = False


class SkillLoader(Protocol):
    """技能加载器接口"""

    @abstractmethod
    def load(self, path: Path) -> Skill | None:
        """加载单个技能"""
        ...

    @abstractmethod
    def load_directory(self, directory: Path) -> dict[str, Skill]:
        """加载目录中的所有技能"""
        ...

    @abstractmethod
    def refresh(self) -> None:
        """刷新技能缓存"""
        ...

    @abstractmethod
    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能"""
        ...

    @abstractmethod
    def list_skills(self) -> list[str]:
        """列出所有技能名称"""
        ...
