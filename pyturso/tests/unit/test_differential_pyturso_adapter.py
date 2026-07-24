"""Unit tests for tests.differential.pyturso_adapter — the NOT-IMPLEMENTED stub.

Verified against: tests/differential/TODO.md (pyturso returns NOT-IMPLEMENTED
cleanly until Phase 5) and the verdict vocabulary in tests/differential/README.md
(NOT-IMPLEMENTED is a distinct, honest status, never counted green).

The stub never executes SQL — it must signal NOT-IMPLEMENTED for every case
without crashing. These tests lock that contract so Phase 5 work (real
execution) is forced to deliberately replace it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.differential.engine import Engine
from tests.differential.pyturso_adapter import (
    EngineNotImplemented,
    PytursoEngine,
)


@pytest.fixture
def engine() -> PytursoEngine:
    return PytursoEngine()


# --- protocol conformance --------------------------------------------------
def test_is_an_engine(engine: PytursoEngine) -> None:
    assert isinstance(engine, Engine)


# --- the Phase 0 contract: every case is NOT-IMPLEMENTED ------------------
def test_raises_not_implemented_for_select(engine: PytursoEngine) -> None:
    with pytest.raises(EngineNotImplemented):
        engine.run_script("SELECT 1;", None)


def test_raises_for_any_statement(engine: PytursoEngine) -> None:
    # The stub is feature-agnostic: DDL, DML, query — all not implemented.
    with pytest.raises(EngineNotImplemented):
        engine.run_script("CREATE TABLE t(x);", None)
    with pytest.raises(EngineNotImplemented):
        engine.run_script("INSERT INTO t VALUES (1);", None)


def test_raises_for_empty_script(engine: PytursoEngine) -> None:
    with pytest.raises(EngineNotImplemented):
        engine.run_script("", None)


def test_raises_with_db_path(engine: PytursoEngine, tmp_path: Path) -> None:
    # db_path is intentionally not validated (a not-implemented engine has
    # nothing to open); the not-implemented status surfaces first.
    with pytest.raises(EngineNotImplemented):
        engine.run_script("SELECT 1;", tmp_path / "anything.db")


def test_raises_with_memory(engine: PytursoEngine) -> None:
    with pytest.raises(EngineNotImplemented):
        engine.run_script("SELECT 1;", None)


# --- the signal is honest and distinguishable ------------------------------
def test_exception_carries_scope_note(engine: PytursoEngine) -> None:
    with pytest.raises(EngineNotImplemented, match="not yet implemented"):
        engine.run_script("SELECT 1;", None)


def test_exception_is_not_a_sqlite3_error_class() -> None:
    # NOT-IMPLEMENTED is a harness verdict, not a SQL error: it must NOT be an
    # instance of the error-class vocabulary (which are plain str comparison
    # classes). EngineNotImplemented is its own exception type so the reporter
    # dispatches on type, not on str content.
    assert issubclass(EngineNotImplemented, Exception)
    # And it is distinct from the oracle-failure channel (AdapterError) and the
    # fixture channel (FixtureError) — different exception hierarchies, so the
    # reporter dispatches on type to different verdicts (NOT-IMPLEMENTED /
    # ERROR / setup-problem).
    from tests.differential.tursodb_adapter import AdapterError
    from tests.differential.engine import FixtureError

    assert not issubclass(EngineNotImplemented, AdapterError)
    assert not issubclass(EngineNotImplemented, FixtureError)


def test_does_not_crash_or_swallow(engine: PytursoEngine) -> None:
    # The harness's defining Phase 0 exit criterion: pyturso reports
    # NOT-IMPLEMENTED *without crashing*. Concretely, run_script must raise
    # EngineNotImplemented (not return garbage, not raise something else).
    try:
        engine.run_script("SELECT 1;", None)
    except EngineNotImplemented:
        return  # expected: the honest signal
    except Exception as exc:  # pragma: no cover - would be a regression
        pytest.fail(f"pyturso crashed instead of signalling NOT-IMPLEMENTED: {exc!r}")
    pytest.fail("pyturso returned a result instead of signalling NOT-IMPLEMENTED")
