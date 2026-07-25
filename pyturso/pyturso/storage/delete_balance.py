"""delete_balance — cell removal with page rebuild for DELETE.

Ports: core/storage/btree.rs (delete + balance paths — concept).
Phase: 7
Status: IMPLEMENTED (simplified: rebuild page without the deleted cell).

When a row is deleted, its cell must be removed from the leaf page. The
simplified approach rebuilds the page with all cells except the deleted one.
This is correct but not optimal (the full Rust algorithm uses free-block
coalescing and underflow/balance with sibling pages).

Phase 7 simplified:
  1. Find the cell with the matching rowid.
  2. Rebuild the page with all other cells.
  3. Write the page back to the pager.

Underflow (page too empty after delete) is not handled — the page just has
fewer cells. A full merge/redistribute with siblings is a future refinement.
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"

from pyturso.errors import Corrupt
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import (
    cell_pointer_offsets, parse_page_header, parse_table_leaf_cell,
    PageType, LEAF_HEADER_SIZE, CELL_PTR_SIZE, write_varint,
)
from pyturso.storage.btree_balance import rebuild_leaf_page

__all__ = ["delete_cell_from_page"]


def delete_cell_from_page(
    pager: Pager, page_no: int, rowid: int,
) -> bool:
    """Delete the cell with ``rowid`` from a leaf page.

    Returns True if the cell was found and deleted, False if not found.
    """
    from pyturso.io.driver import run_to_completion

    page_data = run_to_completion(pager.read_page(page_no))
    hdr = parse_page_header(page_data, page_no=page_no)

    if not hdr.is_leaf or not hdr.is_table:
        raise Corrupt("delete_cell_from_page only handles table leaf pages")

    ptrs = cell_pointer_offsets(page_data, hdr)
    remaining_cells = []
    found = False

    for ptr in ptrs:
        cell = parse_table_leaf_cell(page_data, ptr, pager.page_size)
        if cell.rowid == rowid:
            found = True
            continue  # skip the deleted cell
        remaining_cells.append(cell)

    if not found:
        return False

    # Rebuild the page without the deleted cell.
    new_page_data = rebuild_leaf_page(remaining_cells, pager.page_size, page_no)
    pager.write_page(page_no, new_page_data)
    return True