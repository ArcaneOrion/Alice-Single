"""Function calling 与工具注册相关数据模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .execution_result import ExecutionResult


class ToolCategory(str, Enum):
    """工具分类。"""

    BUILTIN_SYSTEM_TOOLS = "builtin_system_tools"
    SKILLS = "skills"
    TERMINAL_COMMANDS = "terminal_commands"
    CODE_EXECUTION = "code_execution"


class ToolSchemaError(ValueError):
    """工具 schema 相关错误基类。"""

    error_type = "tool_schema_error"


class UnknownToolError(ToolSchemaError):
    """未注册工具错误。"""

    error_type = "unknown_tool"


class ToolArgumentValidationError(ToolSchemaError):
    """工具参数校验错误。"""

    error_type = "invalid_arguments"


@dataclass(frozen=True)
class ToolDescriptor:
    """统一工具描述符。"""

    tool_id: str
    category: ToolCategory
    display_name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "category": self.category.value,
            "display_name": self.display_name,
            "description": self.description,
            "input_schema": self.input_schema,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ToolRegistrySnapshot:
    """四分类工具快照。"""

    builtin_system_tools: list[ToolDescriptor] = field(default_factory=list)
    skills: list[ToolDescriptor] = field(default_factory=list)
    terminal_commands: list[ToolDescriptor] = field(default_factory=list)
    code_execution: list[ToolDescriptor] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            ToolCategory.BUILTIN_SYSTEM_TOOLS.value: [tool.to_dict() for tool in self.builtin_system_tools],
            ToolCategory.SKILLS.value: [tool.to_dict() for tool in self.skills],
            ToolCategory.TERMINAL_COMMANDS.value: [tool.to_dict() for tool in self.terminal_commands],
            ToolCategory.CODE_EXECUTION.value: [tool.to_dict() for tool in self.code_execution],
        }

    def all_tools(self) -> list[ToolDescriptor]:
        return [
            *self.builtin_system_tools,
            *self.skills,
            *self.terminal_commands,
            *self.code_execution,
        ]


@dataclass(frozen=True)
class ToolSchemaDefinition:
    """暴露给模型的工具 schema。"""

    name: str
    description: str
    parameters: dict[str, Any]
    category: ToolCategory = ToolCategory.TERMINAL_COMMANDS
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id=self.name,
            category=self.category,
            display_name=self.name,
            description=self.description,
            input_schema=self.parameters,
            metadata=dict(self.metadata),
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def parse_and_validate_arguments(self, arguments: str) -> dict[str, Any]:
        try:
            payload = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ToolArgumentValidationError(f"无效的工具参数 JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ToolArgumentValidationError("工具参数必须是 JSON object")

        schema_type = self.parameters.get("type")
        if schema_type and schema_type != "object":
            raise ToolArgumentValidationError(f"不支持的工具参数 schema type: {schema_type}")

        properties = self.parameters.get("properties") or {}
        required = self.parameters.get("required") or []
        additional_properties = self.parameters.get("additionalProperties", True)

        for field_name in required:
            value = payload.get(field_name)
            if value in (None, ""):
                raise ToolArgumentValidationError(f"{self.name} 缺少 {field_name} 参数")

        if additional_properties is False:
            unexpected = sorted(key for key in payload if key not in properties)
            if unexpected:
                joined = ", ".join(unexpected)
                raise ToolArgumentValidationError(f"{self.name} 包含未定义参数: {joined}")

        for field_name, schema in properties.items():
            if field_name not in payload:
                continue
            expected_type = schema.get("type")
            if expected_type == "string" and not isinstance(payload[field_name], str):
                raise ToolArgumentValidationError(f"{self.name}.{field_name} 必须是 string")

        return payload


@dataclass(frozen=True)
class ToolInvocation:
    """一次结构化工具调用。"""

    id: str
    name: str
    arguments: str
    index: int = 0
    type: str = "function"

    @classmethod
    def from_tool_call(cls, tool_call: dict[str, Any]) -> "ToolInvocation":
        function = tool_call.get("function") or {}
        return cls(
            id=str(tool_call.get("id") or ""),
            name=str(function.get("name") or ""),
            arguments=str(function.get("arguments") or ""),
            index=int(tool_call.get("index") or 0),
            type=str(tool_call.get("type") or "function"),
        )

    def to_assistant_tool_call(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "index": self.index,
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass(frozen=True)
class ToolResultPayload:
    """回注给模型的结构化工具结果内容。"""

    tool_name: str
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    status: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ToolExecutionResult:
    """结构化工具执行结果。"""

    invocation: ToolInvocation
    payload: ToolResultPayload
    execution_result: ExecutionResult

    def tool_message_content(self) -> str:
        import json

        return json.dumps(self.payload.to_dict(), ensure_ascii=False)

