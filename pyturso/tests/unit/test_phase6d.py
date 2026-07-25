"""Unit tests for Phase 6d: AND/OR, IS/ISNULL, BETWEEN, IN in WHERE."""

from __future__ import annotations
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="type-arg"

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
    db = tmp_path / "where.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER, city TEXT)")
    conn.executemany("INSERT INTO t VALUES (?,?,?,?)",
                     [(1, "alice", 30, "NYC"), (2, "bob", 25, "LA"),
                      (3, "carol", 35, "NYC"), (4, "dave", 40, "SF")])
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


class TestWhereExpressions:
    def test_and(self, db_pager: tuple) -> None:
        """WHERE age > 25 AND city = 'NYC' → alice."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE age > 25 AND city = 'NYC'", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "alice" in names
        # carol is 35 and NYC → should be included
        # Actually carol IS 35 AND NYC → should match. Let me check.
        # age > 25: alice(30), carol(35), dave(40) match.
        # city = 'NYC': alice, carol match.
        # AND: alice, carol match.
        assert "carol" in names

    def test_or(self, db_pager: tuple) -> None:
        """WHERE city = 'LA' OR city = 'SF' → bob, dave."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE city = 'LA' OR city = 'SF'", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "bob" in names
        assert "dave" in names
        assert "alice" not in names

    def test_between(self, db_pager: tuple) -> None:
        """WHERE age BETWEEN 25 AND 35 → alice, bob, carol."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE age BETWEEN 25 AND 35", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "alice" in names
        assert "bob" in names
        assert "carol" in names
        assert "dave" not in names

    def test_not_between(self, db_pager: tuple) -> None:
        """WHERE age NOT BETWEEN 25 AND 35 → dave."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE age NOT BETWEEN 25 AND 35", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "dave" in names
        assert "alice" not in names

    def test_in(self, db_pager: tuple) -> None:
        """WHERE city IN ('LA', 'SF') → bob, dave."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE city IN ('LA', 'SF')", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "bob" in names
        assert "dave" in names
        assert "alice" not in names

    def test_not_in(self, db_pager: tuple) -> None:
        """WHERE city NOT IN ('LA', 'SF') → alice, carol."""
        pager, schema = db_pager
        prog = translate_select("SELECT name FROM t WHERE city NOT IN ('LA', 'SF')", schema)
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "alice" in names
        assert "carol" in names
        assert "bob" not in names

    def test_compound_and_or(self, db_pager: tuple) -> None:
        """WHERE age > 30 AND (city = 'NYC' OR city = 'SF') → carol, dave."""
        pager, schema = db_pager
        prog = translate_select(
            "SELECT name FROM t WHERE age > 30 AND (city = 'NYC' OR city = 'SF')", schema
        )
        state = execute(prog, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "carol" in names
        assert "dave" in names