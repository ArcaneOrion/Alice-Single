from __future__ import annotations

import json
from types import SimpleNamespace

from backend.alice.core.config.settings import HarnessConfig, LLMConfig, MemoryConfig, Settings, WorkflowConfig
from backend.alice.domain.llm.providers.base import ProviderCapability


def test_ensure_runtime_scaffold_creates_runtime_files(tmp_path) -> None:
    from backend.alice.cli import bootstrap

    project_root = tmp_path
    (project_root / "prompts").mkdir()
    (project_root / "prompts" / "01_identity.xml").write_text("<identity>Identity</identity>\n", encoding="utf-8")
    (project_root / "prompts" / "02_principles.xml").write_text(
        "<principles>Principles</principles>\n", encoding="utf-8"
    )
    (project_root / "prompts" / "03_memory.xml").write_text("<memory>Memory</memory>\n", encoding="utf-8")
    (project_root / "prompts" / "04_tools.xml").write_text("<tools>Tools</tools>\n", encoding="utf-8")
    (project_root / "prompts" / "05_output.xml").write_text("<output>Output</output>\n", encoding="utf-8")

    bootstrap.ensure_runtime_scaffold(project_root=project_root)

    config_path = project_root / ".alice" / "config.json"
    prompt_path = project_root / ".alice" / "prompt.xml"
    working_memory_path = project_root / ".alice" / "memory" / "working_memory.md"
    stm_path = project_root / ".alice" / "memory" / "short_term_memory.md"
    ltm_path = project_root / ".alice" / "memory" / "alice_memory.md"
    todo_path = project_root / ".alice" / "memory" / "todo.md"

    assert config_path.exists()
    assert json.loads(config_path.read_text(encoding="utf-8"))["memory"]["todo_path"] == ".alice/memory/todo.md"
    assert prompt_path.read_text(encoding="utf-8") == (
        "<system_prompt>\n"
        "<identity>Identity</identity>\n"
        "<principles>Principles</principles>\n"
        "<memory>Memory</memory>\n"
        "<tools>Tools</tools>\n"
        "<output>Output</output>\n"
        "</system_prompt>\n"
    )
    assert working_memory_path.read_text(encoding="utf-8") == "# Alice 的即时对话背景 (Working Memory)\n\n"
    assert stm_path.read_text(encoding="utf-8") == "# Alice 的短期记忆 (最近 7 天)\n\n"
    assert ltm_path.read_text(encoding="utf-8") == "# Alice 的长期记忆\n"
    assert todo_path.read_text(encoding="utf-8") == "# Alice 的任务清单\n\n"


def test_ensure_runtime_scaffold_does_not_overwrite_existing_files(tmp_path) -> None:
    from backend.alice.cli import bootstrap

    project_root = tmp_path
    (project_root / "prompts").mkdir()
    (project_root / "prompts" / "01_identity.xml").write_text("<identity>Identity</identity>\n", encoding="utf-8")
    (project_root / "prompts" / "02_principles.xml").write_text(
        "<principles>Principles</principles>\n", encoding="utf-8"
    )
    (project_root / "prompts" / "03_memory.xml").write_text("<memory>Memory</memory>\n", encoding="utf-8")
    (project_root / "prompts" / "04_tools.xml").write_text("<tools>Tools</tools>\n", encoding="utf-8")
    (project_root / "prompts" / "05_output.xml").write_text("<output>Output</output>\n", encoding="utf-8")
    runtime_dir = project_root / ".alice"
    memory_dir = runtime_dir / "memory"
    memory_dir.mkdir(parents=True)

    (runtime_dir / "config.json").write_text('{"memory":{"todo_path":"custom/todo.md"}}\n', encoding="utf-8")
    (runtime_dir / "prompt.xml").write_text("<system_prompt>custom prompt</system_prompt>\n", encoding="utf-8")
    (memory_dir / "working_memory.md").write_text("custom working\n", encoding="utf-8")
    (memory_dir / "short_term_memory.md").write_text("custom stm\n", encoding="utf-8")
    (memory_dir / "alice_memory.md").write_text("custom ltm\n", encoding="utf-8")
    (memory_dir / "todo.md").write_text("custom todo\n", encoding="utf-8")

    bootstrap.ensure_runtime_scaffold(project_root=project_root)

    assert (runtime_dir / "config.json").read_text(encoding="utf-8") == '{"memory":{"todo_path":"custom/todo.md"}}\n'
    assert (runtime_dir / "prompt.xml").read_text(encoding="utf-8") == "<system_prompt>custom prompt</system_prompt>\n"
    assert (memory_dir / "working_memory.md").read_text(encoding="utf-8") == "custom working\n"
    assert (memory_dir / "short_term_memory.md").read_text(encoding="utf-8") == "custom stm\n"
    assert (memory_dir / "alice_memory.md").read_text(encoding="utf-8") == "custom ltm\n"
    assert (memory_dir / "todo.md").read_text(encoding="utf-8") == "custom todo\n"


