"""
Toolkit 命令处理器

处理内置 toolkit 指令，管理技能注册表
"""

import logging

logger = logging.getLogger(__name__)


class ToolkitCommandHandler:
    """Toolkit 命令处理器

    处理 toolkit 指令，管理技能列表、刷新和查询
    """

    def __init__(self, snapshot_manager=None):
        self.snapshot_manager = snapshot_manager

    def handle(self, args: list[str]) -> str:
        """处理 toolkit 命令

        Args:
            args: 命令参数列表

        Returns:
            str: 处理结果
        """
        if not args or args[0] == "list":
            return self._handle_list()

        elif args[0] == "info":
            if len(args) > 1:
                return self._handle_info(args[1])
            return "错误: toolkit info 需要提供技能名称。用法: `toolkit info <skill_name>`"

        elif args[0] == "refresh":
            return self._handle_refresh()

        return "未知 toolkit 指令。用法: `toolkit list`, `toolkit info <skill_name>`, `toolkit refresh`"

    def _handle_list(self) -> str:
        """处理 toolkit list 命令"""
        if self.snapshot_manager is None:
            return "技能管理器未初始化。"

        skills = self.snapshot_manager.skills
        if not skills:
            return "当前未注册任何技能。请确保 `skills/` 目录下有正确的 `SKILL.md` 文件。"

        skill_list = []
        for name, data in sorted(skills.items()):
            description = data.get('description', '无描述')
            skill_list.append(f"- **{name}**: {description}")

        return "### 可用技能列表 (内存注册表)\n" + "\n".join(skill_list)

    def _handle_info(self, skill_name: str) -> str:
        """处理 toolkit info 命令"""
        if self.snapshot_manager is None:
            return "技能管理器未初始化。"

        skill = self.snapshot_manager.skills.get(skill_name)
        if not skill:
            return f"技能 '{skill_name}' 未在注册表中。请尝试执行 `toolkit refresh`。"

        yaml_content = skill.get("yaml", "").strip()
        if yaml_content:
            skill_path = skill.get('path', '未知')
            return (
                f"### 技能 '{skill_name}' 配置信息 (内存注册表)\n"
                f"```yaml\n---\n{yaml_content}\n---\n```\n"
                f"*(提示: 如需完整用法，请直接查看 {skill_path})*"
            )

        return f"技能 '{skill_name}' 注册信息不完整，缺少元数据。"

    def _handle_refresh(self) -> str:
        """处理 toolkit refresh 命令"""
        if self.snapshot_manager is None:
            return "技能管理器未初始化。"

        self.snapshot_manager.refresh()
        count = len(self.snapshot_manager.skills)

        logger.info(f"技能注册表已刷新，共发现 {count} 个技能")
        return f"技能注册表已刷新，共发现并注册 {count} 个技能。"


__all__ = [
    "ToolkitCommandHandler",
]
