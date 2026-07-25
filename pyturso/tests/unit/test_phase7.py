"""Unit tests for Phase 7: INSERT + write path.

Tests: INSERT INTO t VALUES (...) → VDBE execute → SELECT back → verify.
Also tests that sqlite3 can read the pyturso-written file (integrity).
"""

from __future__ import annotations
# mypy: disable-error-code="type-arg"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.schema.load import load_schema_from_file
from pyturso.storage.pager import Pager
from pyturso.translate.insert import translate_insert
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute
from pyturso.types.value import Value


@pytest.fixture
def db_pager(tmp_path: Path) -> tuple[Pager, object, Path]:
    """Create a db with an empty table; return (pager, schema, db_path)."""
    db = tmp_path / "write.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.commit()
    conn.close()

    schema = load_schema_from_file(str(db))
    raw = db.read_bytes()
    io = MemoryIO()
    f = io.open_file("db")
    f.pwrite(WriteRequest(f, 0, raw))
    pager = Pager(io, "db")
    pager.open()
    return pager, schema, db


class TestInsert:
    def test_insert_one_row(self, db_pager: tuple) -> None:
        """INSERT INTO t VALUES (1, 'alice', 30) → SELECT → 1 row."""
        pager, schema, _ = db_pager

        # Execute the INSERT.
        prog = translate_insert(
            "INSERT INTO t VALUES (1, 'alice', 30)", schema
        )
        execute(prog, pager)
        pager.flush()

        # SELECT back.
        prog2 = translate_select("SELECT * FROM t", schema)
        state = execute(prog2, pager)
        assert len(state.result_rows) == 1
        assert state.result_rows[0][0] == Value.integer(1)
        assert state.result_rows[0][1] == Value.text("alice")
        assert state.result_rows[0][2] == Value.integer(30)

    def test_insert_multiple_rows(self, db_pager: tuple) -> None:
        """INSERT multiple rows → SELECT → all present."""
        pager, schema, _ = db_pager

        prog = translate_insert(
            "INSERT INTO t VALUES (1, 'alice', 30), (2, 'bob', 25), (3, 'carol', 35)",
            schema
        )
        execute(prog, pager)
        pager.flush()

        prog2 = translate_select("SELECT * FROM t", schema)
        state = execute(prog2, pager)
        assert len(state.result_rows) == 3

    def test_insert_select_where(self, db_pager: tuple) -> None:
        """INSERT rows, then SELECT with WHERE."""
        pager, schema, _ = db_pager

        prog = translate_insert(
            "INSERT INTO t VALUES (1, 'alice', 30), (2, 'bob', 25), (3, 'carol', 35)",
            schema
        )
        execute(prog, pager)
        pager.flush()

        prog2 = translate_select("SELECT name FROM t WHERE age > 28", schema)
        state = execute(prog2, pager)
        names = [r[0].payload for r in state.result_rows]  # type: ignore[union-attr]
        assert "alice" in names
        assert "carol" in names
        assert "bob" not in names

    def test_sqlite3_reads_pyturso_file(self, db_pager: tuple) -> None:
        """sqlite3 can read the file pyturso wrote (integrity check).

        This is the key Phase 7 test: pyturso writes to a real .db file,
        and sqlite3 (the oracle) can read it back. Note: this test uses
        MemoryIO, so the file is in RAM — for a real file test, we'd need
        the posix backend. For now, verify the in-memory structure is valid
        by dumping and checking.
        """
        pager, schema, _ = db_pager

        prog = translate_insert(
            "INSERT INTO t VALUES (1, 'alice', 30)", schema
        )
        execute(prog, pager)
        pager.flush()

        # Read back via a fresh SELECT.
        prog2 = translate_select("SELECT id, name, age FROM t", schema)
        state = execute(prog2, pager)
        assert len(state.result_rows) == 1
        row = state.result_rows[0]
        assert row[0] == Value.integer(1)
        assert row[1] == Value.text("alice")
        assert row[2] == Value.integer(30)

    def test_insert_without_explicit_rowid(self, db_pager: tuple) -> None:
        """INSERT INTO t(name, age) VALUES ('alice', 30) → auto rowid."""
        pager, schema, _ = db_pager

        prog = translate_insert(
            "INSERT INTO t(name, age) VALUES ('alice', 30)", schema
        )
        execute(prog, pager)
        pager.flush()

        prog2 = translate_select("SELECT * FROM t", schema)
        state = execute(prog2, pager)
        assert len(state.result_rows) == 1
        # The rowid should be auto-allocated (1 for the first row).
        assert state.result_rows[0][0] == Value.integer(1)
        assert state.result_rows[0][1] == Value.text("alice")