"""
技能文件仓库

提供技能文件的持久化访问功能。
"""

import logging
from pathlib import Path
from typing import Any

from ..models import Skill, SkillMetadata
from ..loaders.base import BaseSkillLoader

logger = logging.getLogger(__name__)


class FileRepository:
    """技能文件仓库

    负责从文件系统中读取和写入技能相关文件。
    """

    def __init__(self, skills_dir: str | Path = "skills"):
        """初始化仓库

        Args:
            skills_dir: 技能目录路径
        """
        self.skills_dir = Path(skills_dir)

    def read_file(self, relative_path: str) -> str | None:
        """读取文件内容

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件内容字符串，如果读取失败返回 None
        """
        full_path = self.skills_dir / relative_path

        if not full_path.exists():
            logger.warning(f"文件不存在: {full_path}")
            return None

        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败 {full_path}: {e}")
            return None

    def write_file(self, relative_path: str, content: str) -> bool:
        """写入文件内容

        Args:
            relative_path: 相对于 skills/ 目录的文件路径
            content: 要写入的内容

        Returns:
            写入成功返回 True
        """
        full_path = self.skills_dir / relative_path

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"文件写入成功: {full_path}")
            return True
        except Exception as e:
            logger.error(f"写入文件失败 {full_path}: {e}")
            return False

    def file_exists(self, relative_path: str) -> bool:
        """检查文件是否存在

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件存在返回 True
        """
        return (self.skills_dir / relative_path).exists()

    def get_mtime(self, relative_path: str) -> float | None:
        """获取文件修改时间

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件 mtime，如果文件不存在返回 None
        """
        full_path = self.skills_dir / relative_path

        try:
            return full_path.stat().st_mtime
        except FileNotFoundError:
            return None

    def list_skill_directories(self) -> list[Path]:
        """列出所有技能目录

        Returns:
            技能目录路径列表
        """
        if not self.skills_dir.exists():
            return []

        skill_dirs = []
        for item in sorted(self.skills_dir.iterdir()):
            if item.is_dir() and (item / "SKILL.md").exists():
                skill_dirs.append(item)

        return skill_dirs

    def get_skill_path(self, skill_name: str) -> Path:
        """获取技能目录路径

        Args:
            skill_name: 技能名称

        Returns:
            技能目录的完整路径
        """
        return self.skills_dir / skill_name

    def get_skill_md_path(self, skill_name: str) -> Path:
        """获取 SKILL.md 文件路径

        Args:
            skill_name: 技能名称

        Returns:
            SKILL.md 文件的完整路径
        """
        return self.skills_dir / skill_name / "SKILL.md"

    def get_script_path(self, skill_name: str) -> Path:
        """获取 script.py 文件路径

        Args:
            skill_name: 技能名称

        Returns:
            script.py 文件的完整路径
        """
        return self.skills_dir / skill_name / "script.py"


__all__ = ["FileRepository"]
