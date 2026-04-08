"""ConfigLoader 单元测试。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.alice.core.config.loader import ConfigLoader, build_default_config_data


class TestConfigLoader(unittest.TestCase):
    """ConfigLoader 测试"""

    def test_loads_json_config_from_explicit_path(self) -> None:
        """应能从显式 .alice/config.json 读取运行时配置。"""
        config_data = {
            "llm": {
                "model_name": "gpt-4.1",
                "api_key": "test-key",
                "base_url": "https://example.com/v1",
                "provider_name": "openai",
                "request_header_profiles": [{"X-Test": "1"}],
                "supports_tool_calling": False,
            },
            "workflow": {
                "max_iterations": 12,
                "max_history": 80,
            },
            "memory": {
                "prompt_path": ".alice/prompt/prompt.xml",
                "working_memory_path": ".alice/memory/working_memory.md",
                "stm_path": ".alice/memory/short_term_memory.md",
                "ltm_path": ".alice/memory/alice_memory.md",
                "todo_path": ".alice/memory/todo.md",
                "max_rounds": 20,
                "stm_days_to_keep": 14,
            },
            "harness": {"name": "docker"},
            "logging": {
                "console_level": "DEBUG",
                "logs_dir": ".alice/logs",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".alice"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.json"
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            with patch.dict(os.environ, {}, clear=False):
                for key in ("API_KEY", "API_BASE_URL", "MODEL_NAME", "PROVIDER_NAME"):
                    os.environ.pop(key, None)
                settings = ConfigLoader(str(config_path)).load()

        self.assertEqual(settings.llm.model_name, "gpt-4.1")
        self.assertEqual(settings.llm.api_key, "test-key")
        self.assertEqual(settings.llm.base_url, "https://example.com/v1")
        self.assertEqual(settings.llm.provider_name, "openai")
        self.assertEqual(settings.llm.request_header_profiles, [{"X-Test": "1"}])
        self.assertFalse(settings.llm.supports_tool_calling)
        self.assertEqual(settings.workflow.max_iterations, 12)
        self.assertEqual(settings.workflow.max_history, 80)
        self.assertEqual(settings.memory.prompt_path, ".alice/prompt/prompt.xml")
        self.assertEqual(settings.memory.max_rounds, 20)
        self.assertEqual(settings.memory.stm_days_to_keep, 14)
        self.assertEqual(settings.harness.name, "docker")
        self.assertEqual(settings.logging.console_level, "DEBUG")

    def test_defaults_to_alice_directory_when_config_missing(self) -> None:
        """缺失配置文件时应回退到 .alice 目录约定默认值。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ConfigLoader(str(Path(temp_dir) / ".alice" / "config.json")).load()

        self.assertEqual(settings.config_path, ".alice/config.json")
        self.assertEqual(settings.memory.prompt_path, ".alice/prompt/prompt.xml")
        self.assertEqual(settings.memory.working_memory_path, ".alice/memory/working_memory.md")
        self.assertEqual(settings.memory.stm_path, ".alice/memory/short_term_memory.md")
        self.assertEqual(settings.memory.ltm_path, ".alice/memory/alice_memory.md")
        self.assertEqual(settings.memory.todo_path, ".alice/memory/todo.md")
        self.assertEqual(settings.harness.name, "container")
        self.assertEqual(settings.logging.logs_dir, ".alice/logs")
        self.assertEqual(settings.output_dir, ".alice/workspace")
        self.assertEqual(
            settings.docker.mounts,
            {
                "skills": "/app/skills",
                ".alice": "/app/.alice",
                ".alice/workspace": "/workspace",
            },
        )

    def test_build_default_config_data_uses_runtime_defaults(self) -> None:
        """默认配置序列化应保留 .alice 运行时路径约定。"""
        config_data = build_default_config_data("/tmp/example/.alice/config.json")

        self.assertEqual(config_data["memory"]["prompt_path"], ".alice/prompt/prompt.xml")
        self.assertEqual(config_data["memory"]["working_memory_path"], ".alice/memory/working_memory.md")
        self.assertEqual(config_data["memory"]["stm_path"], ".alice/memory/short_term_memory.md")
        self.assertEqual(config_data["memory"]["ltm_path"], ".alice/memory/alice_memory.md")
        self.assertEqual(config_data["memory"]["todo_path"], ".alice/memory/todo.md")
        self.assertEqual(config_data["harness"]["name"], "container")
        self.assertEqual(
            config_data["docker"]["mounts"],
            {
                "skills": "/app/skills",
                ".alice": "/app/.alice",
                ".alice/workspace": "/workspace",
            },
        )
        self.assertEqual(config_data["logging"]["logs_dir"], ".alice/logs")
        self.assertEqual(config_data["output_dir"], ".alice/workspace")

    def test_json_config_is_not_overridden_by_env(self) -> None:
        """运行时配置应只来自 JSON，不应再被环境变量覆盖。"""
        config_data = {
            "llm": {
                "model_name": "gpt-4.1",
                "api_key": "json-key",
                "base_url": "https://json.example/v1",
                "provider_name": "openai",
            },
            "memory": {
                "max_rounds": 20,
            },
            "logging": {
                "level": "INFO",
                "logs_dir": ".alice/logs",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".alice"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.json"
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "API_KEY": "env-key",
                    "API_BASE_URL": "https://env.example/v1",
                    "MODEL_NAME": "env-model",
                    "PROVIDER_NAME": "env-provider",
                    "WORKING_MEMORY_MAX_ROUNDS": "99",
                    "LOG_LEVEL": "DEBUG",
                    "LOGS_DIR": "env-logs",
                },
                clear=False,
            ):
                settings = ConfigLoader(str(config_path)).load()

        self.assertEqual(settings.llm.api_key, "json-key")
        self.assertEqual(settings.llm.base_url, "https://json.example/v1")
        self.assertEqual(settings.llm.model_name, "gpt-4.1")
        self.assertEqual(settings.llm.provider_name, "openai")
        self.assertEqual(settings.memory.max_rounds, 20)
        self.assertEqual(settings.logging.level, "INFO")
        self.assertEqual(settings.logging.logs_dir, ".alice/logs")

    def test_rejects_legacy_runtime_prompt_path(self) -> None:
        """旧的 .alice/prompt.xml 已废弃，应显式报错。"""
        config_data = {
            "memory": {
                "prompt_path": ".alice/prompt.xml",
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".alice"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.json"
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                r"memory\.prompt_path 已废弃旧值 \.alice/prompt\.xml，请改为 \.alice/prompt/prompt\.xml",
            ):
                ConfigLoader(str(config_path)).load()
