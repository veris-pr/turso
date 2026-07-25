"""Unit tests for pyturso.storage.sqlite3_ondisk index cells.

Ports/verified against: core/storage/sqlite3_ondisk.rs IndexLeafCell /
IndexInteriorCell + read_btree_cell IndexLeaf/IndexInterior branches.
Uses a real sqlite3-built db with an index to verify round-trip.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import (
    IndexInteriorCell,
    IndexLeafCell,
    PageType,
    cell_pointer_offsets,
    parse_header,
    parse_index_interior_cell,
    parse_index_leaf_cell,
    parse_page_header,
    parse_record,
)


@pytest.fixture
def db_with_index(tmp_path: Path) -> tuple[bytes, int, int]:
    """Build a db with an index; return (file_bytes, page_size, num_pages)."""
    db = tmp_path / "idx.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(x INTEGER PRIMARY KEY, y TEXT)")
    conn.executemany("INSERT INTO t VALUES (?,?)",
                     [(i, f"val_{i:03d}") for i in range(1, 31)])
    conn.execute("CREATE INDEX idx_y ON t(y)")
    conn.commit()
    conn.close()
    data = db.read_bytes()
    hdr = parse_header(data[:100])
    return data, hdr.page_size, hdr.database_size


# --- IndexLeafCell decode --------------------------------------------------
class TestIndexLeafCell:
    def test_decodes_payload(self) -> None:
        # Hand-made: payload_size=3, payload=b"abc"
        cell = bytes([3]) + b"abc"
        result = parse_index_leaf_cell(cell, 0, 4096)
        assert isinstance(result, IndexLeafCell)
        assert result.payload == b"abc"
        assert result.payload_size == 3
        assert result.first_overflow_page is None

    def test_truncated_raises(self) -> None:
        with pytest.raises(Corrupt):
            parse_index_leaf_cell(b"\x80", 0, 4096)  # truncated varint


# --- IndexInteriorCell decode ----------------------------------------------
class TestIndexInteriorCell:
    def test_decodes_child_and_payload(self) -> None:
        # left_child=page 5, payload_size=2, payload=b"xy"
        cell = (5).to_bytes(4, "big") + bytes([2]) + b"xy"
        result = parse_index_interior_cell(cell, 0, 4096)
        assert isinstance(result, IndexInteriorCell)
        assert result.left_child_page == 5
        assert result.payload == b"xy"
        assert result.payload_size == 2

    def test_truncated_raises(self) -> None:
        with pytest.raises(Corrupt, match="extends beyond"):
            parse_index_interior_cell(b"\x00\x01", 0, 4096)


# --- real db: find and verify an index page -------------------------------
class TestRealIndexPage:
    def test_finds_index_page_with_cells(
        self, db_with_index: tuple[bytes, int, int]
    ) -> None:
        data, ps, npages = db_with_index
        found = False
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if not PageType.is_leaf(hdr.raw_type) or hdr.is_table:
                continue
            # Index leaf page: decode cells.
            assert hdr.cell_count > 0
            ptrs = cell_pointer_offsets(page, hdr)
            for ptr in ptrs:
                cell = parse_index_leaf_cell(page, ptr, ps)
                assert len(cell.payload) > 0
                # The payload is a record key — decode it.
                rec = parse_record(cell.payload)
                assert len(rec.values) >= 1
            found = True
            break
        if not found:
            pytest.skip("no index leaf page in fixture")

    def test_index_page_type_is_index_leaf(
        self, db_with_index: tuple[bytes, int, int]
    ) -> None:
        data, ps, npages = db_with_index
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if hdr.raw_type == PageType.INDEX_LEAF:
                assert not hdr.is_table
                assert hdr.is_leaf
                return
        pytest.skip("no index leaf page")

    def test_index_keys_decode_as_records(
        self, db_with_index: tuple[bytes, int, int]
    ) -> None:
        """Index keys are records — decode and verify they have the indexed
        column value."""
        data, ps, npages = db_with_index
        for pno in range(1, npages + 1):
            start = (pno - 1) * ps
            page = data[start : start + ps]
            hdr = parse_page_header(page, page_no=pno)
            if hdr.raw_type != PageType.INDEX_LEAF:
                continue
            ptrs = cell_pointer_offsets(page, hdr)
            for ptr in ptrs[:3]:  # check first few
                cell = parse_index_leaf_cell(page, ptr, ps)
                rec = parse_record(cell.payload)
                # idx_y is on column y (TEXT); the index key record has the
                # indexed value + the rowid (for table lookup).
                assert len(rec.values) >= 1
                assert isinstance(rec.values[0], str)
                assert rec.values[0].startswith("val_")
            return
        pytest.skip("no index leaf page")