from __future__ import annotations

"""
配置数据类

定义所有配置项的数据结构
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LLMConfig:
    """LLM 配置"""

    model_name: str = ""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    provider_name: str = "openai"
    request_header_profiles: list[dict[str, Any]] = field(default_factory=list)
    supports_tool_calling: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    enable_thinking: bool = True
    timeout: int = 120


@dataclass
class MemoryConfig:
    """内存配置"""

    prompt_path: str = ".alice/prompt.md"
    working_memory_path: str = ".alice/memory/working_memory.md"
    stm_path: str = ".alice/memory/short_term_memory.md"
    ltm_path: str = ".alice/memory/alice_memory.md"
    todo_path: str = ".alice/memory/todo.md"
    max_rounds: int = 30
    stm_days_to_keep: int = 7
    ltm_auto_distill: bool = True

    @property
    def working_memory_max_rounds(self) -> int:
        return self.max_rounds

    @working_memory_max_rounds.setter
    def working_memory_max_rounds(self, value: int) -> None:
        self.max_rounds = value

    @property
    def stm_expiry_days(self) -> int:
        return self.stm_days_to_keep

    @stm_expiry_days.setter
    def stm_expiry_days(self, value: int) -> None:
        self.stm_days_to_keep = value


@dataclass
class WorkflowConfig:
    """工作流配置"""

    max_iterations: int = 10
    max_history: int = 50


@dataclass
class HarnessConfig:
    """运行时装配配置"""

    name: str = "docker"
    skill_source_name: str = "default"


@dataclass
class DockerConfig:
    """Docker 配置"""

    image_name: str = "alice-sandbox:latest"
    container_name: str = "alice-sandbox-instance"
    work_dir: str = "/app"
    dockerfile_path: str = "Dockerfile.sandbox"
    mounts: dict[str, str] = field(
        default_factory=lambda: {
            "skills": "/app/skills",
            ".alice/output": "/app/alice_output",
        }
    )
    timeout: int = 120


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    console_level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: str = "alice_runtime.log"
    enable_colors: bool = True
    max_size_mb: int = 10
    backup_count: int = 3
    enable_structured: bool = True
    dual_write_legacy: bool = True
    logs_dir: str = ".alice/logs"
    system_log_file: str = "system.jsonl"
    tasks_log_file: str = "tasks.jsonl"
    changes_log_file: str = "changes.jsonl"
    schema_file: str = "schema_version.json"
    payload_depth: int = -1
    redaction_policy: str = "minimal"
    capture_thinking: bool = True
    capture_api_headers: bool = True
    capture_api_bodies: bool = True
    capture_tool_io: bool = True
    max_field_length: int = 0


@dataclass
class BridgeConfig:
    """桥接配置"""

    encoding: str = "utf-8"
    line_buffering: bool = True
    max_buffer_size: int = 10 * 1024 * 1024
    window_size: int = 20


@dataclass
class SecurityConfig:
    """安全配置"""

    blocked_commands: list[str] = field(default_factory=lambda: ["rm -rf /", "rm -rf /*"])
    allowed_docker_mounts: list[str] = field(default_factory=list)
    enable_sandbox: bool = True


@dataclass
class Settings:
    """主配置类"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    harness: HarnessConfig = field(default_factory=HarnessConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    bridge: BridgeConfig = field(default_factory=BridgeConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    project_root: Path = field(default_factory=lambda: Path.cwd())
    config_path: str = ".alice/config.json"
    skills_dir: str = "skills"
    output_dir: str = ".alice/output"

    @property
    def prompt_path(self) -> str:
        return self.memory.prompt_path

    @prompt_path.setter
    def prompt_path(self, value: str) -> None:
        self.memory.prompt_path = value

    def get_absolute_path(self, relative_path: str) -> Path:
        """获取绝对路径"""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return self.project_root / path
