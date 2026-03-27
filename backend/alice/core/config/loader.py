"""
配置加载器

从 TOML 文件和环境变量加载配置
"""

import os
from pathlib import Path
from typing import Optional

from .settings import Settings, LLMConfig, MemoryConfig, DockerConfig, LoggingConfig

try:
    import tomllib as toml
except ModuleNotFoundError:
    import tomli as toml


class ConfigLoader:
    """配置加载器"""

    DEFAULT_CONFIG_PATHS = [
        "alice.toml",
        "config/alice.toml",
        "/etc/alice/config.toml",
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path

    def load(self) -> Settings:
        """加载配置"""
        # 1. 从文件加载
        settings = self._load_from_file()

        # 2. 从环境变量覆盖
        self._apply_env_vars(settings)

        # 3. 验证配置
        # from .validator import ConfigValidator
        # ConfigValidator.validate(settings)

        return settings

    def _load_from_file(self) -> Settings:
        """从文件加载配置"""
        config_path = self._find_config_file()
        if config_path is None:
            return Settings()  # 返回默认配置

        try:
            with open(config_path, "rb") as f:
                data = toml.load(f)
            return self._parse_toml(data)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            return Settings()

    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        if self.config_path:
            path = Path(self.config_path)
            if path.exists():
                return path

        for candidate in self.DEFAULT_CONFIG_PATHS:
            path = Path(candidate)
            if path.exists():
                return path

        return None

    def _parse_toml(self, data: dict) -> Settings:
        """解析 TOML 数据"""
        return Settings(
            llm=self._parse_llm_config(data.get("llm", {})),
            memory=self._parse_memory_config(data.get("memory", {})),
            docker=self._parse_docker_config(data.get("docker", {})),
            logging=self._parse_logging_config(data.get("logging", {})),
        )

    def _parse_llm_config(self, data: dict) -> LLMConfig:
        """解析 LLM 配置"""
        return LLMConfig(
            model_name=data.get("model_name", "gpt-4"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", "https://api.openai.com/v1"),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            enable_thinking=data.get("enable_thinking", True),
            timeout=data.get("timeout", 120),
        )

    def _parse_memory_config(self, data: dict) -> MemoryConfig:
        """解析内存配置"""
        return MemoryConfig(
            working_memory_max_rounds=data.get("working_memory_max_rounds", 30),
            stm_expiry_days=data.get("stm_expiry_days", 7),
            ltm_auto_distill=data.get("ltm_auto_distill", True),
            working_memory_path=data.get("working_memory_path", "memory/working_memory.md"),
            stm_path=data.get("stm_path", "memory/short_term_memory.md"),
            ltm_path=data.get("ltm_path", "memory/alice_memory.md"),
            todo_path=data.get("todo_path", "memory/todo.md"),
        )

    def _parse_docker_config(self, data: dict) -> DockerConfig:
        """解析 Docker 配置"""
        return DockerConfig(
            image_name=data.get("image_name", "alice-sandbox:latest"),
            container_name=data.get("container_name", "alice-sandbox-instance"),
            work_dir=data.get("work_dir", "/app"),
            mounts=data.get("mounts", {}),
            timeout=data.get("timeout", 120),
        )

    def _parse_logging_config(self, data: dict) -> LoggingConfig:
        """解析日志配置"""
        return LoggingConfig(
            level=data.get("level", "INFO"),
            format=data.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
            file=data.get("file", "alice_runtime.log"),
            enable_colors=data.get("enable_colors", True),
            max_size_mb=data.get("max_size_mb", 10),
            backup_count=data.get("backup_count", 3),
        )

    def _apply_env_vars(self, settings: Settings) -> None:
        """应用环境变量覆盖"""
        # LLM 配置
        if api_key := os.getenv("API_KEY"):
            settings.llm.api_key = api_key
        if base_url := os.getenv("API_BASE_URL"):
            settings.llm.base_url = base_url
        if model_name := os.getenv("MODEL_NAME"):
            settings.llm.model_name = model_name

        # 内存配置
        if max_rounds := os.getenv("WORKING_MEMORY_MAX_ROUNDS"):
            settings.memory.working_memory_max_rounds = int(max_rounds)

        # 日志配置
        if log_level := os.getenv("LOG_LEVEL"):
            settings.logging.level = log_level

    @staticmethod
    def expand_env_vars(value: str) -> str:
        """展开环境变量 ${VAR}"""
        import re

        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        return re.sub(r'\$\{([^}]+)\}', replace_env_var, value)


def load_config(config_path: Optional[str] = None) -> Settings:
    """便捷函数：加载配置"""
    loader = ConfigLoader(config_path)
    return loader.load()
