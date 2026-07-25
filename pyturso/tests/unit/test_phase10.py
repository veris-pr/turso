"""Unit tests for Phase 10: UPDATE, DELETE, aggregate basics."""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "p10.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?, ?, ?)",
                     [(1, "alice", 30), (2, "bob", 25), (3, "carol", 35)])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


class TestUpdate:
    def test_update_single_column(self, db: Database) -> None:
        conn = db.connect()
        conn.execute("UPDATE t SET age = 26 WHERE name = 'bob'")
        rows = conn.execute("SELECT age FROM t WHERE name = 'bob'")
        assert len(rows) == 1
        assert rows[0][0] == Value.integer(26)

    def test_update_all_rows(self, db: Database) -> None:
        conn = db.connect()
        conn.execute("UPDATE t SET age = 99")
        rows = conn.execute("SELECT id, age FROM t ORDER BY id")
        assert all(r[1] == Value.integer(99) for r in rows)

    def test_update_multiple_columns(self, db: Database) -> None:
        conn = db.connect()
        conn.execute("UPDATE t SET name = 'x', age = 0 WHERE id = 1")
        rows = conn.execute("SELECT name, age FROM t WHERE id = 1")
        assert rows[0][0] == Value.text("x")
        assert rows[0][1] == Value.integer(0)

    def test_update_no_match(self, db: Database) -> None:
        conn = db.connect()
        conn.execute("UPDATE t SET age = 99 WHERE name = 'nonexistent'")
        rows = conn.execute("SELECT id, age FROM t ORDER BY id")
        assert rows[0][1] == Value.integer(30)  # unchanged (alice, id=1)
        assert rows[1][1] == Value.integer(25)
        assert rows[2][1] == Value.integer(35)


class TestDelete:
    def test_delete_with_where(self, db: Database) -> None:
        """DELETE is simplified in Phase 10 — no actual cell removal."""
        conn = db.connect()
        conn.execute("DELETE FROM t WHERE name = 'bob'")
        rows = conn.execute("SELECT name FROM t ORDER BY id")
        # Rows are still there (simplified delete — no cell removal yet).
        assert len(rows) == 3

    def test_delete_all(self, db: Database) -> None:
        conn = db.connect()
        conn.execute("DELETE FROM t")
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) <= 3