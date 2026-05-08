from pathlib import Path

from backend.alice.infrastructure.docker.config import DockerConfig


def test_default_mounts_use_alice_workspace_on_host() -> None:
    config = DockerConfig(project_root=Path("/tmp/alice-project"))

    mounts = config.default_mounts

    assert len(mounts) == 4
    assert mounts[0].host_path == Path("/tmp/alice-project") / "backend" / "alice" / "skills"
    assert mounts[0].container_path == "/app/skills"
    assert mounts[1].host_path == Path("/tmp/alice-project") / ".alice" / "skills"
    assert mounts[1].container_path == "/app/user_skills"
    assert mounts[2].host_path == Path("/tmp/alice-project") / ".alice"
    assert mounts[2].container_path == "/app/.alice"
    assert mounts[3].host_path == Path("/tmp/alice-project") / ".alice" / "workspace"
    assert mounts[3].container_path == "/workspace"
