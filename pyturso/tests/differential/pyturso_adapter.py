"""pyturso_adapter — the subject engine, in-process.

Ports: the pyturso role of the differential harness (no Rust counterpart —
pyturso *is* the port being measured).
Phase: 0
Status: STUB. pyturso has no engine yet; every case signals NOT-IMPLEMENTED.

This is the third adapter in the three-way comparison. Unlike the sqlite3 and
tursodb *oracles*, pyturso is the *subject* — the thing being built. It runs
in-process (no subprocess) and, once Phase 5 lands, drives the real engine
through the same :class:`Engine` protocol the oracles conform to.

Until then it must participate honestly: a corpus case that pyturso cannot yet
run must not crash the harness or be silently mistaken for a pass. So the stub
raises :class:`EngineNotImplemented` for every :meth:`run_script` call. The
reporter (#9) catches it and marks the case NOT-IMPLEMENTED — a distinct,
honest verdict, never counted green. This is the same signal-via-exception
pattern the tursodb adapter uses for :class:`AdapterError`, and the reporter
tells them apart by exception type (NOT-IMPLEMENTED is expected and partial;
ERROR is an unexpected adapter/harness failure).

Phase 5 replaces the ``raise`` with real execution that returns
:data:`StatementResult` per statement; per-statement not-implemented signalling
is layered in then, as cases pyturso *partially* supports appear. For Phase 0
the granularity is whole-case: pyturso runs nothing.
"""

from __future__ import annotations

from pathlib import Path

from .engine import StatementResult

__all__ = ["PytursoEngine", "EngineNotImplemented"]


class EngineNotImplemented(Exception):
    """pyturso cannot run this case yet.

    Raised by :class:`PytursoEngine` for any SQL it does not support (Phase 0:
    all of it). Distinct from a SQL :data:`ErrorClass` (a normal per-statement
    outcome) and from :class:`tests.differential.tursodb_adapter.AdapterError`
    (an oracle-internal failure): this is the *subject* honestly reporting its
    own scope, so the reporter maps it to the NOT-IMPLEMENTED verdict rather
    than ERROR.

    Carries the reason text so the reporter can show *why* a case is red
    (helpful when the scope ledger is being closed phase by phase).
    """


class PytursoEngine:
    """The pyturso subject adapter. Phase 0: a pure NOT-IMPLEMENTED stub.

    Conforms to :class:`Engine` structurally (has ``run_script``), so the
    harness drives it through the same interface as the oracles. It raises
    :class:`EngineNotImplemented` on every call — the reporter turns that into
    the NOT-IMPLEMENTED verdict.

    The ``db_path`` and ``sql_text`` arguments are intentionally *not*
    validated here: a not-implemented engine has nothing to validate against,
    and surfacing the not-implemented status first is the honest behaviour.
    """

    #: Human-readable scope note, shown by the reporter on NOT-IMPLEMENTED.
    #: Updated phase by phase as real execution lands.
    SCOPE_NOTE: str = (
        "pyturso engine not yet implemented (lands in Phase 5); "
        "all corpus cases are NOT-IMPLEMENTED until then"
    )

    def run_script(
        self, sql_text: str, db_path: Path | None
    ) -> list[StatementResult]:
        raise EngineNotImplemented(self.SCOPE_NOTE)
