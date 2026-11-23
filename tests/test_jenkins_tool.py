from __future__ import annotations

import asyncio
import json

from core.harness.tools import default_coding_tools
from core.harness.tools.jenkins import JenkinsTool


def _run(coro):
    return asyncio.run(coro)


def test_jenkins_tool_registered():
    registry = default_coding_tools("E:/code/ai/y-ai-deepcode")
    names = sorted(registry._tools.keys())
    assert "jenkins" in names


def test_jenkins_tool_schema():
    tool = JenkinsTool("E:/code/ai/y-ai-deepcode")
    assert tool.name == "jenkins"
    assert tool.read_only is False
    props = tool.parameters["properties"]
    assert set(props) == {"action", "entityId", "build", "parameters"}
    assert props["action"]["enum"] == ["status", "console", "trigger"]


def test_unknown_action_returns_error():
    tool = JenkinsTool("E:/code/ai/y-ai-deepcode")
    result = _run(tool.execute(action="bogus", entityId="product://x"))
    assert result.startswith("error: unknown action")


def test_missing_entity_and_no_bound_layer():
    # No workspace catalog -> no bound layer -> a helpful error, not a crash.
    tool = JenkinsTool(None)
    result = _run(tool.execute(action="status"))
    assert "error:" in result or "entityId" in result


def test_status_never_leaks_token(monkeypatch):
    captured = {}

    def fake_status(entity_id, home=None):
        captured["entity_id"] = entity_id
        captured["home"] = home
        return {
            "job": "litellm",
            "url": "http://jenkins.ops.isigning.com/job/litellm/",
            "building": False,
            "lastBuild": {"number": 1, "result": "SUCCESS"},
        }

    monkeypatch.setattr(
        "core.application.jenkins_service.status", fake_status
    )
    tool = JenkinsTool("E:/code/ai/y-ai-deepcode")
    result = _run(tool.execute(action="status", entityId="product://paas"))
    # The result must not contain any credential.
    assert "token" not in result.lower()
    assert "password" not in result.lower()
    parsed = json.loads(result)
    assert parsed["job"] == "litellm"
    assert captured["entity_id"] == "product://paas"


def test_trigger_passes_parameters(monkeypatch):
    captured = {}

    def fake_trigger(entity_id, params=None, home=None):
        captured["params"] = params
        return {"queued": True, "queueUrl": "http://jenkins/queue/item/1"}

    monkeypatch.setattr(
        "core.application.jenkins_service.trigger", fake_trigger
    )
    tool = JenkinsTool("E:/code/ai/y-ai-deepcode")
    result = _run(
        tool.execute(
            action="trigger",
            entityId="product://paas",
            parameters={"BRANCH": "main", "DEPLOY": "true"},
        )
    )
    assert captured["params"] == {"BRANCH": "main", "DEPLOY": "true"}
    assert "queued" in result


def test_console_build_number(monkeypatch):
    captured = {}

    def fake_console(entity_id, build=None, home=None):
        captured["build"] = build
        return {"build": build, "text": "SUCCESS"}

    monkeypatch.setattr(
        "core.application.jenkins_service.console", fake_console
    )
    tool = JenkinsTool("E:/code/ai/y-ai-deepcode")
    _run(tool.execute(action="console", entityId="product://paas", build=42))
    assert captured["build"] == 42
