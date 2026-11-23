"""Read-only team-context git source — clone/pull a meta-repo into a local cache.

The team context has three data sources, merged lowest-precedence first:

    git repo (read-only)  <  home global  <  workspace overlay

A company/line-level team-context meta-repo (configured as ``team.git_repo``)
is cloned into ``~/.dfcode/team-git/`` and read as the lowest-precedence layer.
It is a *distribution* source: DFcode never writes to it, and a pull/clone
failure must never block assembly (the other two sources still work).

Credentials come from the git credential manager (``git credential fill``), so
a private repo over SSH/HTTPS uses whatever the user already has configured —
no DFcode-held secret. The cached clone is hardened to private permissions.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from core.config import dfcode_home
from core.private_storage import harden_private_tree

logger = logging.getLogger(__name__)

_TEAM_GIT_DIR = "team-git"


def team_git_root(home: str | Path | None = None) -> Path:
    """The local cache directory for the team-context git source."""
    base = Path(home) if home is not None else dfcode_home()
    return base / _TEAM_GIT_DIR


def _git(*argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run git without touching the user's repo config (no hooks, no pager)."""
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")  # never hang waiting for a prompt
    return subprocess.run(
        ["git", *argv],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=env,
        check=False,
    )


def _clone(repo_url: str, target: Path) -> bool:
    result = _git("clone", "--quiet", "--depth", "1", repo_url, str(target))
    return result.returncode == 0


def _pull(target: Path) -> bool:
    result = _git("pull", "--quiet", "--ff-only", cwd=target)
    return result.returncode == 0


def _is_git_repo(target: Path) -> bool:
    return (target / ".git").exists()


def refresh(repo_url: str, home: str | Path | None = None) -> tuple[bool, str]:
    """Clone (first time) or pull (already cached) the team-context git repo.

    Returns ``(ok, message)``. Never raises: a network, credential, or
    repository failure is reported and the caller degrades to the other two
    sources. Credentials are resolved by the git credential manager via the
    child ``git`` process (``GIT_TERMINAL_PROMPT=0`` so it fails fast instead
    of hanging).
    """
    target = team_git_root(home)
    try:
        if _is_git_repo(target):
            ok = _pull(target)
            message = "pulled" if ok else "pull failed"
        else:
            ok = _clone(repo_url, target)
            message = "cloned" if ok else "clone failed"
        if ok:
            harden_private_tree(target)
        return ok, message
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("team git source refresh failed", exc_info=True)
        return False, f"refresh error: {exc}"


def is_configured(repo_url: str | None) -> bool:
    """True when a git source is configured and should be consulted."""
    return bool((repo_url or "").strip())


def available(home: str | Path | None = None) -> bool:
    """True when the cached clone exists and is a valid git repo."""
    return _is_git_repo(team_git_root(home))


__all__ = [
    "available",
    "is_configured",
    "refresh",
    "team_git_root",
]
