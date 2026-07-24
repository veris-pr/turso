"""engine — the adapter protocol the three engines conform to.

Ports: scripts/diff.sh (the pattern), tests/differential/README.md (contract).
Phase: 0
Status: IMPLEMENTED.

The differential harness compares engines *statement by statement*: each engine
runs the same ``.sql`` script against the same fixture database and reports one
outcome per executed statement. This module is the shared contract — the three
adapters (sqlite3 in-process, tursodb subprocess, pyturso in-process) are built
on it in later TODO items.

Why a :class:`Engine` :class:`typing.Protocol` (structural) rather than an ABC:
the three adapters are structurally different (one is a wrapper around the
``sqlite3`` module, one spawns a subprocess, one drives the in-process engine),
so we want duck-typing, not forced inheritance. A :func:`typing.runtime_checkable`
decorator lets the harness assert at construction time that a candidate adapter
actually provides :meth:`run_script`.

Result model
------------
A statement either returns rows or raises. The adapter reports:

- :data:`Rows` — the rows a statement produced, in result order, carrying raw
  typed SQLite values. Empty for non-row statements (``CREATE``/``INSERT``);
  canonical string rendering is the normalization layer's job, never the
  engine's.
- :data:`ErrorClass` — the comparison-class name (``"OperationalError"``, …) of
  the first error a statement raised. Vocabulary lives in
  :mod:`pyturso.errors` (``OPERATIONAL_ERROR``, …); adapters import those
  constants so all three speak the same names.

The first statement that errors is recorded as its class and stops the run;
later statements are not executed. All three engines honour this so results
compare element-wise across engines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypeAlias, Union, runtime_checkable

#: A single raw SQLite value as delivered by a *type-aware* engine (sqlite3
#: in-process, pyturso in-process) before rendering. SQLite is dynamically
#: typed, so a column can hold any of these. The text-only tursodb subprocess
#: never produces :data:`SqlValue` — it emits rendered cells directly.
SqlValue: TypeAlias = Union[int, float, str, bytes, None]

#: The rows returned by one statement, in result order, as **rendered text
#: cells**. Every adapter returns cells as ``str``: type-aware adapters render
#: via :func:`render_cell` (canonical, type-faithful); the tursodb subprocess
#: emits its own list-mode text which the normalization layer (#6) later
#: reconciles to canonical. Tuples keep rows hashable for multiset comparison
#: and immutable for safe sharing. Empty for non-row statements (CREATE/INSERT).
Rows: TypeAlias = "list[tuple[str, ...]]"

#: The comparison-class name of an error (sqlite3-style: ``"OperationalError"``,
#: ``"IntegrityError"``, …). The shared vocabulary is defined by the constants
#: in :mod:`pyturso.errors`; adapters use those constants, not ad hoc strings,
#: so error-class comparison is exact across engines.
ErrorClass: TypeAlias = str

#: Outcome of one executed statement: either its rows or the error class that
#: the statement raised. The two are distinguishable at runtime — :data:`Rows`
#: is a ``list``, :data:`ErrorClass` is a ``str`` — so a consumer dispatches
#: with ``isinstance(result, str)`` (error) vs ``list`` (rows).
StatementResult: TypeAlias = Union[Rows, ErrorClass]


#: The canonical float format shared with the oracles (tursodb's
#: ``format_float`` uses precision 15; the README pins ``%.15g``). Matches
#: both, so type-aware rendering and tursodb's native rendering agree after
#: the normalization layer normalizes the latter.
_FLOAT_FORMAT: str = "%.15g"


def render_cell(value: SqlValue) -> str:
    """Render one typed SQLite value to its canonical comparison text.

    Used by every *type-aware* adapter (sqlite3 in-process, pyturso in-process)
    so they emit identical text for identical values. The text-only tursodb
    subprocess does not use this — it emits its own list-mode text, which the
    normalization layer (#6) later reconciles to this canonical form.

    Canonical form (pinned by tests/differential/README.md):
      - ``None``  -> ``"NULL"`` (the NULL literal)
      - ``int``   -> decimal (``str(value)``)
      - ``float`` -> ``%.15g``
      - ``bytes`` -> ``x'<lowerhex>'`` (hex-encoded blob)
      - ``str``   -> verbatim

    Note: a TEXT value whose contents are literally ``"NULL"`` is
    indistinguishable from a SQL NULL in text comparison — a known, documented
    limitation of text-based differential comparison. Blob type is likewise
    lost by the tursodb subprocess (it renders blobs as lossy UTF-8); blob
    corpus cases must be chosen with this in mind.
    """
    if value is None:
        return "NULL"
    # bool is a subclass of int; SQLite has no bool, so coerce to 0/1.
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _FLOAT_FORMAT % value
    if isinstance(value, bytes):
        return "x'" + value.hex() + "'"
    return value  # str — verbatim


@runtime_checkable
class Engine(Protocol):
    """Runs a SQL script against a fixture database, reporting per-statement
    outcomes in the shared result model above."""

    def run_script(
        self, sql_text: str, db_path: Path | None
    ) -> list[StatementResult]:
        """Run ``sql_text`` against ``db_path``; return one result per executed
        statement, in order, each cell a rendered :data:`str`.

        Args:
            sql_text: a SQL script (one or more statements). Statement
                boundaries follow the engine's own SQLite tokenizer; for
                corpus-valid SQL the three engines agree.
            db_path: a pre-built fixture database (produced by
                ``tools.mkdb``). ``None`` means start from an empty database
                (in-memory or a fresh temp file) — the adapter chooses how.

        Returns:
            A list with one :data:`StatementResult` per executed statement. The
            run stops at the first erroring statement: it is recorded as its
            :data:`ErrorClass` and no later statement is executed.

        Raises:
            FixtureError: ``db_path`` does not exist or is not a readable
                database. (Engine-internal failures that are *not* SQL errors —
                e.g. the tursodb binary missing, a crash — are surfaced by the
                adapter itself, not raised here, so a single bad adapter never
                aborts the whole corpus run.)
        """
        ...


class FixtureError(Exception):
    """The requested fixture database is missing or unreadable.

    Distinct from a SQL :data:`ErrorClass` (which is a normal per-statement
    outcome): a missing fixture is a harness/setup problem, not a behavioral
    result, so it propagates rather than entering the comparison.
    """

    def __init__(self, db_path: Path | None) -> None:
        self.db_path: Path | None = db_path
        where = str(db_path) if db_path is not None else "<in-memory>"
        super().__init__(f"fixture database not found or unreadable: {where}")


__all__ = [
    "SqlValue",
    "Rows",
    "ErrorClass",
    "StatementResult",
    "render_cell",
    "Engine",
    "FixtureError",
]
