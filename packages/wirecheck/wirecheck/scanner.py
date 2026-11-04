"""A position-tracking JSON scanner over raw bytes.

Yields every leaf (string, number, true/false/null) with its path and the exact byte
span it occupies in the input, so offsets and lengths describe the bytes as they were
sent or verified, not a re-serialization. String spans include their quotes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

WS = b" \t\r\n"
HEX = b"0123456789abcdefABCDEF"


@dataclass(frozen=True)
class Leaf:
    path: str
    start: int
    end: int          # exclusive
    kind: str         # "string" | "number" | "literal"
    escaped: bool     # the raw slice contains a \\uXXXX escape
    non_ascii: bool   # the decoded value contains non-ASCII characters


class ScanError(ValueError):
    pass


class _Scanner:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.i = 0
        self.leaves: list[Leaf] = []

    def ws(self) -> None:
        while self.i < len(self.raw) and self.raw[self.i] in WS:
            self.i += 1

    def peek(self) -> int:
        if self.i >= len(self.raw):
            raise ScanError(f"unexpected end of input at byte {self.i}")
        return self.raw[self.i]

    def expect(self, ch: bytes) -> None:
        if self.peek() != ch[0]:
            raise ScanError(f"expected {ch!r} at byte {self.i}")
        self.i += 1

    def value(self, path: str) -> None:
        self.ws()
        c = self.peek()
        if c == ord("{"):
            self.obj(path)
        elif c == ord("["):
            self.arr(path)
        elif c == ord('"'):
            start = self.i
            escaped = self.string()
            decoded = json.loads(self.raw[start:self.i])
            self.leaves.append(Leaf(path, start, self.i, "string", escaped, not decoded.isascii()))
        else:
            start = self.i
            while self.i < len(self.raw) and self.raw[self.i] not in b",]} \t\r\n":
                self.i += 1
            token = self.raw[start:self.i]
            try:
                json.loads(token)
            except ValueError as exc:
                raise ScanError(f"bad token at byte {start}") from exc
            kind = "literal" if token in (b"true", b"false", b"null") else "number"
            self.leaves.append(Leaf(path, start, self.i, kind, False, False))

    def string(self) -> bool:
        """Consume a JSON string starting at '"'. Returns True if it holds a \\u escape."""
        self.expect(b'"')
        escaped = False
        while True:
            c = self.peek()
            if c == ord('"'):
                self.i += 1
                return escaped
            if c == ord("\\"):
                nxt = self.raw[self.i + 1:self.i + 2]
                if nxt == b"u":
                    digits = self.raw[self.i + 2:self.i + 6]
                    if len(digits) != 4 or any(d not in HEX for d in digits):
                        raise ScanError(f"bad \\u escape at byte {self.i}")
                    escaped = True
                    self.i += 6
                elif nxt and nxt in b'"\\/bfnrt':
                    self.i += 2
                else:
                    raise ScanError(f"bad escape at byte {self.i}")
            elif c < 0x20:
                raise ScanError(f"control character in string at byte {self.i}")
            else:
                self.i += 1

    def key(self) -> str:
        start = self.i
        self.string()
        return json.loads(self.raw[start:self.i])

    def obj(self, path: str) -> None:
        self.expect(b"{")
        self.ws()
        if self.peek() == ord("}"):
            self.i += 1
            return
        while True:
            self.ws()
            k = self.key()
            self.ws()
            self.expect(b":")
            self.value(f"{path}.{k}" if path else k)
            self.ws()
            if self.peek() == ord(","):
                self.i += 1
                continue
            self.expect(b"}")
            return

    def arr(self, path: str) -> None:
        self.expect(b"[")
        self.ws()
        if self.peek() == ord("]"):
            self.i += 1
            return
        n = 0
        while True:
            self.value(f"{path}[{n}]")
            n += 1
            self.ws()
            if self.peek() == ord(","):
                self.i += 1
                continue
            self.expect(b"]")
            return


def scan(raw: bytes) -> list[Leaf]:
    """Return every leaf of the JSON document in `raw`, in document order."""
    s = _Scanner(raw)
    s.value("")
    s.ws()
    if s.i != len(raw):
        raise ScanError(f"trailing data at byte {s.i}")
    return s.leaves
