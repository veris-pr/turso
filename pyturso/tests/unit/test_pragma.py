"""Unit tests for PRAGMA support + VDBE metrics."""

from __future__ import annotations
# mypy: disable-error-code="operator"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.insn import Halt, Init, Integer, ResultRow
from pyturso.vdbe.execute import execute


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "pragma.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER)")
    conn.execute("CREATE INDEX idx_age ON t(age)")
    conn.executemany("INSERT INTO t VALUES (?,?,?)", [(1, "alice", 30), (2, "bob", 25)])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


class TestPragma:
    def test_table_info(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA table_info(t)")
        assert len(rows) == 3  # id, name, age
        # cid=0, name=id, type=INTEGER, notnull=0, dflt=NULL, pk=1
        assert rows[0][0].is_integer
        assert rows[0][1] == Value.text("id")
        assert rows[0][2] == Value.text("INTEGER")
        assert rows[0][5] == Value.integer(1)  # pk

    def test_table_info_not_null(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA table_info(t)")
        # name column has NOT NULL
        assert rows[1][3] == Value.integer(1)  # notnull=1

    def test_index_list(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA index_list(t)")
        assert len(rows) == 1
        assert rows[0][1] == Value.text("idx_age")
        assert rows[0][2].is_integer

    def test_page_count(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA page_count")
        assert len(rows) == 1
        assert rows[0][0].is_integer
        assert rows[0][0].payload >= 2  # type: ignore[comparison-overlap]

    def test_journal_mode(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA journal_mode")
        assert rows[0][0] == Value.text("memory")

    def test_schema_version(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA schema_version")
        assert len(rows) == 1
        assert rows[0][0].is_integer

    def test_unknown_pragma(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("PRAGMA unknown_pragma")
        assert len(rows) == 0


class TestVdbeMetrics:
    def test_opcode_counter(self, db: Database) -> None:
        """Basic opcode count test — verify the VM executes all instructions."""
        b = ProgramBuilder()
        r1 = b.alloc_register()
        b.emit(Init())
        b.emit(Integer(42, r1))
        b.emit(ResultRow(start_reg=r1, count=1))
        b.emit(Halt())
        prog = b.finalize()
        state = execute(prog, db.pager)
        assert len(state.result_rows) == 1
        assert state.result_rows[0][0] == Value.integer(42)