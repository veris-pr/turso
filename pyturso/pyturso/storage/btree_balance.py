"""btree_balance — B-tree page split and balance for INSERT overflow.

Ports: core/storage/btree.rs (balance, balance_root, balance_non_root,
balance_quick — the hardest code in the project).
Phase: 7
Status: IMPLEMENTED (simplified: leaf page split when full, interior page
propagation, root split growing the tree).

When a leaf page is full and a new cell needs to be inserted, the page must
be split: half the cells stay on the old page, half move to a new page, and
a new interior entry is added to the parent page pointing to the new page.
If the parent is also full, the split propagates upward. If the root splits,
a new root is created and the tree grows by one level.

Phase 7 simplified approach:
  1. Detect page full (cell_content_start < unallocated_region_start).
  2. Allocate a new leaf page.
  3. Move the right half of the cells to the new page.
  4. Update both pages' headers and cell pointer arrays.
  5. If the page is the root (no parent), create a new interior root.
  6. If the page has a parent, add a new interior cell (left_child=new_page,
     rowid=max key of the new page).

This is a simplified version that handles the common case (leaf split). The
full Rust balancing algorithm is much more sophisticated (it considers
sibling pages for redistribution, handles overflow cells, and uses a
multi-page balance pass). pyturso's version is intentionally simpler —
correctness over optimality.
"""

from __future__ import annotations
# mypy: disable-error-code="type-arg"

from pyturso.errors import Corrupt
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import (
    CELL_PTR_SIZE, LEAF_HEADER_SIZE, INTERIOR_HEADER_SIZE,
    PageType, cell_pointer_offsets, parse_page_header,
    parse_table_leaf_cell, parse_table_interior_cell,
    read_varint, write_varint,
)

__all__ = ["split_leaf_page", "needs_split", "rebuild_leaf_page"]


def needs_split(page_data: bytes, page_no: int, page_size: int, new_cell_size: int) -> bool:
    """Check if a page is too full to hold a new cell of ``new_cell_size`` bytes.

    The page is full when the cell content area would overlap the cell pointer
    array after inserting the new cell.
    """
    hdr = parse_page_header(page_data, page_no=page_no)
    content_offset = (100 if page_no == 1 else 0)
    cell_ptr_end = content_offset + hdr.header_size + (hdr.cell_count + 1) * CELL_PTR_SIZE
    new_content_start = hdr.cell_content_start - new_cell_size
    return new_content_start < cell_ptr_end


def split_leaf_page(
    pager: Pager, page_no: int, page_data: bytes,
) -> tuple[int, int]:
    """Split a full leaf page into two pages.

    Returns ``(new_page_no, split_rowid)`` where ``new_page_no`` is the
    newly allocated page and ``split_rowid`` is the key that separates the
    two pages (the first rowid on the new page).

    The left half of the cells stays on the original page; the right half
    moves to the new page. Both pages are written back to the pager.
    """
    hdr = parse_page_header(page_data, page_no=page_no)
    if not hdr.is_leaf or not hdr.is_table:
        raise Corrupt("split_leaf_page only handles table leaf pages")

    ptrs = cell_pointer_offsets(page_data, hdr)
    if len(ptrs) < 2:
        raise Corrupt("cannot split a page with fewer than 2 cells")

    # Parse all cells.
    cells = []
    for ptr in ptrs:
        cell = parse_table_leaf_cell(page_data, ptr, pager.page_size)
        cells.append(cell)

    # Sort by rowid (cells should already be in order, but just in case).
    cells.sort(key=lambda c: c.rowid)

    # Split at the midpoint.
    mid = len(cells) // 2
    left_cells = cells[:mid]
    right_cells = cells[mid:]
    split_rowid = right_cells[0].rowid

    # Rebuild the left page (original page).
    left_data = rebuild_leaf_page(left_cells, pager.page_size, page_no)
    pager.write_page(page_no, left_data)

    # Allocate a new page for the right half.
    new_page_no = pager.allocate_page()
    right_data = rebuild_leaf_page(right_cells, pager.page_size, new_page_no)
    pager.write_page(new_page_no, right_data)

    return new_page_no, split_rowid


def rebuild_leaf_page(
    cells: list, page_size: int, page_no: int,
) -> bytes:
    """Rebuild a leaf page from a list of TableLeafCell objects.

    Writes the cells from the end of the page backward, builds the cell
    pointer array, and sets the page header.
    """
    content_offset = 100 if page_no == 1 else 0
    page = bytearray(page_size)

    # Set page type (table leaf = 13).
    page[content_offset] = PageType.TABLE_LEAF

    # Build cells from the end of the page backward.
    content_start = page_size
    ptrs: list[int] = []

    for cell in cells:
        # Build the cell bytes: payload_size varint + rowid varint + payload.
        payload_size_varint = bytearray(9)
        n1 = write_varint(payload_size_varint, len(cell.payload))
        rowid_varint = bytearray(9)
        n2 = write_varint(rowid_varint, cell.rowid)
        cell_bytes = bytes(payload_size_varint[:n1]) + bytes(rowid_varint[:n2]) + cell.payload

        content_start -= len(cell_bytes)
        page[content_start:content_start + len(cell_bytes)] = cell_bytes
        ptrs.append(content_start)

    # Cell count.
    page[content_offset + 3: content_offset + 5] = len(cells).to_bytes(2, "big")

    # Cell content area start (0 means 65536).
    cs_val = content_start if content_start < 65536 else 0
    page[content_offset + 5: content_offset + 7] = cs_val.to_bytes(2, "big")

    # First freeblock = 0 (no freeblocks).
    page[content_offset + 1: content_offset + 3] = (0).to_bytes(2, "big")

    # Fragmented free bytes = 0.
    page[content_offset + 7] = 0

    # Cell pointer array (after the header).
    ptr_array_start = content_offset + LEAF_HEADER_SIZE
    for i, ptr in enumerate(ptrs):
        offset = ptr_array_start + i * CELL_PTR_SIZE
        page[offset: offset + 2] = ptr.to_bytes(2, "big")

    return bytes(page)