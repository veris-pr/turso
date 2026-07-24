"""compare — multiset/ordered comparison of normalized statement results.

Ports: the comparison rules in tests/differential/README.md ("Unordered
queries compared as multisets; ordered queries as sequences — a case opts
into ordered comparison by having an ORDER BY").
Phase: 0
Status: IMPLEMENTED.

This module is the comparator half of the harness (normalization is
:mod:`tests.differential.normalize`). It answers "do two engines agree on
this statement's result?", where "agree" depends on whether the statement
imposes a row order:

  - **ordered** (the statement has an ``ORDER BY``): the two row lists must be
    equal as *sequences* (same rows in the same order).
  - **unordered** (no ``ORDER BY``): the two row lists must be equal as
    *multisets* (same rows, any order). SQL leaves unordered result order
    unspecified, so two correct engines may return the same rows in different
    orders; a sequence comparison would report a false divergence.

ORDER BY detection has no SQL parser available until Phase 3, so
:func:`is_ordered_query` is a conservative *text heuristic*: it looks for the
``ORDER BY`` keyword sequence outside of string/identifier quotes. It is
deliberately conservative — false negatives (missing a real ORDER BY) only
downgrade a comparison to multiset, which still passes for matching rows; the
corpus is built so this is safe until the parser arrives. Phase 3 replaces the
heuristic with parser-based detection on the AST.

Errors compare by class string (already the comparison vocabulary); a mixed
rows-vs-error pair is a divergence (not equal). The harness drives comparison
per-statement, supplying the ordered flag from :func:`is_ordered_query`.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import Union

from .engine import ErrorClass

__all__ = [
    "rows_equal",
    "result_equal",
    "results_equal",
    "is_ordered_query",
]

#: Read-only rows view. Comparison never mutates, so builders hand over
#: :data:`Rows` (``list[tuple[str, ...]]``) and this reader sees the covariant
#: ``Sequence[tuple[str, ...]]`` — accepting any fixed-arity tuple list without
#: the invariant-list friction, the right abstraction for a read-only pass.
ReadRows = Sequence[tuple[str, ...]]

#: A statement result as the comparator sees it: rows (covariant) or an error
#: class. Broader than :data:`StatementResult` only in covariance, not shape.
CompResult = Union[ReadRows, ErrorClass]

#: Matches a top-level ``ORDER`` ``BY`` keyword pair, case-insensitive, with
#: whitespace/newlines between the two words. Word boundaries (``\b``) prevent
#: matching inside identifiers like ``REORDER`` or ``BYPASS``. Quote-stripping
#: below removes string/identifier contents first so an ``ORDER BY`` *inside* a
#: string literal cannot trigger a match.
_ORDER_BY_RE: re.Pattern[str] = re.compile(
    r"\border\s+by\b", re.IGNORECASE | re.DOTALL
)

#: Characters that open a quote/identifier region; their contents are blanked
#: before the ORDER BY search so literals cannot masquerade as keywords.
_QUOTE_CHARS: frozenset[str] = frozenset("'\"`[")


def rows_equal(a: ReadRows, b: ReadRows, *, ordered: bool) -> bool:
    """Compare two row lists.

    Args:
        ordered: ``True`` for sequence equality (statement has ORDER BY);
            ``False`` for multiset equality (no ORDER BY).
    """
    if ordered:
        return list(a) == list(b)
    # Multiset: same rows, any order. Rows are tuple[str,...] → hashable, so a
    # Counter comparison is exact and O(n).
    return Counter(a) == Counter(b)


def result_equal(
    a: CompResult, b: CompResult, *, ordered: bool
) -> bool:
    """Compare two statement results.

    - both rows → :func:`rows_equal`
    - both error classes → equal iff identical class string
    - mixed (rows vs error) → ``False`` (a divergence)
    """
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, str) or isinstance(b, str):
        # Exactly one is an error, the other rows → divergence.
        return False
    # Both rows (isinstance narrowed away the str arm of the union).
    return rows_equal(a, b, ordered=ordered)


def results_equal(
    a: Sequence[CompResult],
    b: Sequence[CompResult],
    ordered_flags: Sequence[bool],
) -> bool:
    """Compare two whole-script results, statement by statement.

    Args:
        a, b: per-statement results from two engines (already normalized).
        ordered_flags: one ``ordered`` flag per statement, parallel to ``a``/``b``.
            The harness derives these from :func:`is_ordered_query` per statement.

    The lists must be the same length and ``ordered_flags`` parallel to them;
    a length mismatch is itself a divergence (the engines disagreed on how many
    statements ran — e.g. one stopped early at an error the other didn't).
    """
    if len(a) != len(b) or len(a) != len(ordered_flags):
        return False
    return all(
        result_equal(x, y, ordered=ordered)
        for x, y, ordered in zip(a, b, ordered_flags, strict=True)
    )


def is_ordered_query(statement: str) -> bool:
    """Heuristic: does ``statement`` impose a row order via ``ORDER BY``?

    Conservative text search: blanks string/identifier contents first so an
    ``ORDER BY`` inside a literal cannot trigger a match, then looks for the
    keyword pair on word boundaries.

    LIMITATIONS (lifted at Phase 3 with parser-based AST detection):
      - A subquery's ``ORDER BY`` is reported even if an outer optimizer could
        prove it redundant — only a false *positive*, which is safe (ordered
        comparison still passes for matching rows).
      - ``GROUP BY … ORDER BY <alias>`` etc. are detected as ordered, correctly.
    """
    # Blank quoted/identifier regions so keyword text inside literals is inert.
    stripped = _blank_quoted(statement)
    return _ORDER_BY_RE.search(stripped) is not None


def _blank_quoted(text: str) -> str:
    """Return ``text`` with every quoted/identifier region replaced by spaces.

    Keeps the result the same length so regex offsets stay meaningful. Handles
    ``'...'``, ``"..."``, ````...```` (SQL standard / double-quote escapes) and
    ``[...]`` (bracket identifiers). Unterminated quotes blank to end of string.
    A best-effort scan — the real tokenizer (Phase 3) is authoritative.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in _QUOTE_CHARS:
            close = _matching_close(ch)
            j = i + 1
            while j < n:
                if close is None:
                    # Bracket identifier: closes on first ']'.
                    if text[j] == "]":
                        j += 1
                        break
                elif text[j] == ch:
                    # Doubled-quote escape inside the region: skip both.
                    if j + 1 < n and text[j + 1] == ch:
                        j += 2
                        continue
                    j += 1  # closing quote
                    break
                j += 1
            out.append(" " * (j - i))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _matching_close(open_char: str) -> str | None:
    """The close char for ``open_char``, or ``None`` for ``[`` (no escape)."""
    if open_char == "[":
        return None
    return open_char
