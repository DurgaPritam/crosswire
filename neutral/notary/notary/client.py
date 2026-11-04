"""HTTP side of the Switch agent protocol: health probe, operations, heartbeat, stream URL."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

CLIENT_NAME = "crosswire-notary"
CLIENT_VERSION = "0.1.0"
# Declared explicitly (negotiation is by overlap). Revision 1 is the SSE contract the docs
# describe; later revisions add the connection incarnation fence and frames we don't need.
PROTOCOL = 1
PROTOCOL_ACCEPTS = 1
REQUIRED_OPS = ("read_context", "post_message", "connect_to_room")


class SwitchError(RuntimeError):
    pass


class ConnectionLost(SwitchError):
    """The server says the connection is dead or has no stream: reopen, don't back off."""


class SwitchClient:
    def __init__(self, base_url: str, agent_id: str, api_key: str, connection_id: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.agent_id = agent_id
        self.connection_id = connection_id
        self.http = httpx.AsyncClient(base_url=self.base, transport=transport, timeout=httpx.Timeout(30, read=None),
                                      headers={"Authorization": f"Bearer {api_key}"})
        self.ops: dict[str, Any] = {}

    async def aclose(self) -> None:
        await self.http.aclose()

    async def probe(self) -> None:
        """GET /health is public and is the probe for 'is this the bridge base URL'."""
        try:
            r = await self.http.get("/health")
        except httpx.HTTPError as exc:
            raise SwitchError(f"cannot reach the Switch bridge at {self.base} ({exc})") from exc
        if r.status_code != 200:
            hint = "right host, wrong path" if r.status_code == 401 else "is this the Gateway URL rather than the bridge?"
            raise SwitchError(f"GET {self.base}/health returned {r.status_code}: {hint}")

    async def discover_ops(self) -> dict[str, Any]:
        r = await self.http.get(f"/agents/{self.agent_id}/ops")
        if r.status_code != 200:
            raise SwitchError(f"GET /agents/{{id}}/ops returned {r.status_code}: {r.text[:200]}")
        self.ops = r.json()["operations"]
        missing = [op for op in REQUIRED_OPS if op not in self.ops]
        if missing:
            raise SwitchError(f"server does not offer required operation(s) {missing}")
        return self.ops

    async def op(self, name: str, **args: Any) -> Any:
        r = await self.http.post(f"/agents/{self.agent_id}/ops/{name}", json=args,
                                 headers={"X-Switch-Connection-Id": self.connection_id})
        if r.status_code == 409:
            raise ConnectionLost(f"{name}: connection unknown or dead (409)")
        if r.status_code != 200:
            raise SwitchError(f"{name} returned {r.status_code}: {r.text[:300]}")
        return r.json().get("result")

    async def beat(self, cursor: int | None) -> dict[str, Any]:
        r = await self.http.post(f"/agents/{self.agent_id}/connection/beat",
                                 json={"connection_id": self.connection_id, "cursor": cursor})
        if r.status_code in (404, 409):
            raise ConnectionLost(f"heartbeat refused ({r.status_code}): reopen the stream")
        if r.status_code != 200:
            raise SwitchError(f"heartbeat returned {r.status_code}: {r.text[:200]}")
        return r.json()

    def events_path(self, cursor: int | None) -> str:
        params: dict[str, Any] = {
            "connection_id": self.connection_id, "scope": "all", "filter": "addressed",
            "protocol": PROTOCOL, "protocol_accepts": PROTOCOL_ACCEPTS,
            "client": CLIENT_NAME, "client_version": CLIENT_VERSION,
        }
        if cursor is None:
            params["start_from"] = "head"   # first start: don't replay history
        return f"/agents/{self.agent_id}/events?{urlencode(params)}"

    def stream(self, cursor: int | None) -> Any:
        headers = {"Accept": "text/event-stream"}
        if cursor is not None:
            headers["Last-Event-ID"] = str(cursor)
        return self.http.stream("GET", self.events_path(cursor), headers=headers)
