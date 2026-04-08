from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.alice.core.config.settings import (
    HarnessConfig,
    LLMConfig,
    MemoryConfig,
    Settings,
    WorkflowConfig,
)


def test_create_from_settings_forwards_runtime_config() -> None:
    from backend.alice.application.services.orchestration_service import OrchestrationService

    settings = Settings(
        project_root=Path("/tmp/alice-project"),
        llm=LLMConfig(
            api_key="test-key",
            base_url="https://example.com/v1",
            model_name="gpt-4.1",
            provider_name="openai",
            request_header_profiles=[{"X-Test": "1"}],
        ),
        workflow=WorkflowConfig(max_history=77),
        memory=MemoryConfig(
            prompt_path=".alice/prompt/prompt.xml",
            working_memory_path=".alice/memory/working_memory.md",
            stm_path=".alice/memory/short_term_memory.md",
            ltm_path=".alice/memory/alice_memory.md",
            todo_path=".alice/memory/todo.md",
            max_rounds=15,
            stm_days_to_keep=9,
        ),
        harness=HarnessConfig(name="docker", skill_source_name="repo-skills"),
    )

    captured: dict[str, object] = {}

    def fake_create_from_config(_cls, **kwargs):
        captured.update(kwargs)
        return "orchestration"

    with patch.object(OrchestrationService, "create_from_config", classmethod(fake_create_from_config)):
        result = OrchestrationService.create_from_settings(settings, extra_headers={"X-Extra": "1"})

    assert result == "orchestration"
    assert captured == {
        "api_key": "test-key",
        "base_url": "https://example.com/v1",
        "model_name": "gpt-4.1",
        "project_root": Path("/tmp/alice-project"),
        "prompt_path": ".alice/prompt/prompt.xml",
        "working_memory_path": ".alice/memory/working_memory.md",
        "stm_path": ".alice/memory/short_term_memory.md",
        "ltm_path": ".alice/memory/alice_memory.md",
        "todo_path": ".alice/memory/todo.md",
        "max_working_rounds": 15,
        "stm_days_to_keep": 9,
        "extra_headers": {"X-Extra": "1"},
        "request_header_profiles": [{"X-Test": "1"}],
        "capabilities": None,
        "provider_name": "openai",
        "skill_source_name": "repo-skills",
        "harness_name": "docker",
        "max_history": 77,
    }
