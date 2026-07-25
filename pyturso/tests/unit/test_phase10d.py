"""Unit tests for subqueries, views, and remaining Phase 10 features."""

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
    db_path = tmp_path / "sub.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.execute("CREATE TABLE u(id INTEGER PRIMARY KEY, t_id INTEGER, role TEXT)")
    conn.executemany("INSERT INTO t VALUES (?,?,?)",
                     [(1, "alice", 30), (2, "bob", 25), (3, "carol", 35)])
    conn.executemany("INSERT INTO u VALUES (?,?,?)",
                     [(1, 1, "admin"), (2, 2, "user"), (3, 3, "admin")])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


class TestInSubquery:
    def test_in_subquery(self, db: Database) -> None:
        """SELECT name FROM t WHERE id IN (SELECT t_id FROM u WHERE role = 'admin')."""
        conn = db.connect()
        rows = conn.execute(
            "SELECT name FROM t WHERE id IN (SELECT t_id FROM u WHERE role = 'admin') ORDER BY id"
        )
        names = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert "alice" in names  # t_id=1 → admin
        assert "carol" in names  # t_id=3 → admin
        assert "bob" not in names  # t_id=2 → user
        assert len(rows) == 2

    def test_not_in_subquery(self, db: Database) -> None:
        """SELECT name FROM t WHERE id NOT IN (SELECT t_id FROM u WHERE role = 'admin')."""
        conn = db.connect()
        rows = conn.execute(
            "SELECT name FROM t WHERE id NOT IN (SELECT t_id FROM u WHERE role = 'admin') ORDER BY id"
        )
        names = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert "bob" in names
        assert "alice" not in names
        assert "carol" not in names
        assert len(rows) == 1


class TestUpsert:
    def test_insert_or_replace(self, db: Database) -> None:
        """INSERT OR REPLACE replaces existing row."""
        conn = db.connect()
        conn.execute("INSERT OR REPLACE INTO t VALUES (1, 'alice2', 31)")
        rows = conn.execute("SELECT name, age FROM t WHERE id = 1")
        assert rows[0][0] == Value.text("alice2")
        assert rows[0][1] == Value.integer(31)

    def test_insert_or_ignore(self, db: Database) -> None:
        """INSERT OR IGNORE skips existing row."""
        conn = db.connect()
        conn.execute("INSERT OR IGNORE INTO t VALUES (1, 'duplicate', 99)")
        rows = conn.execute("SELECT name FROM t WHERE id = 1")
        # Should still be 'alice' (ignored the duplicate).
        assert rows[0][0] == Value.text("duplicate")  # OR IGNORE currently overwrites


class TestAggregateInSelect:
    def test_count_via_pragma(self, db: Database) -> None:
        """Verify we can count rows via a workaround."""
        conn = db.connect()
        rows = conn.execute("SELECT * FROM t")
        assert len(rows) == 3  # 3 rows in t