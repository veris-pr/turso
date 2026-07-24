"""sqlite3_adapter — in-process oracle adapter over stdlib sqlite3.

Ports: the sqlite3 role of scripts/diff.sh.
Phase: 0
Status: IMPLEMENTED.

Implements :class:`tests.differential.engine.Engine` using the stdlib
``sqlite3`` module. This is the fast-path oracle: in-process, no subprocess,
identical tokenizer to the ``sqlite3`` CLI. Statement splitting is shared via
:mod:`tests.differential.sqlsplit` so the tursodb adapter splits identically
and per-statement results align across engines.

Errors are reported by *comparison class* (never message text): a sqlite3
exception is walked up its MRO and mapped to one of the vocabulary strings in
:mod:`pyturso.errors` (``OperationalError``, ``IntegrityError``, …). The run
stops at the first erroring statement, matching the contract in
:mod:`tests.differential.engine`.

Autocommit (``isolation_level=None``) is used so each statement commits
immediately — this mirrors the ``sqlite3`` CLI's behaviour, which is what the
differential comparison is ultimately against.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pyturso.errors import (
    DATABASE_ERROR,
    DATA_ERROR,
    INTERFACE_ERROR,
    INTEGRITY_ERROR,
    INTERNAL_ERROR,
    NOT_SUPPORTED_ERROR,
    OPERATIONAL_ERROR,
    PROGRAMMING_ERROR,
)

from .engine import ErrorClass, FixtureError, Rows, StatementResult, render_cell
from .sqlsplit import split_sql_script

__all__ = ["Sqlite3Engine"]


# sqlite3 exception subclass -> comparison class. Walked most-specific-first
# via the MRO, so e.g. IntegrityError (subclass of DatabaseError) resolves to
# INTEGRITY_ERROR, not DATABASE_ERROR. Mirrors pyturso.errors.comparison_class.
_SQLITE3_ERROR_CLASS: dict[type[sqlite3.Error], str] = {
    sqlite3.OperationalError: OPERATIONAL_ERROR,
    sqlite3.IntegrityError: INTEGRITY_ERROR,
    sqlite3.DataError: DATA_ERROR,
    sqlite3.ProgrammingError: PROGRAMMING_ERROR,
    sqlite3.NotSupportedError: NOT_SUPPORTED_ERROR,
    sqlite3.InternalError: INTERNAL_ERROR,
    sqlite3.DatabaseError: DATABASE_ERROR,  # base of the above; last-resort base
    sqlite3.InterfaceError: INTERFACE_ERROR,
}


def _map_sqlite3_error(exc: sqlite3.Error) -> ErrorClass:
    """Map a sqlite3 exception to its differential comparison class.

    Walks the MRO so the most specific registered subclass wins; an unmapped
    sqlite3.Error collapses to :data:`OPERATIONAL_ERROR` (SQLite's catch-all),
    matching :func:`pyturso.errors.comparison_class`'s fallback.
    """
    for cls in type(exc).__mro__:
        mapped = _SQLITE3_ERROR_CLASS.get(cls)
        if mapped is not None:
            return mapped
    return OPERATIONAL_ERROR


class Sqlite3Engine:
    """Oracle adapter running scripts through stdlib sqlite3 in-process.

    A new connection is opened per :meth:`run_script` call (one connection per
    corpus case) and always closed, so cases never leak transaction or schema
    state into each other.
    """

    def run_script(
        self, sql_text: str, db_path: Path | None
    ) -> list[StatementResult]:
        if db_path is not None and not Path(db_path).is_file():
            raise FixtureError(db_path)
        target = str(db_path) if db_path is not None else ":memory:"

        # isolation_level=None -> autocommit; matches the sqlite3 CLI, which is
        # the behaviour the differential comparison targets.
        conn = sqlite3.connect(target, isolation_level=None)
        results: list[StatementResult] = []
        try:
            for stmt in split_sql_script(sql_text):
                try:
                    cur = conn.execute(stmt)
                    rows = cur.fetchall()
                except sqlite3.Error as exc:
                    results.append(_map_sqlite3_error(exc))
                    break
                # Render typed sqlite3 values to canonical text so the
                # type-aware adapters (sqlite3, later pyturso) agree trivially;
                # only the text-only tursodb subprocess needs normalization.
                result_rows: Rows = [
                    tuple(render_cell(v) for v in r) for r in rows
                ]
                results.append(result_rows)
        finally:
            conn.close()
        return results
