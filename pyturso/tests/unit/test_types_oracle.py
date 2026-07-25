"""Oracle pin — mixed-type ORDER BY and comparison against stdlib sqlite3.

Phase 2 exit criterion: property-style unit tests comparing mixed-type
ORDER BY and comparison results against stdlib sqlite3 directly. This is the
pre-Phase-6 oracle pin (the corpus runs later, once Phase 5 executes SQL).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from collections.abc import Sequence
from typing import Generator

import pytest

from pyturso.types.compare import compare_values, sort_key
from pyturso.types.value import Value


def _sqlite3_order_by(values: Sequence[object], conn: sqlite3.Connection) -> list[object]:
    """Run SELECT ... ORDER BY x via sqlite3; return the sorted values."""
    # Create a temp table, insert, order by, fetch.
    conn.execute("CREATE TABLE _pin (x)")
    conn.executemany("INSERT INTO _pin VALUES (?)", [(v,) for v in values])
    rows = conn.execute("SELECT x FROM _pin ORDER BY x").fetchall()
    conn.execute("DROP TABLE _pin")
    return [r[0] for r in rows]


def _to_value(v: object) -> Value:
    """Convert a Python value to a pyturso Value."""
    if v is None:
        return Value.null()
    if isinstance(v, bool):
        return Value.integer(int(v))
    if isinstance(v, int):
        return Value.integer(v)
    if isinstance(v, float):
        return Value.real(v)
    if isinstance(v, str):
        return Value.text(v)
    if isinstance(v, bytes):
        return Value.blob(v)
    raise TypeError(f"cannot convert {type(v)} to Value")


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


# --- mixed-type ORDER BY parity with sqlite3 -------------------------------
class TestMixedOrderBy:
    def test_null_int_text_blob_order(self, conn: sqlite3.Connection) -> None:
        """NULL < INTEGER < REAL < TEXT < BLOB — the defining cross-class order."""
        values = [42, "hello", None, 3.14, b"blob", -5, "world", 99.9, b"aaa"]
        expected = _sqlite3_order_by(values, conn)
        actual_values = sorted([_to_value(v) for v in values], key=sort_key)
        actual = [v.payload for v in actual_values]
        assert actual == expected

    def test_int_and_real_interleaved(self, conn: sqlite3.Connection) -> None:
        """INTEGER and REAL share the numeric class rank; sorted by value."""
        values = [1, 2.0, 3, 0.5, 1.5, 0]
        expected = _sqlite3_order_by(values, conn)
        actual_values = sorted([_to_value(v) for v in values], key=sort_key)
        actual = [v.payload for v in actual_values]
        assert actual == expected

    def test_text_ordering(self, conn: sqlite3.Connection) -> None:
        values = ["banana", "apple", "Cherry", "blueberry"]
        expected = _sqlite3_order_by(values, conn)
        actual_values = sorted([_to_value(v) for v in values], key=sort_key)
        actual = [v.payload for v in actual_values]
        assert actual == expected

    def test_all_nulls_equal(self, conn: sqlite3.Connection) -> None:
        values = [None, None, None]
        expected = _sqlite3_order_by(values, conn)
        actual_values = sorted([_to_value(v) for v in values], key=sort_key)
        assert len(actual_values) == 3
        assert all(v.is_null for v in actual_values)


# --- comparison result parity with sqlite3 ---------------------------------
class TestComparisonParity:
    @pytest.mark.parametrize("a,b", [
        (1, 2), (2, 1), (1, 1),
        (1.0, 2.0), (2.0, 1.0), (1.0, 1.0),
        (1, 1.0), (1, 2.0), (2, 1.0),
        (-1, 0), (0, -1), (-5, -10),
    ])
    def test_numeric_comparison_matches_sqlite3(
        self, conn: sqlite3.Connection, a: object, b: object
    ) -> None:
        """a < b / a = b / a > b must agree with sqlite3."""
        va = _to_value(a)
        vb = _to_value(b)
        py_cmp = compare_values(va, vb)
        sql_cmp = conn.execute(
            "SELECT CASE WHEN ? < ? THEN -1 WHEN ? > ? THEN 1 ELSE 0 END",
            (a, b, a, b)
        ).fetchone()[0]
        assert py_cmp == sql_cmp, f"compare({a}, {b}): pyturso={py_cmp}, sqlite3={sql_cmp}"

    def test_text_comparison_matches_sqlite3(self, conn: sqlite3.Connection) -> None:
        for a, b in [("a", "b"), ("b", "a"), ("a", "a"),
                     ("abc", "abc"), ("ABC", "abc"),
                     ("hello", "world"), ("", "a")]:
            py_cmp = compare_values(Value.text(a), Value.text(b))
            sql_cmp = conn.execute(
                "SELECT CASE WHEN ? < ? THEN -1 WHEN ? > ? THEN 1 ELSE 0 END",
                (a, b, a, b)
            ).fetchone()[0]
            assert py_cmp == sql_cmp, f"compare({a!r}, {b!r}): pyturso={py_cmp}, sqlite3={sql_cmp}"

    def test_null_comparison_matches_sqlite3(self, conn: sqlite3.Connection) -> None:
        """In SQLite, NULL < everything via ORDER BY; comparison ops return NULL."""
        # ORDER BY semantics: NULL sorts first.
        py_cmp = compare_values(Value.null(), Value.integer(0))
        assert py_cmp == -1  # NULL < 0
        py_cmp = compare_values(Value.integer(0), Value.null())
        assert py_cmp == 1   # 0 > NULL


# --- REAL that is integral (1.0 vs 1) -------------------------------------
class TestRealIntegerEquality:
    def test_integer_one_equals_real_one(self) -> None:
        """1 (INTEGER) and 1.0 (REAL) are equal in comparison (cross-numeric)."""
        assert compare_values(Value.integer(1), Value.real(1.0)) == 0

    def test_integer_one_not_equal_real_one_in_value(self) -> None:
        """But Value equality is structural: integer(1) != real(1.0)."""
        assert Value.integer(1) != Value.real(1.0)