"""``jenkins`` — inspect and operate the team layer's configured Jenkins job.

The agent can read a build's status and console output, and queue a build.
Credentials live in ``~/.dfcode/integrations.yaml`` (0600) and are read by the
service layer only — the token is **never** returned to the model. The tool
returns only the outcome (status, log tail, queue location), so the model can
operate the delivery pipeline without ever seeing the credential.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from core.agent_runtime.tools.base import Tool, tool_parameters


@tool_parameters(
    {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "console", "trigger"],
                "description": (
                    "status: the configured job's last build state; console: the "
                    "tail of a build's console output; trigger: queue a new build "
                    "(optionally with parameters)."
                ),
            },
            "entityId": {
                "type": "string",
                "description": (
                    "The team-context entity whose Jenkins integration to use "
                    "(for example product://paas). Defaults to the bound layer."
                ),
            },
            "build": {
                "type": "integer",
                "description": "Build number for console (default: last build).",
            },
            "parameters": {
                "type": "object",
                "description": "Key/value build parameters for trigger.",
            },
        },
        "required": ["action"],
    }
)
class JenkinsTool(Tool):
    """Inspect and operate the team layer's Jenkins delivery job."""

    def __init__(self, workspace, *, home=None) -> None:
        self._workspace = workspace
        self._home = home

    @property
    def name(self) -> str:
        return "jenkins"

    @property
    def description(self) -> str:
        return (
            "Inspect and operate the team layer's Jenkins delivery job. status "
            "reports the last build result and whether a build is running; "
            "console returns the tail of a build's log; trigger queues a new "
            "build (optionally with parameters). Credentials are held by the "
            "service and never returned to you — you only see the outcome."
        )

    @property
    def read_only(self) -> bool:
        # trigger mutates the remote build queue, so the tool is not read-only.
        return False

    def _bound_entity(self, explicit: str | None) -> str:
        if explicit:
            return explicit.strip()
        try:
            from core.team_context.catalog import load_catalog

            catalog = load_catalog(self._workspace, self._home)
            bound = catalog.bind_for(self._workspace) if self._workspace else None
            if not bound:
                raise ValueError("no team-context layer is bound; pass entityId")
            return bound
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"cannot resolve the Jenkins entity: {exc}") from exc

    async def execute(self, **kwargs: Any) -> str:
        action = str(kwargs.get("action") or "status").strip().lower()
        try:
            entity_id = self._bound_entity(kwargs.get("entityId"))
            from core.application.jenkins_service import console, status, trigger

            if action == "status":
                result = await asyncio.to_thread(status, entity_id, self._home)
            elif action == "console":
                build = kwargs.get("build")
                result = await asyncio.to_thread(
                    console, entity_id, int(build) if build else None, self._home
                )
            elif action == "trigger":
                params = kwargs.get("parameters") or {}
                result = await asyncio.to_thread(
                    trigger,
                    entity_id,
                    {str(k): str(v) for k, v in params.items()} if params else None,
                    self._home,
                )
            else:
                return f"error: unknown action {action!r}"
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as exc:  # noqa: BLE001 - a failed call is a result, not a crash
            return f"error: {type(exc).__name__}: {exc}"


__all__ = ["JenkinsTool"]
