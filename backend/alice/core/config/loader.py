from __future__ import annotations

"""配置加载器。"""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .settings import (
    HarnessConfig,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    Settings,
    WorkflowConfig,
)

_LEGACY_RUNTIME_PROMPT_PATH = ".alice/prompt.xml"
_RUNTIME_PROMPT_PATH = ".alice/prompt/prompt.xml"


class ConfigLoader:
    """配置加载器"""

    DEFAULT_CONFIG_PATHS = [".alice/config.json"]

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path

    def load(self) -> Settings:
        """加载配置"""
        return self._load_from_file()

    def _load_from_file(self) -> Settings:
        """从 JSON 文件加载配置"""
        config_path = self._resolve_config_path()
        if config_path.suffix and config_path.suffix.lower() != ".json":
            raise ValueError("运行时配置源只接受 JSON 文件")

        settings = self._default_settings(config_path)
        if not config_path.exists():
            return settings

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._parse_json(data, config_path=config_path)

    def _resolve_config_path(self) -> Path:
        if self.config_path is not None:
            return Path(self.config_path)
        return Path(self.DEFAULT_CONFIG_PATHS[0])

    def _default_settings(self, config_path: Path) -> Settings:
        project_root = config_path.parent.parent if config_path.name == "config.json" and config_path.parent.name == ".alice" else Path.cwd()
        return Settings(project_root=project_root, config_path=".alice/config.json")

    def _parse_json(self, data: dict[str, Any], *, config_path: Path) -> Settings:
        settings = self._default_settings(config_path)
        settings.llm = self._parse_llm_config(data.get("llm", {}), settings.llm)
        settings.workflow = self._parse_workflow_config(data.get("workflow", {}), settings.workflow)
        settings.memory = self._parse_memory_config(data.get("memory", {}), settings.memory)
        settings.harness = self._parse_harness_config(data.get("harness", {}), settings.harness)
        settings.logging = self._parse_logging_config(data.get("logging", {}), settings.logging)
        if output_dir := data.get("output_dir"):
            settings.output_dir = output_dir
        if skills_dir := data.get("skills_dir"):
            settings.skills_dir = skills_dir
        return settings

    def _parse_llm_config(self, data: dict[str, Any], defaults: LLMConfig) -> LLMConfig:
        return LLMConfig(
            model_name=data.get("model_name", defaults.model_name),
            api_key=data.get("api_key", defaults.api_key),
            base_url=data.get("base_url", defaults.base_url),
            provider_name=data.get("provider_name", defaults.provider_name),
            request_header_profiles=data.get("request_header_profiles", defaults.request_header_profiles),
            supports_tool_calling=data.get("supports_tool_calling", defaults.supports_tool_calling),
            max_tokens=data.get("max_tokens", defaults.max_tokens),
            temperature=data.get("temperature", defaults.temperature),
            enable_thinking=data.get("enable_thinking", defaults.enable_thinking),
            timeout=data.get("timeout", defaults.timeout),
        )

    def _parse_workflow_config(self, data: dict[str, Any], defaults: WorkflowConfig) -> WorkflowConfig:
        return WorkflowConfig(
            max_iterations=data.get("max_iterations", defaults.max_iterations),
            max_history=data.get("max_history", defaults.max_history),
        )

    def _parse_memory_config(self, data: dict[str, Any], defaults: MemoryConfig) -> MemoryConfig:
        prompt_path = data.get("prompt_path", defaults.prompt_path)
        if prompt_path == _LEGACY_RUNTIME_PROMPT_PATH:
            raise ValueError(
                f"memory.prompt_path 已废弃旧值 {_LEGACY_RUNTIME_PROMPT_PATH}，"
                f"请改为 {_RUNTIME_PROMPT_PATH}"
            )
        return MemoryConfig(
            prompt_path=prompt_path,
            working_memory_path=data.get("working_memory_path", defaults.working_memory_path),
            stm_path=data.get("stm_path", defaults.stm_path),
            ltm_path=data.get("ltm_path", defaults.ltm_path),
            todo_path=data.get("todo_path", defaults.todo_path),
            max_rounds=data.get("max_rounds", data.get("working_memory_max_rounds", defaults.max_rounds)),
            stm_days_to_keep=data.get("stm_days_to_keep", data.get("stm_expiry_days", defaults.stm_days_to_keep)),
            ltm_auto_distill=data.get("ltm_auto_distill", defaults.ltm_auto_distill),
        )

    def _parse_harness_config(self, data: dict[str, Any], defaults: HarnessConfig) -> HarnessConfig:
        return HarnessConfig(
            name=data.get("name", defaults.name),
            skill_source_name=data.get("skill_source_name", defaults.skill_source_name),
        )

    def _parse_logging_config(self, data: dict[str, Any], defaults: LoggingConfig) -> LoggingConfig:
        return LoggingConfig(
            level=data.get("level", defaults.level),
            console_level=data.get("console_level", defaults.console_level),
            format=data.get("format", defaults.format),
            file=data.get("file", defaults.file),
            enable_colors=data.get("enable_colors", defaults.enable_colors),
            max_size_mb=data.get("max_size_mb", defaults.max_size_mb),
            backup_count=data.get("backup_count", defaults.backup_count),
            enable_structured=data.get("enable_structured", defaults.enable_structured),
            dual_write_legacy=data.get("dual_write_legacy", defaults.dual_write_legacy),
            logs_dir=data.get("logs_dir", defaults.logs_dir),
            system_log_file=data.get("system_log_file", defaults.system_log_file),
            tasks_log_file=data.get("tasks_log_file", defaults.tasks_log_file),
            changes_log_file=data.get("changes_log_file", defaults.changes_log_file),
            schema_file=data.get("schema_file", defaults.schema_file),
            payload_depth=data.get("payload_depth", defaults.payload_depth),
            redaction_policy=data.get("redaction_policy", defaults.redaction_policy),
            capture_thinking=data.get("capture_thinking", defaults.capture_thinking),
            capture_api_headers=data.get("capture_api_headers", defaults.capture_api_headers),
            capture_api_bodies=data.get("capture_api_bodies", defaults.capture_api_bodies),
            capture_tool_io=data.get("capture_tool_io", defaults.capture_tool_io),
            max_field_length=data.get("max_field_length", defaults.max_field_length),
        )

    @staticmethod
    def expand_env_vars(value: str) -> str:
        """展开环境变量 ${VAR}"""
        import re

        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        return re.sub(r"\$\{([^}]+)\}", replace_env_var, value)


def build_default_config_data(config_path: str | None = None) -> dict[str, Any]:
    """构建默认运行时配置的 JSON 数据。"""
    loader = ConfigLoader(config_path)
    settings = loader._default_settings(loader._resolve_config_path())
    return {
        "llm": asdict(settings.llm),
        "workflow": asdict(settings.workflow),
        "memory": asdict(settings.memory),
        "harness": asdict(settings.harness),
        "logging": asdict(settings.logging),
        "skills_dir": settings.skills_dir,
        "output_dir": settings.output_dir,
    }


def load_config(config_path: str | None = None) -> Settings:
    """便捷函数：加载配置"""
    loader = ConfigLoader(config_path)
    return loader.load()
