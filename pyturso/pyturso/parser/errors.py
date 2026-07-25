"""errors — parse error type with position; maps to OperationalError class.

Ports: sqlite/parser/src/error.rs (``Error`` enum — the lexer/parser errors).
Phase: 3
Status: IMPLEMENTED.

A single :class:`ParseError` carrying the position (byte offset), the token
text that caused the error, and a message. The lexer raises it on malformed
input (unterminated string, bad hex, etc.); the parser raises it on grammar
violations. The differential harness maps it to the same class sqlite3 raises
(``OperationalError``) — that mapping is in ``pyturso.errors``.
"""

from __future__ import annotations

__all__ = ["ParseError"]


class ParseError(Exception):
    """A SQL parse or lex error.

    Attributes:
        message: human-readable error detail.
        offset: byte offset in the source where the error occurred.
        token: the token text (or offending character) that caused the error.
    """

    def __init__(self, message: str, offset: int = 0, token: str = "") -> None:
        self.message: str = message
        self.offset: int = offset
        self.token: str = token
        super().__init__(message)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ParseError({self.message!r}, offset={self.offset}, token={self.token!r})"