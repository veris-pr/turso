"""Integration test: SQL → translate → VDBE execute → compare with sqlite3.

The Phase 5 end-to-end pipeline: parse SQL, plan against the schema, emit a
VDBE program, execute it, and verify the result rows match what sqlite3 returns.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.schema.load import load_schema_from_file
from pyturso.schema.objects import Schema
from pyturso.storage.pager import Pager
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute
from pyturso.types.value import Value


@pytest.fixture
def db_and_schema(tmp_path: Path) -> tuple[Pager, object]:
    db = tmp_path / "trans.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?, ?, ?)",
                     [(1, "alice", 30), (2, "bob", 25), (3, "carol", 35)])
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


class TestTranslateAndExecute:
    def test_select_star(self, db_and_schema: tuple[Pager, Schema]) -> None:
        pager, schema = db_and_schema
        prog = translate_select("SELECT * FROM t", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 3

    def test_select_name(self, db_and_schema: tuple[Pager, Schema]) -> None:
        pager, schema = db_and_schema
        prog = translate_select("SELECT name FROM t", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 3
        assert state.result_rows[0][0] == Value.text("alice")
        assert state.result_rows[1][0] == Value.text("bob")
        assert state.result_rows[2][0] == Value.text("carol")

    def test_select_id_and_name(self, db_and_schema: tuple[Pager, Schema]) -> None:
        pager, schema = db_and_schema
        prog = translate_select("SELECT id, name FROM t", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 3
        assert state.result_rows[0][0] == Value.integer(1)
        assert state.result_rows[0][1] == Value.text("alice")

    def test_where_gt(self, db_and_schema: tuple[Pager, Schema]) -> None:
        """SELECT name FROM t WHERE age > 28 → alice, carol."""
        pager, schema = db_and_schema
        prog = translate_select("SELECT name FROM t WHERE age > 28", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 2
        names = [row[0].payload for row in state.result_rows]
        assert "alice" in names
        assert "carol" in names

    def test_where_eq(self, db_and_schema: tuple[Pager, Schema]) -> None:
        """SELECT * FROM t WHERE name = 'bob' → 1 row."""
        pager, schema = db_and_schema
        prog = translate_select("SELECT * FROM t WHERE name = 'bob'", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 1
        assert state.result_rows[0][0] == Value.integer(2)

    def test_where_on_rowid_alias(self, db_and_schema: tuple[Pager, Schema]) -> None:
        """SELECT name FROM t WHERE id = 2 → bob (uses Rowid for the alias)."""
        pager, schema = db_and_schema
        prog = translate_select("SELECT name FROM t WHERE id = 2", schema)
        state = execute(prog, pager)
        assert len(state.result_rows) == 1
        assert state.result_rows[0][0] == Value.text("bob")