def test_create_agent_from_env_ignores_request_header_profiles_env(monkeypatch) -> None:
    from backend.alice.cli import bootstrap

    settings = Settings(
        llm=LLMConfig(
            api_key="test-key",
            model_name="gpt-4.1",
            base_url="https://example.com/v1",
            provider_name="openai",
            request_header_profiles=[{"X-Base": "1"}],
        ),
        workflow=WorkflowConfig(max_iterations=23, max_history=81),
        memory=MemoryConfig(prompt_path=".alice/prompt.xml"),
        harness=HarnessConfig(name="docker", skill_source_name="default"),
    )

    monkeypatch.setattr(bootstrap, "load_config", lambda: settings)
    monkeypatch.setenv("REQUEST_HEADER_PROFILES", '[{"X-Env":"1"}]')

    class _Registry:
        def resolve_request_header_profiles(self, provider_name, base_url, profiles):
            return profiles

    monkeypatch.setattr(bootstrap, "get_llm_registry", lambda: _Registry())
    monkeypatch.setattr(
        bootstrap.OrchestrationService,
        "create_from_settings",
        staticmethod(
            lambda settings_arg, *, capabilities=None, extra_headers=None: SimpleNamespace(
                chat_service="chat-service",
                execution_service="execution-service",
                tool_registry="tool-registry",
                function_calling_orchestrator="tool-orchestrator",
                harness_bundle=SimpleNamespace(backend="backend-instance"),
            )
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "LifecycleService",
        lambda *, project_root, backend: SimpleNamespace(project_root=project_root, backend=backend),
    )

    class _WorkflowChain:
        def add_workflow(self, workflow):
            self.workflow = workflow

    monkeypatch.setattr(bootstrap, "WorkflowChain", _WorkflowChain)
    monkeypatch.setattr(bootstrap, "ChatWorkflow", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(bootstrap, "AliceAgent", lambda **kwargs: SimpleNamespace(**kwargs))

    bootstrap.create_agent_from_env(project_root=settings.project_root)

    assert settings.llm.request_header_profiles == [{"X-Base": "1"}]


def test_create_agent_from_env_reports_missing_config(monkeypatch) -> None:
    from backend.alice.cli import bootstrap

    settings = Settings(
        llm=LLMConfig(api_key="", model_name=""),
        workflow=WorkflowConfig(),
        memory=MemoryConfig(),
        harness=HarnessConfig(),
    )

    monkeypatch.setattr(bootstrap, "load_config", lambda: settings)

    class _Registry:
        def resolve_request_header_profiles(self, provider_name, base_url, profiles):
            return profiles

    monkeypatch.setattr(bootstrap, "get_llm_registry", lambda: _Registry())

    try:
        bootstrap.create_agent_from_env(project_root=settings.project_root)
    except ValueError as exc:
        assert str(exc) == "LLM 配置缺少 api_key"
    else:
        raise AssertionError("expected ValueError")


def test_create_agent_from_env_builds_workflow_from_settings(monkeypatch) -> None:
    from backend.alice.cli import bootstrap

    settings = Settings(
        llm=LLMConfig(
            api_key="test-key",
            model_name="gpt-4.1",
            base_url="https://example.com/v1",
            provider_name="openai",
            request_header_profiles=[{"X-Base": "1"}],
            supports_tool_calling=False,
        ),
        workflow=WorkflowConfig(max_iterations=23, max_history=81),
        memory=MemoryConfig(prompt_path=".alice/prompt.xml"),
        harness=HarnessConfig(name="docker", skill_source_name="default"),
    )

    orchestration_calls: dict[str, object] = {}
    workflow_kwargs: dict[str, object] = {}
    lifecycle_kwargs: dict[str, object] = {}
    agent_kwargs: dict[str, object] = {}

    monkeypatch.setattr(bootstrap, "load_config", lambda: settings)

    class _Registry:
        def resolve_request_header_profiles(self, provider_name, base_url, profiles):
            assert provider_name == "openai"
            assert base_url == "https://example.com/v1"
            return profiles + [{"X-Resolved": "1"}]

    monkeypatch.setattr(bootstrap, "get_llm_registry", lambda: _Registry())

    def fake_create_from_settings(settings_arg, *, capabilities=None, extra_headers=None):
        orchestration_calls["settings"] = settings_arg
        orchestration_calls["capabilities"] = capabilities
        orchestration_calls["extra_headers"] = extra_headers
        return SimpleNamespace(
            chat_service="chat-service",
            execution_service="execution-service",
            tool_registry="tool-registry",
            function_calling_orchestrator="tool-orchestrator",
            harness_bundle=SimpleNamespace(backend="backend-instance"),
        )

    monkeypatch.setattr(
        bootstrap.OrchestrationService,
        "create_from_settings",
        staticmethod(fake_create_from_settings),
    )

    class _LifecycleService:
        def __init__(self, *, project_root, backend):
            lifecycle_kwargs["project_root"] = project_root
            lifecycle_kwargs["backend"] = backend

    monkeypatch.setattr(bootstrap, "LifecycleService", _LifecycleService)

    class _WorkflowChain:
        def __init__(self):
            self.workflows = []

        def add_workflow(self, workflow):
            self.workflows.append(workflow)

    monkeypatch.setattr(bootstrap, "WorkflowChain", _WorkflowChain)

    def fake_chat_workflow(**kwargs):
        workflow_kwargs.update(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(bootstrap, "ChatWorkflow", fake_chat_workflow)

    class _AliceAgent:
        def __init__(self, **kwargs):
            agent_kwargs.update(kwargs)

    monkeypatch.setattr(bootstrap, "AliceAgent", _AliceAgent)

    project_root = settings.project_root
    bootstrap.create_agent_from_env(
        project_root=project_root,
        harness_name="sandbox-harness",
        skill_source_name="repo-skills",
    )

    assert settings.harness.name == "sandbox-harness"
    assert settings.harness.skill_source_name == "repo-skills"
    assert settings.llm.request_header_profiles == [{"X-Base": "1"}, {"X-Resolved": "1"}]
    assert orchestration_calls["settings"] is settings
    assert orchestration_calls["extra_headers"] is None
    capabilities = orchestration_calls["capabilities"]
    assert isinstance(capabilities, ProviderCapability)
    assert capabilities.supports_tool_calling is False
    assert workflow_kwargs["max_iterations"] == 23
    assert lifecycle_kwargs["project_root"] == project_root
    assert lifecycle_kwargs["backend"] == "backend-instance"
    orchestration = agent_kwargs["orchestration_service"]
    assert isinstance(orchestration, SimpleNamespace)
    assert orchestration.chat_service == "chat-service"
