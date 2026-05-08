"""
技能文件仓库

提供技能文件的持久化访问功能。
支持多目录（内置 + 用户自定义），读取时用户目录优先，
写入时始终写入用户目录。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileRepository:
    """技能文件仓库

    负责从文件系统中读取和写入技能相关文件。
    支持多个技能目录，读取时按顺序查找（后加载的覆盖先加载的），
    写入时始终写入第一个可写目录（通常是用户目录）。
    """

    def __init__(
        self,
        skills_dirs: str | Path | list[str | Path] = "backend/alice/skills",
        write_dir: str | Path | None = None,
    ):
        """初始化仓库

        Args:
            skills_dirs: 技能目录路径，可以是单个路径或路径列表
            write_dir: 写入时使用的目录，默认使用 skills_dirs 的第一个路径
        """
        if isinstance(skills_dirs, (str, Path)):
            self.skills_dirs = [Path(skills_dirs)]
        else:
            self.skills_dirs = [Path(d) for d in skills_dirs]
        self.write_dir = Path(write_dir) if write_dir else self.skills_dirs[0]

    def _resolve_path(self, relative_path: str, for_write: bool = False) -> Path | None:
        """解析文件路径

        Args:
            relative_path: 相对于 skills/ 目录的文件路径
            for_write: 是否为写入操作

        Returns:
            完整路径，如果无法解析返回 None
        """
        if for_write:
            return self.write_dir / relative_path

        # 读取时按顺序查找，后加载的（用户目录）优先
        for skills_dir in reversed(self.skills_dirs):
            full_path = skills_dir / relative_path
            if full_path.exists():
                return full_path
        return None

    def read_file(self, relative_path: str) -> str | None:
        """读取文件内容

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件内容字符串，如果读取失败返回 None
        """
        full_path = self._resolve_path(relative_path)
        if full_path is None:
            logger.warning(f"文件不存在: {relative_path} (搜索目录: {self.skills_dirs})")
            return None

        try:
            with open(full_path, encoding='utf-8', errors='ignore') as f:
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
        full_path = self._resolve_path(relative_path, for_write=True)
        if full_path is None:
            logger.error(f"无法确定写入路径: {relative_path}")
            return False

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
        return self._resolve_path(relative_path) is not None

    def get_mtime(self, relative_path: str) -> float | None:
        """获取文件修改时间

        Args:
            relative_path: 相对于 skills/ 目录的文件路径

        Returns:
            文件 mtime，如果文件不存在返回 None
        """
        full_path = self._resolve_path(relative_path)
        if full_path is None:
            return None

        try:
            return full_path.stat().st_mtime
        except FileNotFoundError:
            return None

    def list_skill_directories(self) -> list[Path]:
        """列出所有技能目录

        从所有 skills_dirs 中收集技能目录，后加载的优先（去重）。

        Returns:
            技能目录路径列表
        """
        seen: set[str] = set()
        skill_dirs: list[Path] = []

        # 先扫描内置目录，再扫描用户目录，后扫描的排在前面
        for skills_dir in reversed(self.skills_dirs):
            if not skills_dir.exists():
                continue

            for item in sorted(skills_dir.iterdir()):
                if not item.is_dir():
                    continue
                if not (item / "SKILL.md").exists():
                    continue
                dir_key = item.name
                if dir_key not in seen:
                    seen.add(dir_key)
                    skill_dirs.append(item)

        return skill_dirs

    def get_skill_path(self, skill_name: str) -> Path:
        """获取技能目录路径（用于写入）

        Args:
            skill_name: 技能名称

        Returns:
            技能目录的完整路径
        """
        return self.write_dir / skill_name

    def get_skill_md_path(self, skill_name: str) -> Path:
        """获取 SKILL.md 文件路径（用于写入）

        Args:
            skill_name: 技能名称

        Returns:
            SKILL.md 文件的完整路径
        """
        return self.write_dir / skill_name / "SKILL.md"

    def get_script_path(self, skill_name: str) -> Path:
        """获取 script.py 文件路径（用于写入）

        Args:
            skill_name: 技能名称

        Returns:
            script.py 文件的完整路径
        """
        return self.write_dir / skill_name / "script.py"

    def find_skill_path(self, skill_name: str) -> Path | None:
        """查找技能目录路径（读取，优先用户目录）

        Args:
            skill_name: 技能名称

        Returns:
            技能目录的完整路径，如果不存在返回 None
        """
        for skills_dir in reversed(self.skills_dirs):
            path = skills_dir / skill_name
            if path.exists() and (path / "SKILL.md").exists():
                return path
        return None


__all__ = ["FileRepository"]
