"""Small Mattermost REST client shared by Phase 7 automation and scripts/rehearse.py.

Logins come from the environment or the gitignored crosswire/.env (mode 600). Passwords and
session tokens are never printed or written anywhere else. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DOTENV = ROOT / ".env"


def load_env(path: Path = DOTENV) -> dict[str, str]:
    """KEY=VALUE pairs from .env, without touching os.environ. Values are never printed."""
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            out[k.strip().removeprefix("export ").strip()] = v
    return {**out, **{k: v for k, v in os.environ.items() if k in out or k.startswith(("MM_", "SWITCH_"))}}


def set_env_value(key: str, value: str, path: Path = DOTENV) -> None:
    """Add or replace KEY=value in .env (kept mode 600). The value is never printed."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [l for l in lines if not re.match(rf"^\s*{re.escape(key)}=", l)] + [f"{key}={value}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


class MMError(RuntimeError):
    pass


@dataclass
class Post:
    id: str
    channel_id: str
    user_id: str
    username: str
    override: str
    message: str
    root_id: str
    create_at: int
    edited: bool
    deleted: bool

    @property
    def label(self) -> str:
        return self.override or self.username

    def is_by(self, name: str) -> bool:
        n = name.lstrip("@").lower()
        return n in (self.username.lower(), self.override.lower())


class Mattermost:
    def __init__(self, url: str) -> None:
        self.base = url.rstrip("/") + "/api/v4"
        self.token: str | None = None
        self.me: dict[str, Any] = {}
        self._users: dict[str, str] = {}

    def _req(self, method: str, path: str, body: Any = None, auth: bool = True) -> tuple[Any, dict[str, str]]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if auth and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return (json.loads(raw) if raw else None), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("message", "")
            except Exception:
                detail = ""
            raise MMError(f"{method} {path.split('?')[0]} → HTTP {exc.code} {detail}".strip()) from None
        except urllib.error.URLError as exc:
            raise MMError(f"cannot reach Mattermost at {self.base} ({exc.reason})") from None

    def get(self, path: str) -> Any:
        return self._req("GET", path)[0]

    def post(self, path: str, body: Any, auth: bool = True) -> Any:
        return self._req("POST", path, body, auth)[0]

    def put(self, path: str, body: Any) -> Any:
        return self._req("PUT", path, body)[0]

    def login(self, user: str, password: str) -> "Mattermost":
        try:
            me, headers = self._req("POST", "/users/login", {"login_id": user, "password": password}, auth=False)
        except MMError as exc:
            raise MMError(f"login as {user!r} failed ({exc})") from None
        self.token = headers.get("Token") or headers.get("token")
        if not self.token:
            raise MMError("Mattermost returned no Token header")
        self.me = me
        return self

    # -------------------------------------------------------------- lookups

    def team(self) -> dict[str, Any]:
        teams = self.get("/users/me/teams") or []
        if not teams:
            raise MMError("this account is in no team")
        return teams[0]

    def user_by_name(self, username: str) -> dict[str, Any] | None:
        found = self.post("/users/usernames", [username.lstrip("@")]) or []
        return found[0] if found else None

    def channel(self, team_id: str, name: str) -> dict[str, Any] | None:
        for ch in self.get(f"/users/me/teams/{team_id}/channels") or []:
            if name in (ch["name"], ch.get("display_name")):
                return ch
        return None

    def username(self, user_id: str) -> str:
        if user_id not in self._users:
            for u in self.post("/users/ids", [user_id]) or []:
                self._users[u["id"]] = u["username"]
        return self._users.get(user_id, user_id)

    # -------------------------------------------------------------- writes

    def send(self, channel_id: str, message: str, root_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"channel_id": channel_id, "message": message}
        if root_id:
            body["root_id"] = root_id
        return self.post("/posts", body)

    # -------------------------------------------------------------- reads

    def posts_since(self, channel_id: str, since_ms: int) -> list[Post]:
        data = self.get(f"/channels/{channel_id}/posts?since={since_ms}&collapsedThreads=false") or {}
        out = []
        for raw in (data.get("posts") or {}).values():
            if raw.get("type", "").startswith("system_"):
                continue
            props = raw.get("props") or {}
            out.append(Post(raw["id"], raw["channel_id"], raw["user_id"], self.username(raw["user_id"]),
                            str(props.get("override_username") or ""), raw.get("message", ""), raw.get("root_id", ""),
                            raw["create_at"], bool(raw.get("edit_at")), bool(raw.get("delete_at"))))
        return sorted(out, key=lambda p: p.create_at)

    def wait(self, channel_ids: list[str], since_ms: int, done: Callable[[list[Post]], bool], timeout: float = 180,
             poll: float = 5, quiet: float = 15, exclude: set[str] | None = None,
             on_new: Callable[[Post], None] | None = None) -> list[Post]:
        """Collect posts (thread + top-level, edits included) until done(posts) holds and nothing changed for
        `quiet` seconds, or `timeout`. `exclude` = post ids to ignore (our own)."""
        exclude = exclude or set()
        seen: dict[str, Post] = {}
        start = last = time.monotonic()
        while True:
            for cid in channel_ids:
                for p in self.posts_since(cid, since_ms - 1):
                    if p.id in exclude or p.create_at < since_ms:
                        continue
                    old = seen.get(p.id)
                    if old and old.deleted and not p.message:
                        p.message = old.message
                    if old is None or old.message != p.message or old.deleted != p.deleted:
                        seen[p.id] = p
                        last = time.monotonic()
                        if on_new:
                            on_new(p)
            posts = sorted(seen.values(), key=lambda p: p.create_at)
            now = time.monotonic()
            if (done(posts) and now - last >= quiet) or now - start >= timeout:
                return posts
            time.sleep(poll)


STARTING_RE = re.compile(r"^\W*(starting (a )?session|\*\*work(ing|ed))", re.I)


def real(posts: list[Post], author: str | None = None) -> list[Post]:
    """Posts with actual content (not progress cards or 'Starting a session…'), optionally by one author."""
    return [p for p in posts if p.message.strip() and not STARTING_RE.match(p.message)
            and (author is None or p.is_by(author))]


def admin_client(env: dict[str, str] | None = None) -> Mattermost:
    env = env or load_env()
    missing = [k for k in ("MM_URL", "MM_USER", "MM_PASSWORD") if not env.get(k)]
    if missing:
        raise MMError(f"{missing} not set in .env")
    return Mattermost(env["MM_URL"]).login(env["MM_USER"], env["MM_PASSWORD"])
