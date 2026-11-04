from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from notary.register import register, registration_body


def transport(status: int, seen: list[httpx.Request], health: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(health, json={"status": "ok"})
        seen.append(request)
        return httpx.Response(status, json={"id": "agent-123", "api_key": "sk-once"} if status == 200 else {"detail": "x"})
    return httpx.MockTransport(handler)


def test_registers_always_on_via_post_agents() -> None:
    seen: list[httpx.Request] = []
    creds = asyncio.run(register("http://bridge.test", "reg-token", False, transport(200, seen)))
    assert creds["id"] == "agent-123" and creds["api_key"] == "sk-once" and creds["bridge_url"] == "http://bridge.test"
    req = seen[0]
    assert req.url.path == "/agents" and req.headers["Authorization"] == "Bearer reg-token"
    body = json.loads(req.content)
    assert body["name"] == "notary" and body["integration_profile"]["connection_model"] == "always_on"
    assert body["overwrite"] is False


def test_conflict_and_wrong_base_url_fail_loudly() -> None:
    with pytest.raises(SystemExit, match="already exists"):
        asyncio.run(register("http://bridge.test", "t", False, transport(409, [])))
    with pytest.raises(SystemExit, match="not the agent bridge"):
        asyncio.run(register("http://gateway.test", "t", False, transport(200, [], health=404)))


def test_name_matches_switch_rules() -> None:
    import re
    assert re.fullmatch(r"[a-z0-9][a-z0-9._-]*", registration_body(False)["name"])
