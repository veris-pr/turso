"""Unit tests for tests.differential.sqlite3_adapter.

Verified against: the per-statement / errors-by-class contract in
tests/differential/README.md and the result model in tests.differential.engine.
sqlite3 itself is the oracle, so rows are asserted as sqlite3 actually returns
them (tuples of typed values).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.errors import INTEGRITY_ERROR, OPERATIONAL_ERROR
from tests.differential.engine import Engine, FixtureError
from tests.differential.sqlite3_adapter import Sqlite3Engine


@pytest.fixture
def engine() -> Sqlite3Engine:
    return Sqlite3Engine()


# --- protocol conformance --------------------------------------------------
class TestProtocol:
    def test_is_an_engine(self, engine: Sqlite3Engine) -> None:
        assert isinstance(engine, Engine)


# --- per-statement rows ----------------------------------------------------
class TestRows:
    def test_single_select_returns_one_result(self, engine: Sqlite3Engine) -> None:
        # Cells are rendered canonical text (Design B).
        out = engine.run_script("SELECT 1;", None)
        assert out == [[("1",)]]

    def test_two_selects_two_results_in_order(self, engine: Sqlite3Engine) -> None:
        out = engine.run_script("SELECT 1; SELECT 2;", None)
        assert out == [[("1",)], [("2",)]]

    def test_non_row_statement_is_empty_rows(self, engine: Sqlite3Engine) -> None:
        # CREATE/INSERT contribute an empty Rows entry so the per-statement
        # index stays aligned across engines.
        out = engine.run_script("CREATE TABLE t(x);", None)
        assert out == [[]]

    def test_select_star_multirow(self, engine: Sqlite3Engine) -> None:
        out = engine.run_script(
            "CREATE TABLE t(x); INSERT INTO t VALUES (1),(2),(3); SELECT * FROM t;",
            None,
        )
        assert out == [[], [], [("1",), ("2",), ("3",)]]

    def test_typed_values_rendered_canonical(
        self, engine: Sqlite3Engine
    ) -> None:
        # NULL -> "NULL", float -> %.15g, text verbatim, blob -> x'<hex>'.
        out = engine.run_script("SELECT NULL, 1.5, 'x', x'00ff';", None)
        assert out == [[("NULL", "1.5", "x", "x'00ff'")]]


# --- error handling: errors reported by class, run stops -------------------
class TestErrors:
    def test_parse_error_is_operational_and_stops_run(
        self, engine: Sqlite3Engine
    ) -> None:
        out = engine.run_script("SELECT 1; THIS IS NOT SQL; SELECT 2;", None)
        # First statement ran; second errored and stopped the run.
        assert out == [[("1",)], OPERATIONAL_ERROR]

    def test_integrity_error_maps_to_integrity_class(
        self, engine: Sqlite3Engine
    ) -> None:
        out = engine.run_script(
            "CREATE TABLE t(x UNIQUE); INSERT INTO t VALUES (1),(1);",
            None,
        )
        assert out == [[], INTEGRITY_ERROR]

    def test_no_such_table_is_operational(self, engine: Sqlite3Engine) -> None:
        out = engine.run_script("SELECT * FROM nope;", None)
        assert out == [OPERATIONAL_ERROR]

    def test_programming_error_keeps_its_class(self, engine: Sqlite3Engine) -> None:
        # sqlite3 reports a wrong-arg-count as OperationalError
        # ("table t has 2 columns but 1 values was supplied"), not
        # ProgrammingError — that is the real oracle behaviour we must mirror.
        out = engine.run_script(
            "CREATE TABLE t(a,b); INSERT INTO t VALUES (1);", None
        )
        assert out == [[], OPERATIONAL_ERROR]


# --- isolation: each run is independent ------------------------------------
class TestIsolation:
    def test_each_call_starts_fresh(self, engine: Sqlite3Engine) -> None:
        # No schema leaks between calls (per-call connection in-memory).
        a = engine.run_script("CREATE TABLE a(x); SELECT * FROM a;", None)
        b = engine.run_script("SELECT * FROM a;", None)
        assert a == [[], []]
        # Second call has no table `a` — fresh database.
        assert b == [OPERATIONAL_ERROR]


# --- fixture handling ------------------------------------------------------
class TestFixture:
    def test_missing_fixture_raises_fixtureerror(
        self, engine: Sqlite3Engine, tmp_path: Path
    ) -> None:
        missing = tmp_path / "nope.db"
        with pytest.raises(FixtureError) as exc:
            engine.run_script("SELECT 1;", missing)
        assert exc.value.db_path == missing

    def test_runs_against_a_real_fixture(
        self, engine: Sqlite3Engine, tmp_path: Path
    ) -> None:
        # Build a fixture with stdlib sqlite3 (the way tools.mkdb will), then
        # run a script against it through the adapter.
        fpath = tmp_path / "people.db"
        conn = sqlite3.connect(str(fpath))
        conn.execute("CREATE TABLE people(name, age)")
        conn.executemany("INSERT INTO people VALUES (?,?)", [("ada", 36), ("bob", 7)])
        conn.commit()
        conn.close()
        out = engine.run_script("SELECT name FROM people ORDER BY age;", fpath)
        assert out == [[("bob",), ("ada",)]]
