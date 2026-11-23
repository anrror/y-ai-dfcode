from __future__ import annotations

from pathlib import Path

import yaml

from core.team_context.catalog import load_catalog
from core.team_context.git_source import (
    available,
    is_configured,
    refresh,
    team_git_root,
)


def _write_layer(root: Path, kind_dir: str, slug: str, entity: dict) -> Path:
    d = root / kind_dir / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "entity.yaml").write_text(
        yaml.safe_dump(entity, allow_unicode=True), encoding="utf-8"
    )
    return d


def _write_knowledge(d: Path, entry_id: str, scope: str, type_: str, statement: str, **extra):
    path = d / "knowledge.yaml"
    items = []
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        items = loaded if isinstance(loaded, list) else [loaded]
    items.append({"id": entry_id, "scope": scope, "type": type_, "statement": statement, **extra})
    path.write_text(yaml.safe_dump(items, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# is_configured / team_git_root
# ---------------------------------------------------------------------------


def test_is_configured():
    assert is_configured("git@github.com:acme/team.git") is True
    assert is_configured(None) is False
    assert is_configured("") is False
    assert is_configured("   ") is False


def test_team_git_root(tmp_path):
    assert team_git_root(tmp_path) == tmp_path / "team-git"


# ---------------------------------------------------------------------------
# load_catalog reads the git cache at lowest precedence
# ---------------------------------------------------------------------------


def test_git_cache_is_read_and_lowest_precedence(tmp_path):
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    git_cache = home / "team-git"
    home_team = home / ".dfcode" / "team"
    ws_team = ws / ".dfcode" / "team"

    # Git cache: an org with a red line.
    org_git = _write_layer(
        git_cache, "company", "default",
        {"id": "org://auto-sub", "name": "Auto Sub"},
    )
    _write_knowledge(org_git, "git-red", "org://auto-sub", "redline", "GIT red line", status="reviewed")

    # Home global: same org id, different knowledge.
    org_home = _write_layer(
        home_team, "company", "default",
        {"id": "org://auto-sub", "name": "Auto Sub"},
    )
    _write_knowledge(org_home, "home-fact", "org://auto-sub", "decision", "HOME fact", status="reviewed")

    # Workspace: a project that binds to a task.
    _write_layer(
        ws_team, "task", "LEAD-1",
        {"id": "task://LEAD-1", "name": "Task", "workspace": str(ws)},
    )

    catalog = load_catalog(ws, home)

    # All three sources merged.
    assert "org://auto-sub" in catalog.entities
    assert "task://LEAD-1" in catalog.entities
    # Both the git red line and the home fact are present.
    assert "git-red" in catalog.knowledge
    assert "home-fact" in catalog.knowledge
    # The workspace binds to the task.
    assert catalog.bind_for(ws) == "task://LEAD-1"


def test_no_git_cache_is_fine(tmp_path):
    home = tmp_path / "home"
    ws = tmp_path / "ws"
    # No team-git directory at all — must not break load_catalog.
    catalog = load_catalog(ws, home)
    assert catalog.entities == {}


# ---------------------------------------------------------------------------
# refresh degrades gracefully (no network, no hang)
# ---------------------------------------------------------------------------


def test_refresh_unreachable_repo_returns_false_not_raise(tmp_path, monkeypatch):
    # Point at a repo URL that cannot exist so clone fails fast. GIT_TERMINAL_PROMPT=0
    # is set inside _git, so this must not hang.
    ok, message = refresh("https://example.invalid/team.git", home=tmp_path)
    assert ok is False
    assert message  # a non-empty failure message


def test_refresh_marks_available_only_on_success(tmp_path):
    assert available(tmp_path) is False
    # A refresh failure must not create a broken cache dir that `available` sees.
    refresh("https://example.invalid/team.git", home=tmp_path)
    assert available(tmp_path) is False
