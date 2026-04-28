"""Tests for minimal application package exports."""

from __future__ import annotations

import importlib
import sys


def test_application_package_imports_cleanly() -> None:
    """application 包应能被直接导入，不抛异常。"""
    sys.modules.pop("backend.alice.application", None)
    application_module = importlib.import_module("backend.alice.application")
    assert application_module is not None


def test_submodule_imports_resolve_correctly() -> None:
    """子模块导入应在没有循环依赖的情况下正常解析。"""
    from backend.alice.application.agent import AliceAgent as RealAliceAgent
    from backend.alice.application.workflow import ChatWorkflow as RealChatWorkflow

    assert RealAliceAgent is not None
    assert RealChatWorkflow is not None


def test_legacy_artifacts_are_gone() -> None:
    """旧的 ReAct 相关 artifact 不应存在。"""
    agent_module = importlib.import_module("backend.alice.application.agent")
    assert not hasattr(agent_module, "ReActLoop")
    assert not hasattr(agent_module, "ReActConfig")
    assert not hasattr(agent_module, "ReActState")
