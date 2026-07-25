"""Unit tests for pyturso.storage.sqlite3_ondisk interior table pages.

Ports/verified against: core/storage/sqlite3_ondisk.rs TableInteriorCell +
read_btree_cell TableInterior branch. Uses a real sqlite3-built db with
enough rows to force an interior page (a 2-level B-tree).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import (
    INTERIOR_HEADER_SIZE,
    PageType,
    TableInteriorCell,
    cell_pointer_offsets,
    parse_header,
    parse_page_header,
    parse_table_interior_cell,
    parse_table_leaf_cell,
    parse_record,
)


@pytest.fixture
def real_db_interior(tmp_path: Path) -> tuple[bytes, int, int]:
    """Build a db with enough rows to produce an interior table page.

    With small text values and 50 rows in a 4096-byte page, the table B-tree
    typically has an interior root with 1-2 leaf children. We verify the
    interior page is found and its cells decode.
    """
    db = tmp_path / "interior.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(x INTEGER PRIMARY KEY, y TEXT)")
    conn.executemany(
        "INSERT INTO t VALUES (?,?)",
        [(i, f"row_{i:04d}_" + "x" * 50) for i in range(1, 101)],
    )
    conn.commit()
    conn.close()
    data = db.read_bytes()
    hdr = parse_header(data[:100])
    return data, hdr.page_size, hdr.database_size


# --- TableInteriorCell decode ----------------------------------------------
class TestParseInteriorCell:
    def test_decodes_left_child_and_rowid(self) -> None:
        # Build a hand-made interior cell: left_child=page 3, rowid=42.
        page_no = 3
        rowid = 42
        cell = page_no.to_bytes(4, "big") + bytes([rowid])
        result = parse_table_interior_cell(cell, 0)
        assert isinstance(result, TableInteriorCell)
        assert result.left_child_page == 3
        assert result.rowid == 42

    def test_large_rowid_uses_multibyte_varint(self) -> None:
        page_no = 7
        rowid = 300  # 2-byte varint
        cell = page_no.to_bytes(4, "big") + bytes([0x82, 0x2C])  # 300
        result = parse_table_interior_cell(cell, 0)
        assert result.left_child_page == 7
        assert result.rowid == 300

    def test_truncated_cell_raises_corrupt(self) -> None:
        with pytest.raises(Corrupt, match="extends beyond"):
            parse_table_interior_cell(b"\x00\x01", 0)

    def test_truncated_rowid_raises_corrupt(self) -> None:
        # left_child present but rowid varint has continuation and no end.
        cell = (3).to_bytes(4, "big") + b"\x80"  # continuation, no terminator
        with pytest.raises(Corrupt):
            parse_table_interior_cell(cell, 0)


# --- real db: find and verify an interior page -----------------------------
class TestRealInteriorPage:
    def test_finds_interior_page_with_cells(
        self, real_db_interior: tuple[bytes, int, int]
    ) -> None:
        data, ps, npages = real_db_interior
        found = False
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if hdr.is_interior and hdr.is_table:
                # Interior table page: has rightmost pointer + cell pointers.
                assert hdr.rightmost_pointer is not None
                assert hdr.rightmost_pointer > 0
                assert hdr.cell_count > 0
                # Decode all interior cells.
                ptrs = cell_pointer_offsets(page, hdr)
                for ptr in ptrs:
                    cell = parse_table_interior_cell(page, ptr)
                    assert cell.left_child_page > 0
                    assert cell.left_child_page <= npages  # valid page ref
                found = True
                break
        if not found:
            pytest.skip("db too small for an interior page")

    def test_interior_rightmost_pointer_is_valid_page(
        self, real_db_interior: tuple[bytes, int, int]
    ) -> None:
        data, ps, npages = real_db_interior
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if hdr.is_interior and hdr.is_table:
                assert 1 <= hdr.rightmost_pointer <= npages  # type: ignore[operator]
                return
        pytest.skip("no interior page")

    def test_interior_cells_have_ascending_rowids(
        self, real_db_interior: tuple[bytes, int, int]
    ) -> None:
        data, ps, npages = real_db_interior
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if hdr.is_interior and hdr.is_table:
                ptrs = cell_pointer_offsets(page, hdr)
                rowids = [parse_table_interior_cell(page, p).rowid for p in ptrs]
                assert rowids == sorted(rowids), (
                    f"interior cells must be in ascending rowid order: {rowids}"
                )
                return
        pytest.skip("no interior page")


# --- full descent: interior → leaf → record --------------------------------
class TestDescent:
    def test_descend_interior_to_leaf_records(
        self, real_db_interior: tuple[bytes, int, int]
    ) -> None:
        """Verify the full read path: find an interior page, follow a child
        pointer to a leaf, decode a record, and confirm the rowid matches."""
        data, ps, npages = real_db_interior
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if not (hdr.is_interior and hdr.is_table):
                continue
            # Take the first interior cell's left child page.
            ptrs = cell_pointer_offsets(page, hdr)
            if not ptrs:
                continue
            interior_cell = parse_table_interior_cell(page, ptrs[0])
            child_pno = interior_cell.left_child_page
            # Read the child page (it should be a table leaf).
            child_start = (child_pno - 1) * ps
            child_page = data[child_start : child_start + ps]
            child_hdr = parse_page_header(child_page, page_no=child_pno)
            assert child_hdr.is_table, "child of a table interior must be a table page"
            if child_hdr.is_leaf:
                # Decode leaf cells and verify rowids are <= the interior key.
                child_ptrs = cell_pointer_offsets(child_page, child_hdr)
                for cp in child_ptrs:
                    leaf_cell = parse_table_leaf_cell(child_page, cp, ps)
                    assert leaf_cell.rowid <= interior_cell.rowid, (
                        f"leaf rowid {leaf_cell.rowid} must be <= "
                        f"interior key {interior_cell.rowid}"
                    )
                    # The record should decode without error.
                    rec = parse_record(leaf_cell.payload)
                    assert len(rec.values) >= 1
                return
        pytest.skip("no suitable interior→leaf descent found")