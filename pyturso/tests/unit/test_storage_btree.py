"""Unit tests for pyturso.storage.btree BTreeCursor (table trees, read path).

Ports/verified against: core/storage/btree.rs traversal paths. Drives a real
sqlite3-built db through the pager + cursor, verifying ordered traversal
matches sqlite3's SELECT (the Phase 1 read-path gate in miniature).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.driver import run_to_completion
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.btree import BTreeCursor, CursorRow
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import parse_record


@pytest.fixture
def cursor_and_expected(
    tmp_path: Path,
) -> tuple[BTreeCursor, list[tuple[int, str]]]:
    """Build a real db, load into MemoryIO, return (cursor, expected_rows).

    The cursor is positioned at the root of the 't' table. expected_rows is
    what sqlite3 returns for SELECT id, y FROM t ORDER BY id — the ground
    truth the cursor must match.
    """
    db_path = tmp_path / "cursor.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(x INTEGER PRIMARY KEY, y TEXT)")
    rows = [(i, f"row_{i:04d}_" + "x" * 20) for i in range(1, 51)]
    conn.executemany("INSERT INTO t VALUES (?,?)", rows)
    conn.commit()
    conn.close()

    # Load into MemoryIO.
    raw = db_path.read_bytes()
    io = MemoryIO()
    f = io.open_file("test.db")
    f.pwrite(WriteRequest(f, 0, raw))

    # Open the pager, find the 't' table's root page from sqlite_schema.
    pager = Pager(io, "test.db")
    pager.open()

    # Page 1 is the sqlite_schema root (table leaf for a small db).
    page1 = run_to_completion(pager.read_page(1))
    from pyturso.storage.sqlite3_ondisk import (
        cell_pointer_offsets,
        parse_page_header,
        parse_table_leaf_cell,
    )
    hdr = parse_page_header(page1, page_no=1)
    ptrs = cell_pointer_offsets(page1, hdr)
    t_root = 0
    for ptr in ptrs:
        cell = parse_table_leaf_cell(page1, ptr, pager.page_size)
        rec = parse_record(cell.payload)
        # sqlite_schema: type, name, tbl_name, rootpage, sql
        if rec.values[0] == "table" and rec.values[1] == "t":
            t_root = rec.values[3]  # type: ignore[assignment]
            break
    assert t_root > 0, "could not find 't' table root page in sqlite_schema"

    cursor = BTreeCursor(pager, t_root)
    return cursor, [(r[0], r[1]) for r in rows]


# --- rewind + ordered traversal (the core read-path test) ------------------
class TestRewindAndNext:
    def test_rewind_positions_at_first_row(
        self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]
    ) -> None:
        cursor, expected = cursor_and_expected
        run_to_completion(cursor.rewind())
        assert not cursor.done
        row = cursor.row()
        assert row.rowid == expected[0][0]

    def test_full_traversal_matches_sqlite3(
        self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]
    ) -> None:
        """The Phase 1 gate in miniature: cursor traversal == sqlite3 SELECT."""
        cursor, expected = cursor_and_expected
        run_to_completion(cursor.rewind())
        actual: list[tuple[int, str]] = []
        while not cursor.done:
            row = cursor.row()
            rec = parse_record(row.payload)
            # Column 0 is INTEGER PRIMARY KEY (== rowid); column 1 is TEXT.
            actual.append((row.rowid, rec.values[1]))  # type: ignore[arg-type]
            run_to_completion(cursor.next())
        assert actual == expected

    def test_rowids_are_ascending(self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]) -> None:
        cursor, _ = cursor_and_expected
        run_to_completion(cursor.rewind())
        rowids: list[int] = []
        while not cursor.done:
            rowids.append(cursor.row().rowid)
            run_to_completion(cursor.next())
        assert rowids == sorted(rowids)

    def test_cursor_done_at_end(self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]) -> None:
        cursor, _ = cursor_and_expected
        run_to_completion(cursor.rewind())
        while not cursor.done:
            run_to_completion(cursor.next())
        assert cursor.done
        # Calling next() after done is a no-op.
        run_to_completion(cursor.next())
        assert cursor.done


# --- seek ------------------------------------------------------------------
class TestSeek:
    def test_seek_exact_match(self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]) -> None:
        cursor, expected = cursor_and_expected
        target = 25
        found = run_to_completion(cursor.seek(target))
        assert found is True
        assert not cursor.done
        row = cursor.row()
        assert row.rowid == target
        assert row.rowid == expected[24][0]

    def test_seek_first_row(self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]) -> None:
        cursor, _ = cursor_and_expected
        found = run_to_completion(cursor.seek(1))
        assert found is True
        assert cursor.row().rowid == 1

    def test_seek_last_row(self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]) -> None:
        cursor, _ = cursor_and_expected
        found = run_to_completion(cursor.seek(50))
        assert found is True
        assert cursor.row().rowid == 50

    def test_seek_between_rows_positions_at_next(
        self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]
    ) -> None:
        cursor, _ = cursor_and_expected
        # No row 25.5; seek should position at 26.
        found = run_to_completion(cursor.seek(26))
        assert found is True
        assert cursor.row().rowid == 26

    def test_seek_past_end_sets_done(self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]) -> None:
        cursor, _ = cursor_and_expected
        found = run_to_completion(cursor.seek(999))
        assert found is False
        assert cursor.done

    def test_seek_before_first_positions_at_first(
        self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]
    ) -> None:
        cursor, _ = cursor_and_expected
        found = run_to_completion(cursor.seek(-1))
        assert found is False
        assert not cursor.done
        assert cursor.row().rowid == 1

    def test_seek_then_traverse_remaining(
        self, cursor_and_expected: tuple[BTreeCursor, list[tuple[int, str]]]
    ) -> None:
        """After seeking, traversal continues from the seek position."""
        cursor, expected = cursor_and_expected
        run_to_completion(cursor.seek(30))
        actual: list[int] = []
        while not cursor.done:
            actual.append(cursor.row().rowid)
            run_to_completion(cursor.next())
        # Should be rows 30..50.
        assert actual == list(range(30, 51))


# --- CursorRow dataclass ---------------------------------------------------
class TestCursorRow:
    def test_fields(self) -> None:
        r = CursorRow(rowid=42, payload=b"abc")
        assert r.rowid == 42 and r.payload == b"abc"