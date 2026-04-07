from pathlib import Path

from backend.alice.core.registry.command_registry import InMemoryCommandRegistry


def test_default_harness_prefers_container_runtime() -> None:
    registry = InMemoryCommandRegistry()

    container_spec = registry.get_harness("container")
    docker_spec = registry.get_harness("docker")

    assert container_spec is not None
    assert docker_spec is not None

    bundle = registry.create_harness(project_root=Path("/tmp/alice-project"))

    assert bundle.executor.__class__.__name__ == "DockerExecutor"
    assert bundle.backend.__class__.__name__ == "DockerExecutionBackend"
