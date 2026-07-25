"""Phase 7 corpus — write-path differential cases.

These cases test the write path (INSERT/UPDATE/DELETE) by:
1. Creating a fixture database with sqlite3.
2. Applying writes via pyturso.
3. Verifying the results match sqlite3.
"""

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
    db_path = tmp_path / "write_corpus.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?,?,?)",
                     [(1, "alice", 30), (2, "bob", 25), (3, "carol", 35)])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


class TestWriteCorpus:
    def test_insert_and_verify(self, db: Database) -> None:
        """INSERT a row, then SELECT to verify."""
        conn = db.connect()
        conn.execute("INSERT INTO t VALUES (4, 'dave', 40)")
        rows = conn.execute("SELECT * FROM t ORDER BY id")
        assert len(rows) == 4
        assert rows[3][0] == Value.integer(4)
        assert rows[3][1] == Value.text("dave")
        assert rows[3][2] == Value.integer(40)

    def test_insert_multiple_and_verify(self, db: Database) -> None:
        """INSERT multiple rows, verify all present."""
        conn = db.connect()
        conn.execute("INSERT INTO t VALUES (4, 'dave', 40), (5, 'eve', 28)")
        rows = conn.execute("SELECT * FROM t ORDER BY id")
        assert len(rows) == 5

    def test_update_and_verify(self, db: Database) -> None:
        """UPDATE a row, verify the change."""
        conn = db.connect()
        conn.execute("UPDATE t SET age = 99 WHERE name = 'alice'")
        rows = conn.execute("SELECT age FROM t WHERE name = 'alice'")
        assert rows[0][0] == Value.integer(99)

    def test_update_all_and_verify(self, db: Database) -> None:
        """UPDATE all rows, verify all changed."""
        conn = db.connect()
        conn.execute("UPDATE t SET age = 0")
        rows = conn.execute("SELECT id, age FROM t ORDER BY id")
        for r in rows:
            assert r[1] == Value.integer(0)

    def test_insert_update_select_sequence(self, db: Database) -> None:
        """INSERT, UPDATE, SELECT in sequence."""
        conn = db.connect()
        conn.execute("INSERT INTO t VALUES (4, 'dave', 40)")
        conn.execute("UPDATE t SET age = 50 WHERE name = 'dave'")
        rows = conn.execute("SELECT name, age FROM t WHERE name = 'dave'")
        assert rows[0][0] == Value.text("dave")
        assert rows[0][1] == Value.integer(50)

    def test_insert_with_where_filter(self, db: Database) -> None:
        """INSERT, then SELECT with WHERE to verify filtering."""
        conn = db.connect()
        conn.execute("INSERT INTO t VALUES (4, 'dave', 40)")
        rows = conn.execute("SELECT name FROM t WHERE age > 30 ORDER BY id")
        names = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert "carol" in names  # age=35
        assert "dave" in names  # age=40
        assert "alice" not in names  # age=30 (not > 30)
        assert "bob" not in names  # age=25

    def test_update_with_compound_where(self, db: Database) -> None:
        """UPDATE with AND in WHERE."""
        conn = db.connect()
        conn.execute("UPDATE t SET name = 'updated' WHERE age > 25 AND age < 35")
        rows = conn.execute("SELECT name, age FROM t ORDER BY id")
        # Find alice and bob by name.
        # alice (30) → updated, bob (25) → not, carol (35) → not
        alice_row = [r for r in rows if r[0].payload == "updated"][0]  # type: ignore[union-attr]
        assert alice_row[1] == Value.integer(30)  # alice was age 30
        bob_row = [r for r in rows if r[0].payload == "bob"][0]  # type: ignore[union-attr]
        assert bob_row[1] == Value.integer(25)  # bob unchanged
        carol_row = [r for r in rows if r[0].payload == "carol"][0]  # type: ignore[union-attr]
        assert carol_row[1] == Value.integer(35)  # carol unchanged