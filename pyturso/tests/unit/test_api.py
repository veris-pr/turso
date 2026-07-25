"""Unit tests for the public API: Database, Connection, Statement.

Tests the end-to-end user-facing API:
  db = Database.open(path) or Database.open_memory()
  conn = db.connect()
  rows = conn.execute("SELECT ...")
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="no-untyped-def"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.connection import Connection
from pyturso.statement import Statement
from pyturso.types.value import Value


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a db with a table and data, opened as a pyturso Database."""
    db_path = tmp_path / "api.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?, ?, ?)",
                     [(1, "alice", 30), (2, "bob", 25), (3, "carol", 35)])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


class TestDatabase:
    def test_open(self, db: Database) -> None:
        assert db.pager is not None
        assert db.pager.page_size == 4096

    def test_connect(self, db: Database) -> None:
        conn = db.connect()
        assert isinstance(conn, Connection)

    def test_open_memory(self) -> None:
        db = Database.open_memory()
        conn = db.connect()
        rows = conn.execute("SELECT * FROM _init")
        assert isinstance(rows, list)

    def test_from_bytes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "raw.db"
        c = sqlite3.connect(str(db_path))
        c.execute("CREATE TABLE t(x INTEGER PRIMARY KEY, y TEXT)")
        c.execute("INSERT INTO t VALUES (1, 'hello')")
        c.commit()
        c.close()
        raw = db_path.read_bytes()
        db = Database.from_bytes(raw)
        conn = db.connect()
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 1
        assert rows[0][0] == Value.integer(1)
        assert rows[0][1] == Value.text("hello")


class TestConnection:
    def test_execute_select(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT name FROM t")
        assert len(rows) == 3
        assert rows[0][0] == Value.text("alice")
        assert rows[1][0] == Value.text("bob")
        assert rows[2][0] == Value.text("carol")

    def test_execute_select_where(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT name FROM t WHERE age > 28")
        assert len(rows) == 2
        names = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert "alice" in names
        assert "carol" in names

    def test_execute_select_all(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 3
        assert rows[0][0] == Value.integer(1)
        assert rows[0][1] == Value.text("alice")
        assert rows[0][2] == Value.integer(30)

    def test_schema_cached(self, db: Database) -> None:
        conn = db.connect()
        s1 = conn.schema
        s2 = conn.schema
        assert s1 is s2  # same object (cached)

    def test_prepare(self, db: Database) -> None:
        conn = db.connect()
        prog = conn.prepare("SELECT * FROM t")
        assert prog is not None
        assert len(prog.insns) > 0

    def test_execute_insert(self, db: Database) -> None:
        conn = db.connect()
        conn.execute("INSERT INTO t VALUES (4, 'dave', 40)")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 4

    def test_execute_unsupported(self, db: Database) -> None:
        conn = db.connect()
        with pytest.raises(Exception):
            conn.execute("DROP TABLE t")

    def test_transaction_control(self, db: Database) -> None:
        conn = db.connect()
        assert not conn.in_transaction
        conn.execute("BEGIN")
        assert conn.in_transaction
        conn.execute("COMMIT")
        assert not conn.in_transaction


class TestStatement:
    def test_step(self, db: Database) -> None:
        conn = db.connect()
        prog = conn.prepare("SELECT name FROM t")
        stmt = Statement(prog, db.pager)
        row = stmt.step()
        assert row is not None
        assert row[0] == Value.text("alice")
        row = stmt.step()
        assert row is not None
        assert row[0] == Value.text("bob")
        row = stmt.step()
        assert row is not None
        assert row[0] == Value.text("carol")
        row = stmt.step()
        assert row is None  # done

    def test_run(self, db: Database) -> None:
        conn = db.connect()
        prog = conn.prepare("SELECT name FROM t")
        stmt = Statement(prog, db.pager)
        rows = stmt.run()
        assert len(rows) == 3

    def test_reset(self, db: Database) -> None:
        conn = db.connect()
        prog = conn.prepare("SELECT name FROM t")
        stmt = Statement(prog, db.pager)
        stmt.step()  # consume first row
        stmt.reset()
        row = stmt.step()
        assert row is not None
        assert row[0] == Value.text("alice")  # back to first row

    def test_finalize(self, db: Database) -> None:
        conn = db.connect()
        prog = conn.prepare("SELECT name FROM t")
        stmt = Statement(prog, db.pager)
        stmt.finalize()
        with pytest.raises(Exception):
            stmt.step()

    def test_iter(self, db: Database) -> None:
        conn = db.connect()
        prog = conn.prepare("SELECT name FROM t")
        stmt = Statement(prog, db.pager)
        names = [row[0].payload for row in stmt]  # type: ignore[union-attr]
        assert names == ["alice", "bob", "carol"]

    def test_two_statements_independent(self, db: Database) -> None:
        conn = db.connect()
        prog1 = conn.prepare("SELECT name FROM t")
        prog2 = conn.prepare("SELECT age FROM t")
        stmt1 = Statement(prog1, db.pager)
        stmt2 = Statement(prog2, db.pager)
        row1 = stmt1.step()
        row2 = stmt2.step()
        assert row1 is not None and row2 is not None
        assert row1[0] == Value.text("alice")
        assert row2[0] == Value.integer(30)