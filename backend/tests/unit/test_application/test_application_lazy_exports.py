"""Tests for lazy exports in backend.alice.application."""

from __future__ import annotations

import importlib
import sys


def test_package_lazy_exports_resolve_real_objects() -> None:
    sys.modules.pop("backend.alice.application", None)
    application_module = importlib.import_module("backend.alice.application")

    assert "AliceAgent" not in application_module.__dict__
    assert "ChatWorkflow" not in application_module.__dict__

    from backend.alice.application import AliceAgent, ChatWorkflow
    from backend.alice.application.agent import AliceAgent as RealAliceAgent
    from backend.alice.application.workflow import ChatWorkflow as RealChatWorkflow

    assert AliceAgent is RealAliceAgent
    assert ChatWorkflow is RealChatWorkflow
