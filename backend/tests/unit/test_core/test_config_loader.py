"""
ConfigLoader 单元测试

验证 TOML 加载在 Python 3.11+ 环境下可正常工作。
"""

from pathlib import Path
import tempfile
import unittest

from backend.alice.core.config.loader import ConfigLoader


class TestConfigLoader(unittest.TestCase):
    """ConfigLoader 测试"""

    def test_loads_toml_fixture_without_tomli_dependency(self) -> None:
        """在 Python 3.11+ 上应能使用标准库 tomllib 读取 TOML"""
        config_text = """
[llm]
model_name = "gpt-4.1"

[memory]
working_memory_max_rounds = 20

[logging]
level = "DEBUG"
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "alice.toml"
            config_path.write_text(config_text, encoding="utf-8")

            settings = ConfigLoader(str(config_path)).load()

        self.assertEqual(settings.llm.model_name, "gpt-4.1")
        self.assertEqual(settings.memory.working_memory_max_rounds, 20)
        self.assertEqual(settings.logging.level, "DEBUG")


if __name__ == "__main__":
    unittest.main()
