from __future__ import annotations

from pathlib import Path

import yaml

from core.harness.tools.shell import BashTool
from core.team_context.service import TeamContextService


def _setup_team_env(ws: Path, *, active: bool = True) -> None:
    team = ws / ".dfcode" / "team"
    project = team / "project" / "changan"
    project.mkdir(parents=True, exist_ok=True)
    (project / "entity.yaml").write_text(
        yaml.safe_dump(
            {"id": "project://changan", "name": "Changan", "workspace": str(ws)}
        ),
        encoding="utf-8",
    )
    envdir = project / "environments"
    envdir.mkdir(parents=True, exist_ok=True)
    (envdir / "dev.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "dev",
                "values": {"DATABASE_URL": "postgres://x", "API_KEY": "secret123"},
            }
        ),
        encoding="utf-8",
    )
    if active:
        (envdir / "active.yaml").write_text(
            yaml.safe_dump({"name": "dev"}), encoding="utf-8"
        )


def test_active_environment_values_resolves_bound_layer(tmp_path):
    ws = tmp_path / "ws"
    home = tmp_path / "home"
    ws.mkdir()
    _setup_team_env(ws)
    service = TeamContextService(ws, home)
    values = service.active_environment_values()
    assert values["DATABASE_URL"] == "postgres://x"
    assert values["API_KEY"] == "secret123"


def test_no_active_environment_is_empty(tmp_path):
    ws = tmp_path / "ws"
    home = tmp_path / "home"
    ws.mkdir()
    _setup_team_env(ws, active=False)
    service = TeamContextService(ws, home)
    assert service.active_environment_values() == {}


def test_unbound_workspace_is_empty(tmp_path):
    ws = tmp_path / "ws"
    home = tmp_path / "home"
    ws.mkdir()
    service = TeamContextService(ws, home)
    assert service.active_environment_values() == {}


def test_bash_extra_env_includes_team_active_env(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    _setup_team_env(ws)
    tool = BashTool(str(ws))
    extra = tool._extra_env()
    assert extra is not None
    assert extra["DATABASE_URL"] == "postgres://x"
    assert extra["API_KEY"] == "secret123"


def test_bash_extra_env_without_team_is_none(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    tool = BashTool(str(ws))
    assert tool._extra_env() is None


def test_read_only_bash_still_sets_bytecode_guard(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    tool = BashTool(str(ws), read_only_workspace=True)
    extra = tool._extra_env()
    assert extra is not None
    assert extra["PYTHONDONTWRITEBYTECODE"] == "1"
