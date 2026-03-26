"""
Skills Domain Module

负责技能的发现、加载、缓存和注册管理。

模块结构：
- models: 技能数据模型（Skill, SkillMetadata）
- loaders: 技能加载器（DirectorySkillLoader, CacheSkillLoader）
- services: 业务服务（SkillRegistry, SkillCache）
- repository: 文件访问（FileRepository）
"""

from .models import Skill, SkillMetadata
from .loaders import CacheSkillLoader, DirectorySkillLoader, SkillLoader
from .services import SkillRegistry, SkillCache
from .repository import FileRepository

__all__ = [
    # Models
    "Skill",
    "SkillMetadata",
    # Loaders
    "SkillLoader",
    "DirectorySkillLoader",
    "CacheSkillLoader",
    # Services
    "SkillRegistry",
    "SkillCache",
    # Repository
    "FileRepository",
]
