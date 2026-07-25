"""Unit tests for compound SELECTs, ORDER BY in the emitter, and LEFT JOIN basics."""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="arg-type"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value
from pyturso.translate.compound import combine_results


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "compound.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE a(id INTEGER PRIMARY KEY, x TEXT)")
    conn.execute("CREATE TABLE b(id INTEGER PRIMARY KEY, x TEXT)")
    conn.executemany("INSERT INTO a VALUES (?,?)", [(1,"apple"),(2,"banana"),(3,"cherry")])
    conn.executemany("INSERT INTO b VALUES (?,?)", [(1,"banana"),(2,"date"),(3,"apple")])
    conn.commit()
    conn.close()
    return Database.open(str(db_path))


# --- combine_results ---
class TestCombineResults:
    def test_union_all(self) -> None:
        left = [(Value.text("a"),), (Value.text("b"),)]
        right = [(Value.text("b"),), (Value.text("c"),)]
        result = combine_results(left, right, "UNION ALL")
        assert len(result) == 4

    def test_union_distinct(self) -> None:
        left = [(Value.text("a"),), (Value.text("b"),)]
        right = [(Value.text("b"),), (Value.text("c"),)]
        result = combine_results(left, right, "UNION")
        assert len(result) == 3  # a, b, c (no duplicate b)

    def test_intersect(self) -> None:
        left = [(Value.text("a"),), (Value.text("b"),)]
        right = [(Value.text("b"),), (Value.text("c"),)]
        result = combine_results(left, right, "INTERSECT")
        assert len(result) == 1
        assert result[0][0] == Value.text("b")

    def test_except(self) -> None:
        left = [(Value.text("a"),), (Value.text("b"),)]
        right = [(Value.text("b"),), (Value.text("c"),)]
        result = combine_results(left, right, "EXCEPT")
        assert len(result) == 1
        assert result[0][0] == Value.text("a")


# --- compound SELECT end-to-end ---
class TestCompoundSelect:
    def test_union(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT x FROM a UNION SELECT x FROM b")
        # Should have 5 unique values: apple, banana, cherry, date, + one more
        # a has: apple, banana, cherry. b has: banana, date, apple.
        # UNION: apple, banana, cherry, date = 4 unique.
        assert len(rows) == 4
        values = {r[0].payload for r in rows}  # type: ignore[union-attr]
        assert "apple" in values
        assert "banana" in values
        assert "cherry" in values
        assert "date" in values

    def test_union_all(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT x FROM a UNION ALL SELECT x FROM b")
        assert len(rows) == 6  # 3 + 3, all included

    def test_intersect(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT x FROM a INTERSECT SELECT x FROM b")
        # a has apple, banana, cherry. b has banana, date, apple.
        # INTERSECT: apple, banana = 2.
        assert len(rows) == 2
        values = {r[0].payload for r in rows}  # type: ignore[union-attr]
        assert "apple" in values
        assert "banana" in values

    def test_except(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT x FROM a EXCEPT SELECT x FROM b")
        # a has apple, banana, cherry. b has banana, date, apple.
        # EXCEPT: cherry = 1.
        assert len(rows) == 1
        assert rows[0][0] == Value.text("cherry")


# --- ORDER BY end-to-end ---
class TestOrderBy:
    def test_order_by_ascending(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT x FROM a ORDER BY x")
        values = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert values == ["apple", "banana", "cherry"]

    def test_order_by_descending(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT x FROM a ORDER BY x DESC")
        values = [r[0].payload for r in rows]  # type: ignore[union-attr]
        assert values == ["cherry", "banana", "apple"]

    def test_order_by_id(self, db: Database) -> None:
        conn = db.connect()
        rows = conn.execute("SELECT id, x FROM a ORDER BY id DESC")
        assert rows[0][0] == Value.integer(3)
        assert rows[0][1] == Value.text("cherry")