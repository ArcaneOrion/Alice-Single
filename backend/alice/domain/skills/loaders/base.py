"""
技能加载器基类

实现 SkillLoader 接口协议。
"""

import re
import time
import os
from pathlib import Path
from typing import Protocol
from abc import ABC, abstractmethod

from ..models import Skill, SkillMetadata


class SkillLoader(Protocol):
    """技能加载器接口协议"""

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


class BaseSkillLoader(ABC):
    """技能加载器基类

    提供通用的 SKILL.md 解析逻辑。
    """

    # YAML frontmatter 匹配模式
    YAML_PATTERN = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)

    def _parse_skill_markdown(self, content: str) -> tuple[str, str]:
        """解析 SKILL.md 文件内容

        Args:
            content: SKILL.md 文件内容

        Returns:
            (yaml_content, markdown_content) 元组
        """
        yaml_match = self.YAML_PATTERN.match(content)
        if yaml_match:
            yaml_content = yaml_match.group(1)
            markdown_content = content[yaml_match.end():]
            return yaml_content, markdown_content
        return "", content

    def _parse_yaml_dict(self, yaml_content: str) -> dict[str, any]:
        """简单的 YAML 解析

        解析 skill metadata 所需的基本字段。
        不依赖外部 yaml 库，保持轻量级。

        Args:
            yaml_content: YAML 内容字符串

        Returns:
            解析后的字典
        """
        result = {}
        for line in yaml_content.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # 处理列表值
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip().strip('"\'') for v in value[1:-1].split(',')]
                # 去除引号
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # 处理连字符命名的 key
                key = key.replace('-', '_')

                result[key] = value

        return result

    def _extract_description(self, yaml_content: str, full_content: str) -> str:
        """从 YAML 内容中提取 description

        Args:
            yaml_content: YAML frontmatter 内容
            full_content: 完整的文件内容（作为后备）

        Returns:
            描述字符串
        """
        # 优先从 YAML 中提取
        if yaml_content:
            desc_match = re.search(r'description:\s*(.*)', yaml_content)
            if desc_match:
                desc = desc_match.group(1).strip()
                # 去除可能的引号
                desc = desc.strip('"\'')
                return desc

        # 后备：从全文中搜索
        desc_match = re.search(r'description:\s*(.*)', full_content)
        if desc_match:
            desc = desc_match.group(1).strip()
            desc = desc.strip('"\'')
            return desc

        return "无描述"

    @abstractmethod
    def load(self, path: Path) -> Skill | None:
        """加载单个技能"""
        pass

    @abstractmethod
    def load_directory(self, directory: Path) -> dict[str, Skill]:
        """加载目录中的所有技能"""
        pass


__all__ = ["SkillLoader", "BaseSkillLoader"]
