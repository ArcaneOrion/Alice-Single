"""
Execution Domain - 数据模型
"""

from .command import Command, CommandType, ExecutionEnvironment
from .execution_result import ExecutionResult, ExecutionStatus
from .security_rule import SecurityRule, SecurityAction, DEFAULT_SECURITY_RULES
from .tool_calling import (
    ToolArgumentValidationError,
    ToolCategory,
    ToolDescriptor,
    ToolExecutionResult,
    ToolInvocation,
    ToolRegistrySnapshot,
    ToolResultPayload,
    ToolSchemaDefinition,
    ToolSchemaError,
    UnknownToolError,
)

__all__ = [
    "Command",
    "CommandType",
    "ExecutionEnvironment",
    "ExecutionResult",
    "ExecutionStatus",
    "SecurityRule",
    "SecurityAction",
    "DEFAULT_SECURITY_RULES",
    "ToolArgumentValidationError",
    "ToolCategory",
    "ToolDescriptor",
    "ToolExecutionResult",
    "ToolInvocation",
    "ToolRegistrySnapshot",
    "ToolResultPayload",
    "ToolSchemaDefinition",
    "ToolSchemaError",
    "UnknownToolError",
]
