"""sqlsplit — split a SQL script into statements (quote/comment aware).

Ports: (no Rust counterpart — harness infrastructure; mirrors the statement
boundary rules every SQLite tokenizer uses, per the SQLite file format /
lexer grammar in ``sqlite/parser/src/lexer.rs``).
Phase: 0
Status: IMPLEMENTED.

The differential harness compares engines *per statement*, so all three
adapters must agree on where one statement ends and the next begins. Each
engine has its own tokenizer, but for corpus-valid SQL the boundary rule is
the same: a top-level ``;`` that is not inside a string literal, quoted
identifier, bracket identifier, or comment. This module is the single shared
implementation of that rule — the sqlite3 adapter (no native per-statement
API in the Python module) and the tursodb subprocess adapter both call it,
and the future pyturso parser (Phase 3) will be validated to agree with it.

Known limitation: SQL *compound statements* — trigger/view bodies wrapped in
``BEGIN ... END;`` — contain interior ``;`` that this splitter would wrongly
break on. None of the Phase 0 corpus uses them; the limitation is lifted
when a phase's corpus first needs trigger bodies (documented there).
"""

from __future__ import annotations

from typing import Iterator

__all__ = ["split_sql_script"]


def split_sql_script(sql: str) -> list[str]:
    """Split ``sql`` into individual SQL statements.

    A statement boundary is a ``;`` at the top level — i.e. not inside a
    ``'...'``/``"..."``/````...````/``[...]`` quoted region and not inside a
    ``--`` line or ``/* */`` block comment. Quote-escaping (``''`` inside
    ``'...'``, ``""`` inside ``"..."``) is honoured.

    Returns:
        The non-empty statements in order, each stripped of surrounding
        whitespace and comments. Whitespace-only and comment-only fragments
        between semicolons produce no entry (they are not statements).

    Examples:
        >>> split_sql_script("SELECT 1")
        ['SELECT 1']
        >>> split_sql_script("SELECT 1; SELECT 2;")
        ['SELECT 1', 'SELECT 2']
        >>> split_sql_script("SELECT ';' -- ignore; this")
        ["SELECT ';'"]
    """
    return list(_iter_statements(sql))


def _iter_statements(sql: str) -> Iterator[str]:
    """Yield non-empty statements from ``sql`` using a char-level state
    machine. See :func:`split_sql_script` for the boundary rules."""
    buf: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        # Comment starts: consume without adding to the statement buffer.
        if ch == "-" and nxt == "-":
            i = _skip_line_comment(sql, i, n)
            continue
        if ch == "/" and nxt == "*":
            i = _skip_block_comment(sql, i, n)
            continue

        # Quoted regions: copy verbatim (escape sequences included) so an
        # interior ';' never looks like a boundary.
        if ch == "'":
            end = _skip_until_close(sql, i, n, "'", "''")
            buf.append(sql[i:end])
            i = end
            continue
        if ch == '"':
            end = _skip_until_close(sql, i, n, '"', '""')
            buf.append(sql[i:end])
            i = end
            continue
        if ch == "`":
            end = _skip_until_close(sql, i, n, "`", "``")
            buf.append(sql[i:end])
            i = end
            continue
        if ch == "[":
            # Bracket identifiers ([...]) have no escape; close on first ']'.
            end = _skip_until_close(sql, i, n, "]", None)
            buf.append(sql[i:end])
            i = end
            continue

        # Top-level ';' ends the current statement.
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                yield stmt
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    # Trailing statement with no terminating ';' (common in corpus scripts).
    stmt = "".join(buf).strip()
    if stmt:
        yield stmt


def _skip_line_comment(sql: str, i: int, n: int) -> int:
    """Return the index just past a ``--`` line comment (after the newline)."""
    j = i + 2
    while j < n and sql[j] != "\n":
        j += 1
    return j  # newline (if any) is processed by the main loop as whitespace


def _skip_block_comment(sql: str, i: int, n: int) -> int:
    """Return the index just past a ``/* ... */`` block comment."""
    j = i + 2
    while j < n - 1 and not (sql[j] == "*" and sql[j + 1] == "/"):
        j += 1
    return min(j + 2, n)  # past the closing "*/" (or clamped to end)


def _skip_until_close(
    sql: str, i: int, n: int, close: str, escape: str | None
) -> int:
    """Return the index just past a quoted region opened at ``i``.

    Args:
        i: index of the opening quote.
        close: the closing quote char.
        escape: the doubled-quote escape sequence (``''``, ``""``, ``````` ``)
            that represents a literal quote *inside* the region, or ``None``
            for bracket identifiers which have no escape.
    """
    j = i + 1
    while j < n:
        if escape is not None and sql[j] == close and j + 1 < n and sql[j + 1] == close:
            j += 2  # escaped quote: skip both chars
            continue
        if sql[j] == close:
            return j + 1  # past the closing quote
        j += 1
    return n  # unterminated: consume to end (caller keeps it verbatim)
