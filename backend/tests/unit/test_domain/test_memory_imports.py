"""
Memory domain 导入测试

确保记忆服务模块在当前依赖图下可正常导入。
"""

import importlib
import unittest
from types import SimpleNamespace

from backend.alice.domain.memory.services.distiller import Distiller


class TestMemoryImports(unittest.TestCase):
    """Memory domain 导入测试"""

    def test_distiller_module_imports(self) -> None:
        """Distiller 模块应可被导入"""
        module = importlib.import_module("backend.alice.domain.memory.services.distiller")
        self.assertTrue(hasattr(module, "Distiller"))

    def test_distiller_uses_provider_extra_headers(self) -> None:
        """记忆提炼请求应沿用 provider 的额外请求头策略"""

        class FakeCompletions:
            def __init__(self) -> None:
                self.last_kwargs: dict | None = None

            def create(self, **kwargs):
                self.last_kwargs = kwargs
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="提炼总结")
                        )
                    ]
                )

        class FakeProvider:
            def __init__(self) -> None:
                self.model_name = "test-model"
                self.completions = FakeCompletions()
                self.client = SimpleNamespace(
                    chat=SimpleNamespace(completions=self.completions)
                )
                self.extra_headers_calls = 0

            def _get_extra_headers(self) -> dict[str, str]:
                self.extra_headers_calls += 1
                return {"User-Agent": "curl/8.0.0", "X-Test": "1"}

        provider = FakeProvider()
        distiller = Distiller(llm_provider=provider)

        result = distiller.distill_stm("过期记忆")

        self.assertTrue(result["success"])
        self.assertEqual(provider.extra_headers_calls, 1)
        assert provider.completions.last_kwargs is not None
        self.assertEqual(
            provider.completions.last_kwargs["extra_headers"],
            {"User-Agent": "curl/8.0.0", "X-Test": "1"},
        )


if __name__ == "__main__":
    unittest.main()
