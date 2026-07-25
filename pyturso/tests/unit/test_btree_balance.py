"""Unit tests for B-tree balancing (page split) and remaining items."""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"

import sqlite3
import struct
from pathlib import Path

import pytest

from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import (
    cell_pointer_offsets, parse_page_header, parse_table_leaf_cell,
    PageType, LEAF_HEADER_SIZE, CELL_PTR_SIZE, write_varint,
)
from pyturso.storage.btree_balance import (
    needs_split, split_leaf_page, rebuild_leaf_page,
)
from pyturso.types.value import Value
from pyturso.types.record import build_record


# --- page split ---
class TestPageSplit:
    def _make_pager(self, page_size: int = 512) -> Pager:
        """Create a small-page pager for testing splits."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\x00" * (page_size * 10)))
        pager = Pager(io, "db", page_size=page_size)
        pager._file = f
        pager._page_size = page_size
        pager._header = None
        return pager

    def _make_leaf_cell(self, rowid: int, payload: bytes) -> bytes:
        """Build a table leaf cell."""
        ps_v = bytearray(9)
        n1 = write_varint(ps_v, len(payload))
        ri_v = bytearray(9)
        n2 = write_varint(ri_v, rowid)
        return bytes(ps_v[:n1]) + bytes(ri_v[:n2]) + payload

    def _fill_page(self, page_size: int, page_no: int, n_cells: int) -> bytes:
        """Fill a leaf page with n_cells cells of ~20 bytes each."""
        page = bytearray(page_size)
        content_offset = 100 if page_no == 1 else 0
        page[content_offset] = PageType.TABLE_LEAF

        content_start = page_size
        ptrs = []
        for i in range(n_cells):
            payload = struct.pack(">I", i) * 4  # 16 bytes
            cell = self._make_leaf_cell(i + 1, payload)
            content_start -= len(cell)
            page[content_start:content_start + len(cell)] = cell
            ptrs.append(content_start)

        page[content_offset + 3: content_offset + 5] = n_cells.to_bytes(2, "big")
        cs_val = content_start if content_start < 65536 else 0
        page[content_offset + 5: content_offset + 7] = cs_val.to_bytes(2, "big")
        page[content_offset + 1: content_offset + 3] = (0).to_bytes(2, "big")

        ptr_array_start = content_offset + LEAF_HEADER_SIZE
        for i, ptr in enumerate(ptrs):
            offset = ptr_array_start + i * CELL_PTR_SIZE
            page[offset: offset + 2] = ptr.to_bytes(2, "big")

        return bytes(page)

    def test_needs_split_true(self) -> None:
        page_size = 256
        page_data = self._fill_page(page_size, page_no=2, n_cells=12)
        assert needs_split(page_data, 2, page_size, 25)  # no room for 25 more bytes

    def test_needs_split_false(self) -> None:
        page_size = 4096
        page_data = self._fill_page(page_size, page_no=2, n_cells=3)
        assert not needs_split(page_data, 2, page_size, 25)  # plenty of room

    def test_split_leaf_page(self) -> None:
        """Split a full leaf page: left half stays, right half moves to new page."""
        page_size = 512
        pager = self._make_pager(page_size)
        n_cells = 15
        page_data = self._fill_page(page_size, page_no=2, n_cells=n_cells)
        pager.write_page(2, page_data)

        # Verify the page has all 15 cells.
        hdr = parse_page_header(page_data, page_no=2)
        assert hdr.cell_count == n_cells

        # Split the page.
        new_page_no, split_rowid = split_leaf_page(pager, 2, page_data)

        # Check the left page (original).
        left_data = pager.cache.get(2)
        assert left_data is not None
        left_hdr = parse_page_header(left_data, page_no=2)
        assert left_hdr.cell_count == n_cells // 2  # ~7 cells

        # Check the right page (new).
        right_data = pager.cache.get(new_page_no)
        assert right_data is not None
        right_hdr = parse_page_header(right_data, page_no=new_page_no)
        assert right_hdr.cell_count == n_cells - n_cells // 2  # ~8 cells

        # The split_rowid should be the first rowid on the right page.
        right_ptrs = cell_pointer_offsets(right_data, right_hdr)
        first_right_cell = parse_table_leaf_cell(right_data, right_ptrs[0], page_size)
        assert first_right_cell.rowid == split_rowid

        # All rowids should be present across both pages.
        left_ptrs = cell_pointer_offsets(left_data, left_hdr)
        all_rowids = set()
        for ptr in left_ptrs:
            cell = parse_table_leaf_cell(left_data, ptr, page_size)
            all_rowids.add(cell.rowid)
        for ptr in right_ptrs:
            cell = parse_table_leaf_cell(right_data, ptr, page_size)
            all_rowids.add(cell.rowid)
        assert all_rowids == set(range(1, n_cells + 1))

    def test_rebuild_leaf_page(self) -> None:
        """Rebuild a leaf page from cells."""
        page_size = 512
        # Create some fake cells.
        class FakeCell:
            def __init__(self, rowid: int, payload: bytes):
                self.rowid = rowid
                self.payload = payload

        cells = [FakeCell(i + 1, struct.pack(">I", i) * 4) for i in range(5)]
        page_data = rebuild_leaf_page(cells, page_size, page_no=2)

        hdr = parse_page_header(page_data, page_no=2)
        assert hdr.cell_count == 5
        assert hdr.is_leaf
        assert hdr.is_table

        ptrs = cell_pointer_offsets(page_data, hdr)
        assert len(ptrs) == 5

        # Verify the cells are in order.
        for i, ptr in enumerate(ptrs):
            cell = parse_table_leaf_cell(page_data, ptr, page_size)
            assert cell.rowid == i + 1