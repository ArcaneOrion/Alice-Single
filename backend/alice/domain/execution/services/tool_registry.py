"""Phase-2 轻量 Tool Registry。"""

from __future__ import annotations

from ..models import (
    ToolCategory,
    ToolDescriptor,
    ToolRegistrySnapshot,
    ToolSchemaDefinition,
)
from ...skills.services.skill_registry import SkillRegistry


class ToolRegistry:
    """统一维护四分类工具快照，并继续暴露最小 function calling schema。"""

    def __init__(self, skill_registry: SkillRegistry | None = None) -> None:
        self.skill_registry = skill_registry
        self._tools = {
            "run_bash": ToolSchemaDefinition(
                name="run_bash",
                description="在受控执行环境中运行 bash 命令。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的 bash 命令字符串",
                        }
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                category=ToolCategory.TERMINAL_COMMANDS,
                metadata={"execution_environment": "docker"},
            ),
            "run_python": ToolSchemaDefinition(
                name="run_python",
                description="在受控执行环境中运行 Python 代码。",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "要执行的 Python 代码",
                        }
                    },
                    "required": ["code"],
                    "additionalProperties": False,
                },
                category=ToolCategory.CODE_EXECUTION,
                metadata={"execution_environment": "docker"},
            ),
        }

    def set_skill_registry(self, skill_registry: SkillRegistry | None) -> None:
        self.skill_registry = skill_registry

    def list_tools(self) -> list[ToolSchemaDefinition]:
        return list(self._tools.values())

    def list_openai_tools(self) -> list[dict]:
        return [tool.to_openai_tool() for tool in self.list_tools()]

    def get_tool(self, name: str) -> ToolSchemaDefinition | None:
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def snapshot(self) -> ToolRegistrySnapshot:
        builtin_tools = [
            ToolDescriptor(
                tool_id="toolkit",
                category=ToolCategory.BUILTIN_SYSTEM_TOOLS,
                display_name="toolkit",
                description="宿主机侧技能注册表命令入口。",
                metadata={"handler": "toolkit", "source": "execution_service"},
            ),
            ToolDescriptor(
                tool_id="memory",
                category=ToolCategory.BUILTIN_SYSTEM_TOOLS,
                display_name="memory",
                description="宿主机侧记忆写入命令入口。",
                metadata={"handler": "memory", "source": "execution_service"},
            ),
            ToolDescriptor(
                tool_id="todo",
                category=ToolCategory.BUILTIN_SYSTEM_TOOLS,
                display_name="todo",
                description="宿主机侧待办写入命令入口。",
                metadata={"handler": "todo", "source": "execution_service"},
            ),
            ToolDescriptor(
                tool_id="update_prompt",
                category=ToolCategory.BUILTIN_SYSTEM_TOOLS,
                display_name="update_prompt",
                description="宿主机侧系统提示词更新命令入口。",
                metadata={"handler": "update_prompt", "source": "execution_service"},
            ),
        ]
        skill_tools = self._build_skill_descriptors()
        return ToolRegistrySnapshot(
            builtin_system_tools=builtin_tools,
            skills=skill_tools,
            terminal_commands=[self._tools["run_bash"].to_descriptor()],
            code_execution=[self._tools["run_python"].to_descriptor()],
        )

    def snapshot_dict(self) -> dict[str, list[dict]]:
        return self.snapshot().to_dict()

    def _build_skill_descriptors(self) -> list[ToolDescriptor]:
        if self.skill_registry is None:
            return []

        descriptors: list[ToolDescriptor] = [
            ToolDescriptor(
                tool_id="skills.list",
                category=ToolCategory.SKILLS,
                display_name="skills.list",
                description="列出当前已注册技能。",
                metadata={"source": "skill_registry"},
            ),
            ToolDescriptor(
                tool_id="skills.info",
                category=ToolCategory.SKILLS,
                display_name="skills.info",
                description="读取指定技能元信息。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string", "description": "技能名称"}
                    },
                    "required": ["skill_name"],
                    "additionalProperties": False,
                },
                metadata={"source": "skill_registry"},
            ),
            ToolDescriptor(
                tool_id="skills.refresh",
                category=ToolCategory.SKILLS,
                display_name="skills.refresh",
                description="刷新技能注册表。",
                metadata={"source": "skill_registry"},
            ),
            ToolDescriptor(
                tool_id="skills.read_file",
                category=ToolCategory.SKILLS,
                display_name="skills.read_file",
                description="读取 skills/ 目录下的技能文件快照。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "relative_path": {"type": "string", "description": "相对于 skills/ 的路径"}
                    },
                    "required": ["relative_path"],
                    "additionalProperties": False,
                },
                metadata={"source": "skill_registry"},
            ),
        ]

        for name, skill in sorted(self.skill_registry.get_all_skills().items()):
            descriptors.append(
                ToolDescriptor(
                    tool_id=f"skill:{name}",
                    category=ToolCategory.SKILLS,
                    display_name=name,
                    description=skill.description,
                    metadata={
                        "source": "skill_registry",
                        "path": str(skill.path),
                    },
                )
            )
        return descriptors


__all__ = ["ToolRegistry"]
