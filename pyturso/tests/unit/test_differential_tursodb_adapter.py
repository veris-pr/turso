"""Unit tests for tests.differential.tursodb_adapter.

Verified against: cli/app.rs print_list_mode (one line per row, ``|`` cells,
trailing newline, nothing for non-row), the per-statement subprocess contract
in tests/differential/README.md, and the ``#[error("...")]`` prefixes in
core/error.rs for error-class mapping.

No real tursodb binary is required: a stub runner injects the
(stdout, stderr, returncode) triples, mimicking tursodb's list-mode output
and exit codes. Real-binary integration is the Phase 0 gate (#13).
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

import pytest

from pyturso.errors import (
    DATABASE_ERROR,
    INTEGRITY_ERROR,
    INTERNAL_ERROR,
    OPERATIONAL_ERROR,
)
from tests.differential.engine import Engine, FixtureError
from tests.differential.tursodb_adapter import (
    AdapterError,
    ProcResult,
    Runner,
    TursodbEngine,
)


def make_engine(
    results: list[ProcResult],
) -> tuple[TursodbEngine, list[list[str]]]:
    """Build a TursodbEngine whose runner returns ``results`` in order.

    Returns the engine plus the captured list of commands (one per call) so
    tests can assert invocation shape. Raises if the runner is called more
    times than scripted (a test bug, not a pass).
    """
    calls: list[list[str]] = []
    seq = iter(results)

    def run(cmd: Sequence[str], timeout: float) -> ProcResult:
        calls.append(list(cmd))
        try:
            return next(seq)
        except StopIteration:  # pragma: no cover - test bug if hit
            raise AssertionError("runner called more times than scripted")

    eng: TursodbEngine = TursodbEngine(binary="stub", runner=run)
    return eng, calls


# --- protocol conformance --------------------------------------------------
def test_is_an_engine() -> None:
    assert isinstance(TursodbEngine(binary="stub"), Engine)


# --- list-mode row parsing -------------------------------------------------
class TestRowParsing:
    def test_single_value_row(self) -> None:
        eng, _ = make_engine([ProcResult("1\n", "", 0)])
        assert eng.run_script("SELECT 1;", None) == [[("1",)]]

    def test_multicolumn_row(self) -> None:
        eng, _ = make_engine([ProcResult("1|2|3\n", "", 0)])
        assert eng.run_script("SELECT 1,2,3;", None) == [[("1", "2", "3")]]

    def test_multirow(self) -> None:
        eng, _ = make_engine([ProcResult("1\n2\n3\n", "", 0)])
        assert eng.run_script("SELECT * FROM t;", None) == [
            [("1",), ("2",), ("3",)]
        ]

    def test_non_row_statement_prints_nothing(self) -> None:
        # CREATE/INSERT: tursodb prints nothing → empty Rows.
        eng, _ = make_engine([ProcResult("", "", 0)])
        assert eng.run_script("CREATE TABLE t(x);", None) == [[]]

    def test_empty_select_is_empty_rows(self) -> None:
        eng, _ = make_engine([ProcResult("", "", 0)])
        assert eng.run_script("SELECT * FROM empty;", None) == [[]]

    def test_null_renders_as_empty_cell(self) -> None:
        # tursodb list mode: NULL → "" (not "NULL"). For SELECT NULL, 1 the
        # cells "" and "1" join as "|1". Normalization (#6) later restores NULL.
        eng, _ = make_engine([ProcResult("|1\n", "", 0)])
        assert eng.run_script("SELECT NULL, 1;", None) == [[("", "1")]]

    def test_one_empty_text_row_distinguished_from_no_rows(self) -> None:
        # SELECT '' → stdout "\n" (one empty-text row) vs no-rows stdout "".
        eng, _ = make_engine([ProcResult("\n", "", 0)])
        assert eng.run_script("SELECT '';", None) == [[("",)]]


# --- per-statement invocation shape ---------------------------------------
class TestInvocation:
    def test_one_invocation_per_statement(self) -> None:
        eng, calls = make_engine(
            [ProcResult("1\n", "", 0), ProcResult("2\n", "", 0)]
        )
        assert eng.run_script("SELECT 1; SELECT 2;", None) == [
            [("1",)],
            [("2",)],
        ]
        assert len(calls) == 2

    def test_command_uses_list_mode_and_db_arg(self, tmp_path: Path) -> None:
        db = tmp_path / "x.db"
        db.write_bytes(b"")  # exists, so the FixtureError check passes
        eng, calls = make_engine([ProcResult("1\n", "", 0)])
        eng.run_script("SELECT 1;", db)
        cmd = calls[0]
        assert cmd[:1] == ["stub"]  # prefix
        assert "-m" in cmd and "list" in cmd  # list mode
        assert str(db) in cmd  # db positional
        assert "SELECT 1" in cmd  # stmt positional

    def test_in_memory_when_no_db(self) -> None:
        eng, calls = make_engine([ProcResult("1\n", "", 0)])
        eng.run_script("SELECT 1;", None)
        assert ":memory:" in calls[0]


# --- error handling --------------------------------------------------------
class TestErrors:
    def test_parse_error_maps_to_operational(self) -> None:
        eng, _ = make_engine(
            [ProcResult("", 'Parse error: near "FOO": syntax error', 1)]
        )
        assert eng.run_script("FOO;", None) == [OPERATIONAL_ERROR]

    def test_constraint_maps_to_integrity(self) -> None:
        eng, _ = make_engine(
            [ProcResult("", "Runtime error: UNIQUE constraint failed", 1)]
        )
        assert eng.run_script("INSERT INTO t VALUES(1);", None) == [
            INTEGRITY_ERROR
        ]

    def test_corrupt_maps_to_database(self) -> None:
        eng, _ = make_engine([ProcResult("", "Corrupt database: bad page", 1)])
        assert eng.run_script("SELECT 1;", None) == [DATABASE_ERROR]

    def test_out_of_memory_maps_to_internal(self) -> None:
        eng, _ = make_engine([ProcResult("", "Out of memory", 1)])
        assert eng.run_script("SELECT 1;", None) == [INTERNAL_ERROR]

    def test_integer_overflow_is_operational_not_integrity(self) -> None:
        # The specific "Runtime error: integer overflow" prefix must win over
        # the constraint catch-all "Runtime error:".
        eng, _ = make_engine([ProcResult("", "Runtime error: integer overflow", 1)])
        assert eng.run_script("SELECT 1<<63;", None) == [OPERATIONAL_ERROR]

    def test_unmapped_error_falls_back_to_operational(self) -> None:
        eng, _ = make_engine([ProcResult("", "something totally novel", 2)])
        assert eng.run_script("SELECT 1;", None) == [OPERATIONAL_ERROR]

    def test_error_stops_the_run(self) -> None:
        # Only one scripted result: the error. A second call would raise.
        eng, _ = make_engine([ProcResult("", "Parse error: bad", 1)])
        assert eng.run_script("SELECT 1; SELECT 2;", None) == [OPERATIONAL_ERROR]


# --- engine-internal failures (distinct verdict) --------------------------
def test_crash_raises_adaptererror() -> None:
    eng, _ = make_engine([ProcResult("", "", -11)])  # SIGSEGV
    with pytest.raises(AdapterError, match="crashed"):
        eng.run_script("SELECT 1;", None)


def test_timeout_raises_adaptererror() -> None:
    def run(cmd: Sequence[str], timeout: float) -> ProcResult:
        raise AdapterError("timed out after 0.1s")

    eng = TursodbEngine(binary="stub", runner=run)
    with pytest.raises(AdapterError, match="timed out"):
        eng.run_script("SELECT 1;", None)


# --- fixture + binary resolution ------------------------------------------
def test_missing_fixture_raises_fixtureerror(tmp_path: Path) -> None:
    eng, _ = make_engine([ProcResult("1\n", "", 0)])
    with pytest.raises(FixtureError):
        eng.run_script("SELECT 1;", tmp_path / "nope.db")


def test_no_binary_raises_adaptererror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TURSODB_BIN", raising=False)
    eng = TursodbEngine()  # prefix falls back to cargo
    eng._prefix = None  # simulate "neither TURSODB_BIN nor cargo available"
    with pytest.raises(AdapterError, match="unavailable"):
        eng.run_script("SELECT 1;", None)


def test_tursodbbin_env_used_as_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TURSODB_BIN", "/opt/tursodb")
    # __init__ resolves the prefix from env without calling the runner.
    eng = TursodbEngine(runner=_NOOP_RUNNER)
    assert eng._prefix == ["/opt/tursodb"]


def test_explicit_binary_arg_wins_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TURSODB_BIN", "/from/env")
    eng = TursodbEngine(binary="/explicit")
    assert eng._prefix == ["/explicit"]


# A runner that is never invoked; only its type matters for prefix-resolution
# tests that construct an engine without running a script.
def _noop_run(cmd: Sequence[str], timeout: float) -> ProcResult:
    raise AssertionError("runner should not be called in a prefix test")


_NOOP_RUNNER: Runner = _noop_run
