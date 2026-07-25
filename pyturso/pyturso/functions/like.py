"""like — LIKE/GLOB pattern matching.

Ports: core/functions/string.rs (LIKE/GLOB implementation).
Phase: 6
Status: IMPLEMENTED (LIKE with % and _ wildcards; GLOB with * and ? wildcards).

SQLite LIKE rules:
  - ``%`` matches zero or more characters.
  - ``_`` matches exactly one character.
  - Case-insensitive by default (ASCII only), unless ``PRAGMA case_sensitive_like = ON``.
  - ``ESCAPE`` clause provides a custom escape character (default: none).

SQLite GLOB rules:
  - ``*`` matches zero or more characters.
  - ``?`` matches exactly one character.
  - ``[...]`` character classes.
  - Case-sensitive.
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="arg-type"

import re

from pyturso.types.value import Value

__all__ = ["like_match", "glob_match"]


def like_match(pattern: str, text: str, case_insensitive: bool = True,
               escape: str | None = None) -> bool:
    """Match ``text`` against LIKE ``pattern``.

    Returns True if the pattern matches. ``%`` = any sequence, ``_`` = one char.
    Case-insensitive by default (ASCII only). The ``escape`` character escapes
    ``%`` and ``_``.
    """
    if case_insensitive:
        pattern = pattern.upper()
        text = text.upper()

    # Build a regex from the LIKE pattern.
    regex_parts: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if escape is not None and ch == escape and i + 1 < n:
            # Escaped char → literal.
            regex_parts.append(re.escape(pattern[i + 1]))
            i += 2
        elif ch == "%":
            regex_parts.append(".*")
            i += 1
        elif ch == "_":
            regex_parts.append(".")
            i += 1
        else:
            regex_parts.append(re.escape(ch))
            i += 1

    regex = "^" + "".join(regex_parts) + "$"
    return bool(re.match(regex, text, re.DOTALL))


def glob_match(pattern: str, text: str) -> bool:
    """Match ``text`` against GLOB ``pattern``. Case-sensitive.

    ``*`` = any sequence, ``?`` = one char, ``[...]`` = character class.
    """
    # GLOB is more complex (character classes); use fnmatch for the common case.
    import fnmatch
    return fnmatch.fnmatchcase(text, pattern)


def like_function(args: list[Value]) -> Value:
    """LIKE function: like(pattern, text[, escape])."""
    pat_v, text_v = args[0], args[1]
    if text_v.is_null or pat_v.is_null:
        return Value.null()
    text = text_v.payload if text_v.is_text else str(text_v.payload)  # type: ignore[union-attr]
    pattern = pat_v.payload if pat_v.is_text else str(pat_v.payload)  # type: ignore[union-attr]
    escape = None
    if len(args) > 2 and not args[2].is_null:
        escape = args[2].payload if args[2].is_text else str(args[2].payload)  # type: ignore[union-attr]
    return Value.integer(1 if like_match(pattern, text, escape=escape) else 0)


def glob_function(args: list[Value]) -> Value:
    """GLOB function: glob(pattern, text)."""
    pat_v, text_v = args[0], args[1]
    if text_v.is_null or pat_v.is_null:
        return Value.null()
    text = text_v.payload if text_v.is_text else str(text_v.payload)  # type: ignore[union-attr]
    pattern = pat_v.payload if pat_v.is_text else str(pat_v.payload)  # type: ignore[union-attr]
    return Value.integer(1 if glob_match(pattern, text) else 0)