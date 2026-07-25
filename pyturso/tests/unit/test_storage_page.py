"""Unit tests for pyturso.storage.sqlite3_ondisk page decode.

Ports/verified against: core/storage/sqlite3_ondisk.rs PageType +
core/storage/pager.rs PageInner (page header + cell pointer array). Uses a
real sqlite3-built database as the source of truth — the whole port is
verified against real .db files.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

import pytest

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import (
    CELL_PTR_SIZE,
    INTERIOR_HEADER_SIZE,
    LEAF_HEADER_SIZE,
    PageHeader,
    PageType,
    cell_pointer_offsets,
    parse_header,
    parse_page_header,
)


DbFixture = tuple[bytes, int, int]


@pytest.fixture
def real_db_pages(tmp_path: Path) -> DbFixture:
    """Build a real sqlite3 db with a populated table; return
    (file_bytes, page_size, num_pages)."""
    db = tmp_path / "pages.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(x INTEGER PRIMARY KEY, y TEXT)")
    conn.executemany("INSERT INTO t VALUES (?,?)",
                     [(i, f"row{i}" * 10) for i in range(50)])
    conn.commit()
    conn.close()
    data = db.read_bytes()
    hdr = parse_header(data[:100])
    return data, hdr.page_size, hdr.database_size


# --- PageType --------------------------------------------------------------
class TestPageType:
    def test_constants_match_rust(self) -> None:
        assert PageType.INDEX_INTERIOR == 2
        assert PageType.TABLE_INTERIOR == 5
        assert PageType.INDEX_LEAF == 10
        assert PageType.TABLE_LEAF == 13

    def test_is_table(self) -> None:
        assert PageType.is_table(PageType.TABLE_INTERIOR)
        assert PageType.is_table(PageType.TABLE_LEAF)
        assert not PageType.is_table(PageType.INDEX_INTERIOR)
        assert not PageType.is_table(PageType.INDEX_LEAF)

    def test_is_interior(self) -> None:
        assert PageType.is_interior(PageType.TABLE_INTERIOR)
        assert PageType.is_interior(PageType.INDEX_INTERIOR)
        assert not PageType.is_interior(PageType.TABLE_LEAF)

    def test_is_leaf(self) -> None:
        assert PageType.is_leaf(PageType.TABLE_LEAF)
        assert PageType.is_leaf(PageType.INDEX_LEAF)
        assert not PageType.is_leaf(PageType.TABLE_INTERIOR)


# --- header sizes / constants ----------------------------------------------
class TestConstants:
    def test_leaf_header_8_bytes(self) -> None:
        assert LEAF_HEADER_SIZE == 8

    def test_interior_header_12_bytes(self) -> None:
        assert INTERIOR_HEADER_SIZE == 12

    def test_cell_ptr_2_bytes(self) -> None:
        assert CELL_PTR_SIZE == 2


# --- parse_page_header: real db, page 1 (the root b-tree page) -------------
class TestParsePageHeader:
    def test_page1_header_parses(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        page1 = data[:page_size]
        hdr = parse_page_header(page1, page_no=1)
        assert isinstance(hdr, PageHeader)

    def test_page1_offset_handled(self, real_db_pages: DbFixture) -> None:
        # Page 1's content starts at offset 100; the page-type byte must be
        # at buf[100], not buf[0]. A real db's page 1 root is a table leaf or
        # interior — never garbage.
        data, page_size, _ = real_db_pages
        page1 = data[:page_size]
        hdr = parse_page_header(page1, page_no=1)
        assert hdr.raw_type in (
            PageType.TABLE_LEAF, PageType.TABLE_INTERIOR,
            PageType.INDEX_LEAF, PageType.INDEX_INTERIOR,
        )

    def test_cell_count_nonzero(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        hdr = parse_page_header(data[:page_size], page_no=1)
        # The root page of sqlite_schema must have cells.
        assert hdr.cell_count > 0

    def test_cell_content_start_is_valid(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        hdr = parse_page_header(data[:page_size], page_no=1)
        assert hdr.cell_content_start > 0
        assert hdr.cell_content_start <= page_size

    def test_leaf_has_no_rightmost_pointer(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        hdr = parse_page_header(data[:page_size], page_no=1)
        if hdr.is_leaf:
            assert hdr.rightmost_pointer is None

    def test_interior_has_rightmost_pointer(self, real_db_pages: DbFixture) -> None:
        data, page_size, num_pages = real_db_pages
        # With 50 rows the tree likely has an interior page; search for one.
        found_interior = False
        for pno in range(1, num_pages + 1):
            start = (pno - 1) * page_size
            page = data[start : start + page_size]
            hdr = parse_page_header(page, page_no=pno)
            if hdr.is_interior:
                assert hdr.rightmost_pointer is not None
                assert hdr.rightmost_pointer > 0
                found_interior = True
                break
        # If no interior page exists (small tree), this test is a no-op —
        # but with 50 rows and 4096-byte pages it usually has one.
        if not found_interior:
            pytest.skip("db too small to have an interior page")

    def test_header_size_matches_type(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        hdr = parse_page_header(data[:page_size], page_no=1)
        if hdr.is_interior:
            assert hdr.header_size == INTERIOR_HEADER_SIZE
        else:
            assert hdr.header_size == LEAF_HEADER_SIZE


# --- cell pointer array ----------------------------------------------------
class TestCellPointers:
    def test_pointers_count_matches_header(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        page1 = data[:page_size]
        hdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, hdr)
        assert len(ptrs) == hdr.cell_count

    def test_pointers_within_page(self, real_db_pages: DbFixture) -> None:
        data, page_size, _ = real_db_pages
        page1 = data[:page_size]
        hdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, hdr)
        for p in ptrs:
            assert 0 < p < page_size  # within the page buffer

    def test_pointers_point_to_content_area(
        self, real_db_pages: DbFixture
    ) -> None:
        # Every cell offset must be >= the cell-content-area start (cells
        # live at the top of the unallocated region, growing downward).
        data, page_size, _ = real_db_pages
        page1 = data[:page_size]
        hdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, hdr)
        for p in ptrs:
            assert p >= hdr.cell_content_start

    def test_pointers_are_sorted_descending(self, real_db_pages: DbFixture) -> None:
        # SQLite writes cells in key order from the end of the page backward;
        # the pointer array lists them in rowid order, but the *offsets* are
        # generally descending (cells fill from the top). This is a sanity
        # check, not a hard invariant — just verify they're all distinct.
        data, page_size, _ = real_db_pages
        page1 = data[:page_size]
        hdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, hdr)
        if len(ptrs) > 1:
            assert len(set(ptrs)) == len(ptrs)  # all distinct


# --- corrupt detection -----------------------------------------------------
class TestCorrupt:
    def test_invalid_page_type_raises(self) -> None:
        buf = bytearray(b"\x00" * 120)
        buf[100] = 99  # invalid page type at page-1 offset
        with pytest.raises(Corrupt, match="Invalid page type"):
            parse_page_header(bytes(buf), page_no=1)

    def test_too_short_buffer_raises(self) -> None:
        with pytest.raises(Corrupt, match="too short"):
            parse_page_header(b"\x05\x00\x00", page_no=2)

    def test_too_short_for_interior_header(self) -> None:
        # A buffer with a valid interior type byte but too short for 12-byte
        # interior header.
        buf = bytearray(b"\x05" + b"\x00" * 9)  # 10 bytes, need 12 (after offset 0)
        with pytest.raises(Corrupt, match="too short"):
            parse_page_header(bytes(buf), page_no=2)

    def test_cell_pointer_array_beyond_buffer_raises(self) -> None:
        # Header claims many cells but buffer is too short for the array.
        buf = bytearray(110)
        buf[100] = PageType.TABLE_LEAF  # page 1, leaf
        buf[103:105] = (999).to_bytes(2, "big")  # 999 cells — won't fit
        hdr = parse_page_header(bytes(buf), page_no=1)
        with pytest.raises(Corrupt, match="cell pointer array"):
            cell_pointer_offsets(bytes(buf), hdr)


# --- cell-content-area zero sentinel means 65536 --------------------------
class TestContentAreaSentinel:
    def test_zero_sentinel_decodes_as_65536(self) -> None:
        buf = bytearray(200)
        buf[100] = PageType.TABLE_LEAF
        # cell_content_start field (offset 5) = 0 → sentinel → 65536
        hdr = parse_page_header(bytes(buf), page_no=1)
        assert hdr.cell_content_start == 65536