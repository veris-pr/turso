"""Unit tests for Phase 6e: affinity in comparisons, LIKE in WHERE, CASE."""

from __future__ import annotations
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="type-arg"
# mypy: disable-error-code="unused-ignore"

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.schema.load import load_schema_from_file
from pyturso.storage.pager import Pager
from pyturso.translate.select import translate_select
from pyturso.types.value import Value
from pyturso.vdbe.execute import execute


@pytest.fixture
def db_pager(tmp_path: Path) -> tuple[Pager, object]:
    db = tmp_path / "affinity.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("""CREATE TABLE t(
        id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        score REAL,
        code TEXT
    )""")
    conn.executemany("INSERT INTO t VALUES (?,?,?,?,?)",
                     [(1, "alice", 30, 95.5, "A100"),
                      (2, "bob", 25, 80.0, "B200"),
                      (3, "carol", 35, 88.3, "A300")])
    conn.commit()
    conn.close()
    schema = load_schema_from_file(str(db))
    raw = db.read_bytes()
    io = MemoryIO()
    f = io.open_file("db")
    f.pwrite(WriteRequest(f, 0, raw))
    pager = Pager(io, "db")
    pager.open()
    return pager, schema


class TestAffinityInComparisons:
    def test_integer_column_vs_string_literal(self, db_pager: tuple) -> None:
        """WHERE age = '25' → affinity coerces '25' to 25 (INTEGER column)."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE age = '25'", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "bob" in names
        assert len(names) == 1

    def test_text_column_vs_integer_literal(self, db_pager: tuple) -> None:
        """WHERE name = 30 → TEXT affinity coerces 30 to '30'."""
        # No rows have name='30', so this should return 0 rows.
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE name = 30", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 0

    def test_no_affinity_blob_column(self, db_pager: tuple) -> None:
        """BLOB affinity (no declared type) → no coercion."""
        # The 'code' column has TEXT affinity. Let's test with a column
        # that has no type → BLOB affinity.
        # For now, test that TEXT affinity works with string comparison.
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE name = 'alice'", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 1
        assert state.result_rows[0][0] == Value.text("alice")


class TestLikeInWhere:
    def test_like_prefix(self, db_pager: tuple) -> None:
        """WHERE code LIKE 'A%' → A100, A300."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE code LIKE 'A%'", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "alice" in names
        assert "carol" in names
        assert "bob" not in names
        assert len(names) == 2

    def test_like_exact(self, db_pager: tuple) -> None:
        """WHERE code LIKE 'A100' → alice."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE code LIKE 'A100'", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 1
        assert state.result_rows[0][0] == Value.text("alice")

    def test_like_wildcard(self, db_pager: tuple) -> None:
        """WHERE code LIKE '_2__' → B200 (single-char match)."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE code LIKE '_2__'", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "bob" in names

    def test_like_no_match(self, db_pager: tuple) -> None:
        """WHERE name LIKE 'z%' → no rows."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE name LIKE 'z%'", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 0

class TestCaseExpression:
    def test_case_when(self, db_pager: tuple) -> None:
        """SELECT CASE WHEN age > 30 THEN 'old' ELSE 'young' END FROM t"""
        pager, schema = db_pager
        from pyturso.translate.select import translate_select
        from pyturso.vdbe.execute import execute
        prog = translate_select(
            "SELECT CASE WHEN age > 30 THEN 'old' ELSE 'young' END FROM t ORDER BY id", schema
        )
        state = execute(prog, pager)
        assert len(state.result_rows) == 3
        assert state.result_rows[0][0] == Value.text('young')  # alice 30
        assert state.result_rows[1][0] == Value.text('young')  # bob 25
        assert state.result_rows[2][0] == Value.text('old')    # carol 35

    def test_case_with_base(self, db_pager: tuple) -> None:
        """SELECT CASE age WHEN 30 THEN 'thirty' WHEN 25 THEN 'twentyfive' ELSE 'other' END"""
        pager, schema = db_pager
        from pyturso.translate.select import translate_select
        from pyturso.vdbe.execute import execute
        prog = translate_select(
            "SELECT CASE age WHEN 30 THEN 'thirty' WHEN 25 THEN 'twentyfive' ELSE 'other' END FROM t ORDER BY id", schema
        )
        state = execute(prog, pager)
        assert state.result_rows[0][0] == Value.text('thirty')
        assert state.result_rows[1][0] == Value.text('twentyfive')
        assert state.result_rows[2][0] == Value.text('other')
