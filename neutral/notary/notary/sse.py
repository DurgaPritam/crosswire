"""Incremental server-sent-events parser (WHATWG event-stream rules, the parts Switch uses)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class Frame:
    event: str
    data: Any            # JSON-decoded data (str if not JSON)
    id: str | None       # SSE id: line (domain events carry the sequence)


class SSEParser:
    def __init__(self) -> None:
        self._buf = ""
        self._event = ""
        self._data: list[str] = []
        self._id: str | None = None

    def feed(self, chunk: str) -> list[Frame]:
        self._buf += chunk
        frames: list[Frame] = []
        while True:
            nl = min((i for i in (self._buf.find("\n"), self._buf.find("\r")) if i != -1), default=-1)
            if nl == -1:
                return frames
            line = self._buf[:nl]
            skip = 2 if self._buf[nl:nl + 2] == "\r\n" else 1
            self._buf = self._buf[nl + skip:]
            frame = self._line(line)
            if frame:
                frames.append(frame)

    def _line(self, line: str) -> Frame | None:
        if line == "":
            if not self._data and not self._event:
                return None
            raw = "\n".join(self._data)
            try:
                data: Any = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                data = raw
            frame = Frame(self._event or "message", data, self._id)
            self._event, self._data, self._id = "", [], None
            return frame
        if line.startswith(":"):          # keepalive comment
            return None
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            self._event = value
        elif field == "data":
            self._data.append(value)
        elif field == "id":
            self._id = value
        return None
