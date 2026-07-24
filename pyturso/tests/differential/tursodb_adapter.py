"""tursodb_adapter — subprocess oracle adapter over the Rust tursodb binary.

Ports: the tursodb role of scripts/diff.sh; the CLI surface in cli/app.rs and
cli/input.rs (positional ``<db> <sql>``, ``-m list`` list-mode output).
Phase: 0
Status: IMPLEMENTED (logic); real-binary integration is exercised at the
Phase 0 gate (#13) once ``TURSODB_BIN`` is built — this module is tested here
against a stub runner that mimics tursodb's list-mode text and exit codes.

tursodb is a *text-only* subprocess: it runs SQL and prints pipe-separated
rows in list mode (NULL → empty cell, ``|`` between columns, one row per
line, trailing newline after every row). It has no per-statement API and no
typed values, so to align with the per-statement result model the adapter:

1. Splits the script with the shared :mod:`sqlsplit` (identical to the
   sqlite3 adapter).
2. Invokes tursodb **once per statement** (``-m list <db> <stmt>``); each
   invocation's stdout is exactly that statement's rows (list mode prints
   nothing for non-row statements), so per-statement alignment is exact.

Cells stay as tursodb's native text (NULL→empty, blobs→lossy-utf8). The
normalization layer (#6) later reconciles this to the canonical form
(:func:`tests.differential.engine.render_cell`).

Engine-internal failures — timeout, crash (signalled exit), or a missing
binary — are **not** SQL error classes and never enter the comparison: they
raise :class:`AdapterError`, which the reporter surfaces as a distinct
verdict. A crash aborts the whole :meth:`run_script`.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from pyturso.errors import (
    DATABASE_ERROR,
    DATA_ERROR,
    INTEGRITY_ERROR,
    INTERNAL_ERROR,
    OPERATIONAL_ERROR,
)

from .engine import ErrorClass, FixtureError, Rows, StatementResult
from .sqlsplit import split_sql_script

__all__ = ["TursodbEngine", "AdapterError", "ProcResult", "Runner"]

#: Default per-invocation timeout (seconds). A tursodb that hangs on a
#: statement is surfaced as a timeout verdict, not a hang of the whole suite.
DEFAULT_TIMEOUT: float = 30.0

#: What ``cargo run -q --bin tursodb`` looks like as a command prefix. Used
#: when ``TURSODB_BIN`` is unset. The trailing ``--`` separates cargo args
#: from the binary's own args.
_CARGO_PREFIX: list[str] = ["cargo", "run", "-q", "--bin", "tursodb", "--"]


@dataclass
class ProcResult:
    """Outcome of one subprocess invocation, as a runner returns it.

    ``returncode`` follows :class:`subprocess.CompletedProcess` convention:
    0 success, positive the process exit status, negative a signal number
    (crash — e.g. ``-11`` for SIGSEGV).
    """

    stdout: str
    stderr: str
    returncode: int


#: A runner executes one assembled command and returns a :class:`ProcResult`,
#: or raises :class:`AdapterError` for timeout / missing-binary. Injected in
#: tests so the real binary is not required; defaults to :func:`default_runner`.
Runner = Callable[[Sequence[str], float], ProcResult]


class AdapterError(Exception):
    """Engine-internal failure (timeout, crash, missing binary).

    Distinct from a SQL :data:`ErrorClass` (a normal per-statement outcome):
    these abort the run and the reporter marks the case ERROR rather than
    entering the comparison.
    """


# --- error-text → comparison-class mapping --------------------------------
#: Ordered (prefix, class) pairs. tursodb prints its ``LimboError`` via a
#: miette report whose message is the variant's ``#[error("...")]`` string
#: (see core/error.rs). We match the longest unambiguous prefixes first:
#: ``"Runtime error: integer overflow"`` before the catch-all
#: ``"Runtime error:"``. Searched over combined stdout+stderr text.
#: Sub-disambiguation of the remaining ``"Runtime error:"`` (constraint vs
#: other) defaults to IntegrityError — constraints dominate runtime errors in
#: the corpus; refined when the corpus first exercises the ambiguous cases.
_ERROR_PREFIX_CLASS: list[tuple[str, str]] = [
    # Corrupt / format (SQLITE_CORRUPT, NOTADB)
    ("Corrupt database", DATABASE_ERROR),
    ("File is not a database", DATABASE_ERROR),
    ("Database is empty, header does not exist", DATABASE_ERROR),
    ("Invalid blob size", DATABASE_ERROR),
    # Internal / resource
    ("Internal error", INTERNAL_ERROR),
    ("Out of memory", INTERNAL_ERROR),
    # Parse / lexer (SQLITE_ERROR → Operational, matching sqlite3)
    ("Parse error", OPERATIONAL_ERROR),
    ("Modifier parsing error", OPERATIONAL_ERROR),
    # Conversion / data
    ("Conversion error", DATA_ERROR),
    ("Null value", DATA_ERROR),
    ("invalid column type", DATA_ERROR),
    # Specific "Runtime error:" subtypes (must precede the catch-all).
    ("Runtime error: integer overflow", OPERATIONAL_ERROR),
    ("Runtime error: string or blob too big", OPERATIONAL_ERROR),
    ("Runtime error: database table is locked", OPERATIONAL_ERROR),
    ("Runtime error: blob handle expired", OPERATIONAL_ERROR),
    # Remaining "Runtime error:" → constraint family (UNIQUE/PK/CHECK/NOTNULL/FK/RAISE).
    ("Runtime error:", INTEGRITY_ERROR),
    # Concurrency / busy / locking
    ("Database is busy", OPERATIONAL_ERROR),
    ("Locking error", OPERATIONAL_ERROR),
    ("interrupt", OPERATIONAL_ERROR),
    ("Database snapshot is stale", OPERATIONAL_ERROR),
    ("Error: Resource is read-only", OPERATIONAL_ERROR),
    ("SQL statements in progress", OPERATIONAL_ERROR),
    ("Database is full", OPERATIONAL_ERROR),
    # Transaction / schema / planning / io / misc → operational
    ("Transaction error", OPERATIONAL_ERROR),
    ("Transaction terminated", OPERATIONAL_ERROR),
    ("Conflict", OPERATIONAL_ERROR),
    ("Write-write conflict", OPERATIONAL_ERROR),
    ("Commit dependency aborted", OPERATIONAL_ERROR),
    ("No such transaction ID", OPERATIONAL_ERROR),
    ("Database schema changed", OPERATIONAL_ERROR),
    ("Database schema conflict", OPERATIONAL_ERROR),
    ("Planning error", OPERATIONAL_ERROR),
    ("Extension error", OPERATIONAL_ERROR),
    ("Unsupported text encoding", OPERATIONAL_ERROR),
    ("Checkpoint failed", OPERATIONAL_ERROR),
    ("Invalid argument supplied", OPERATIONAL_ERROR),
    ("Invalid formatter supplied", OPERATIONAL_ERROR),
    ("I/O error", OPERATIONAL_ERROR),
]


def _classify_tursodb_error(combined_output: str) -> ErrorClass:
    """Map tursodb's error text to a comparison class by prefix match.

    Falls back to :data:`OPERATIONAL_ERROR` (SQLite's catch-all) when no prefix
    matches — matching :func:`pyturso.errors.comparison_class`'s fallback so an
    unmapped tursodb error never crashes the harness.
    """
    for prefix, cls in _ERROR_PREFIX_CLASS:
        if prefix in combined_output:
            return cls
    return OPERATIONAL_ERROR


def _parse_list_rows(stdout: str) -> Rows:
    """Parse tursodb list-mode stdout into rows of text cells.

    tursodb prints one line per row (cells joined by ``|``) and terminates
    every row with a newline; non-row statements print nothing. NULL renders
    as an empty cell. Algorithm:

    - Split on ``\\n`` and drop exactly **one** trailing empty string (the
      final newline). This distinguishes "no rows" (stdout ``""`` → ``[""]``
      → drop → ``[]``) from "one row whose only cell is empty text" (stdout
      ``"\\n"`` → ``["", ""]`` → drop → ``[""]`` → ``[("",)]``).
    - Each remaining line is one row; ``line.split("|")`` gives its cells
      (an empty line → one empty-text cell).

    Known limitation (inherent to list mode, affects every text engine): a
    TEXT value containing ``|`` splits into extra cells. The corpus avoids
    text-with-pipe; tracked with the normalization layer.
    """
    lines = stdout.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [tuple(line.split("|")) for line in lines]


def default_runner(cmd: Sequence[str], timeout: float) -> ProcResult:
    """Run ``cmd`` capturing output; raise :class:`AdapterError` on timeout or
    missing binary. The injectable default used in production."""
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise AdapterError(f"tursodb binary not found: {exc.filename or cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdapterError(f"tursodb timed out after {timeout}s") from exc
    return ProcResult(
        stdout=proc.stdout or "", stderr=proc.stderr or "", returncode=proc.returncode
    )


class TursodbEngine:
    """Oracle adapter running each statement through the tursodb binary.

    Args:
        binary: path to the tursodb binary. Defaults to ``$TURSODB_BIN``, then
            the ``cargo run -q --bin tursodb`` fallback. ``None`` only if
            neither is available — :meth:`run_script` then raises
            :class:`AdapterError`, so construction always succeeds.
        timeout: per-invocation timeout in seconds.
        runner: subprocess executor (injectable for tests).
    """

    def __init__(
        self,
        binary: str | os.PathLike[str] | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        runner: Runner | None = None,
    ) -> None:
        self._prefix: list[str] | None = _resolve_prefix(binary)
        self._timeout: float = timeout
        self._runner: Runner = runner if runner is not None else default_runner

    def run_script(
        self, sql_text: str, db_path: Path | None
    ) -> list[StatementResult]:
        if self._prefix is None:
            raise AdapterError(
                "tursodb binary unavailable: set TURSODB_BIN or build with cargo"
            )
        if db_path is not None and not Path(db_path).is_file():
            raise FixtureError(db_path)
        db_arg = str(db_path) if db_path is not None else ":memory:"

        results: list[StatementResult] = []
        for stmt in split_sql_script(sql_text):
            cmd = [*self._prefix, "-m", "list", db_arg, stmt]
            proc = self._runner(cmd, self._timeout)
            if proc.returncode < 0:
                # Signalled exit (e.g. SIGSEGV -11): a crash, not a SQL error.
                raise AdapterError(
                    f"tursodb crashed with signal {-proc.returncode}"
                )
            if proc.returncode != 0:
                # SQL error: classify by the #[error] prefix in its output.
                results.append(
                    _classify_tursodb_error(proc.stdout + proc.stderr)
                )
                break
            results.append(_parse_list_rows(proc.stdout))
        return results


def _resolve_prefix(binary: str | os.PathLike[str] | None) -> list[str] | None:
    """Resolve the command prefix: explicit arg → ``$TURSODB_BIN`` → cargo."""
    if binary is not None:
        return [str(binary)]
    env = os.environ.get("TURSODB_BIN")
    if env:
        return [env]
    return _CARGO_PREFIX  # may fail at run time if cargo is absent
