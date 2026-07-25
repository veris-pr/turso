"""Unit tests for DELETE balance, nested-loop joins, and final integration."""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="attr-defined"

import sqlite3
from pathlib import Path

import pytest

from pyturso.database import Database
from pyturso.types.value import Value
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.pager import Pager
from pyturso.storage.btree_balance import rebuild_leaf_page
from pyturso.storage.delete_balance import delete_cell_from_page
from pyturso.storage.sqlite3_ondisk import (
    cell_pointer_offsets, parse_page_header, parse_table_leaf_cell,
)
from pyturso.io.driver import run_to_completion


# --- DELETE balance ---
class TestDeleteBalance:
    def test_delete_cell(self, tmp_path: Path) -> None:
        """Delete a cell from a leaf page by rowid."""
        # Create a db with a table.
        db_path = tmp_path / "del.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO t VALUES (?,?)",
                         [(1, "alice"), (2, "bob"), (3, "carol")])
        conn.commit()
        conn.close()

        db = Database.open(str(db_path))
        pager = db.pager

        # Find the table's root page from schema.
        from pyturso.schema.load import load_schema
        schema = load_schema(pager)
        table = schema.get_table("t")
        assert table is not None

        # Delete rowid=2 (bob).
        deleted = delete_cell_from_page(pager, table.root_page, rowid=2)
        assert deleted is True
        pager.flush()

        # Verify: scan the page and check cells.
        page_data = run_to_completion(pager.read_page(table.root_page))
        hdr = parse_page_header(page_data, page_no=table.root_page)
        ptrs = cell_pointer_offsets(page_data, hdr)
        assert len(ptrs) == 2  # was 3, deleted 1
        rowids = set()
        for ptr in ptrs:
            cell = parse_table_leaf_cell(page_data, ptr, pager.page_size)
            rowids.add(cell.rowid)
        assert rowids == {1, 3}  # bob (rowid=2) is gone

    def test_delete_not_found(self, tmp_path: Path) -> None:
        """Delete a non-existent rowid returns False."""
        db_path = tmp_path / "del2.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'alice')")
        conn.commit()
        conn.close()

        db = Database.open(str(db_path))
        from pyturso.schema.load import load_schema
        schema = load_schema(db.pager)
        table = schema.get_table("t")
        assert table is not None

        deleted = delete_cell_from_page(db.pager, table.root_page, rowid=999)
        assert deleted is False


# --- nested-loop join ---
class TestNestedJoin:
    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        db_path = tmp_path / "join.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("CREATE TABLE dept(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE emp(id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER)")
        conn.executemany("INSERT INTO dept VALUES (?,?)", [(1, "eng"), (2, "sales")])
        conn.executemany("INSERT INTO emp VALUES (?,?,?)",
                         [(1, "alice", 1), (2, "bob", 1), (3, "carol", 2)])
        conn.commit()
        conn.close()
        return Database.open(str(db_path))

    def test_inner_join_comma(self, db: Database) -> None:
        """SELECT * FROM emp, dept WHERE emp.dept_id = dept.id"""
        conn = db.connect()
        rows = conn.execute("SELECT emp.name, dept.name FROM emp, dept WHERE emp.dept_id = dept.id ORDER BY emp.id")
        assert len(rows) == 3
        # alice→eng, bob→eng, carol→sales
        names = [(r[1].payload, r[4].payload) for r in rows]  # type: ignore[union-attr]
        assert ("alice", "eng") in names
        assert ("bob", "eng") in names
        assert ("carol", "sales") in names

    def test_cross_join(self, db: Database) -> None:
        """SELECT * FROM emp, dept (no WHERE = cross join = all combinations)"""
        conn = db.connect()
        rows = conn.execute("SELECT emp.name, dept.name FROM emp, dept")
        assert len(rows) == 6  # 3 emp × 2 dept = 6 combinations

    def test_left_join(self, db: Database) -> None:
        """LEFT JOIN: unmatched outer rows get NULLs."""
        # Add an emp with no matching dept.
        conn = db.connect()
        conn.execute("INSERT INTO emp VALUES (4, 'dave', 99)")  # dept_id=99 doesn't exist
        rows = conn.execute("SELECT emp.name, dept.name FROM emp LEFT JOIN dept ON emp.dept_id = dept.id ORDER BY emp.id")
        assert len(rows) == 4
        # dave should have NULL for dept.name.
        dave_row = [r for r in rows if r[1].payload == "dave"][0]  # type: ignore[union-attr]
        assert dave_row[4].is_null  # dept.name is column 4 (emp.id, emp.name, emp.dept_id, dept.id, dept.name)