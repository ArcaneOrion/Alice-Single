"""
配置数据类

定义所有配置项的数据结构
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path


@dataclass
class LLMConfig:
    """LLM 配置"""
    model_name: str = "gpt-4"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.7
    enable_thinking: bool = True
    timeout: int = 120


@dataclass
class MemoryConfig:
    """内存配置"""
    working_memory_max_rounds: int = 30
    stm_expiry_days: int = 7
    ltm_auto_distill: bool = True
    working_memory_path: str = "memory/working_memory.md"
    stm_path: str = "memory/short_term_memory.md"
    ltm_path: str = "memory/alice_memory.md"
    todo_path: str = "memory/todo.md"


@dataclass
class DockerConfig:
    """Docker 配置"""
    image_name: str = "alice-sandbox:latest"
    container_name: str = "alice-sandbox-instance"
    work_dir: str = "/app"
    mounts: Dict[str, str] = field(default_factory=lambda: {
        "skills": "/app/skills",
        "alice_output": "/app/alice_output",
    })
    timeout: int = 120


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: str = "alice_runtime.log"
    enable_colors: bool = True
    max_size_mb: int = 10
    backup_count: int = 3


@dataclass
class BridgeConfig:
    """桥接配置"""
    encoding: str = "utf-8"
    line_buffering: bool = True
    max_buffer_size: int = 10 * 1024 * 1024  # 10MB
    window_size: int = 20


@dataclass
class SecurityConfig:
    """安全配置"""
    blocked_commands: List[str] = field(default_factory=lambda: ["rm -rf /", "rm -rf /*"])
    allowed_docker_mounts: List[str] = field(default_factory=list)
    enable_sandbox: bool = True


@dataclass
class Settings:
    """主配置类"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    bridge: BridgeConfig = field(default_factory=BridgeConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # 项目路径
    project_root: Path = field(default_factory=lambda: Path.cwd())
    prompt_path: str = "prompts/alice.md"
    skills_dir: str = "skills"
    output_dir: str = "alice_output"

    def get_absolute_path(self, relative_path: str) -> Path:
        """获取绝对路径"""
        return self.project_root / relative_path
