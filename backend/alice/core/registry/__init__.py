"""
注册表包

提供命令、技能、内存、LLM 提供商的注册表
"""

from .command_registry import (
    CommandSpec,
    CommandRegistry,
    InMemoryCommandRegistry,
    get_command_registry,
)
from .skill_registry import (
    SkillSpec,
    SkillRegistry,
    InMemorySkillRegistry,
    get_skill_registry,
)
from .memory_registry import (
    MemoryTypeSpec,
    MemoryRegistry,
    InMemoryMemoryRegistry,
    get_memory_registry,
)
from .llm_registry import (
    LLMProviderSpec,
    ModelConfig,
    LLMRegistry,
    InMemoryLLMRegistry,
    get_llm_registry,
)

__all__ = [
    # 命令注册表
    "CommandSpec",
    "CommandRegistry",
    "InMemoryCommandRegistry",
    "get_command_registry",
    # 技能注册表
    "SkillSpec",
    "SkillRegistry",
    "InMemorySkillRegistry",
    "get_skill_registry",
    # 内存注册表
    "MemoryTypeSpec",
    "MemoryRegistry",
    "InMemoryMemoryRegistry",
    "get_memory_registry",
    # LLM 注册表
    "LLMProviderSpec",
    "ModelConfig",
    "LLMRegistry",
    "InMemoryLLMRegistry",
    "get_llm_registry",
]
