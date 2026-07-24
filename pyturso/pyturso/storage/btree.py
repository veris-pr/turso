"""btree — BTreeCursor: rewind/next/seek; later insert/delete/split/balance.

Ports: core/storage/btree.rs (read traversal paths: move_to_leftmost,
table_leaf_next, move_to/seek for table trees).
Phase: 1 (read) / 7 (write)
Status: IMPLEMENTED (read path — table trees: full scan, ordered traversal,
seek by rowid). Index trees, insert/delete/balance are Phase 7.

The cursor traverses a table B-tree (rowid-keyed). It is a **generator**: page
reads compose via ``yield from pager.read_page(n)``, so a driver at the top
(``run_to_completion`` or ``StepDriver``) services every I/O. The cursor
maintains an explicit page stack (list of ``(page_no, cell_index)`` frames) —
the same shape as the Rust ``PageStack``, simplified for the read path. Phase
7's balance will invalidate cursors; the stack is the place to hang that rule.

Traversal model (table trees):
  - ``rewind()`` descends from the root to the leftmost leaf, positioning
    at cell 0. Interior pages are pushed onto the stack; leaf pages are the
    current page.
  - ``next()`` advances the current cell index. When the leaf is exhausted,
    it pops the stack to the parent interior page, advances to the next child
    (or the rightmost pointer), and descends to the leftmost leaf of that
    child. When the stack is empty and the leaf is exhausted, the cursor is
    done.
  - ``rowid()`` returns the current cell's rowid; ``payload()`` returns the
    current cell's payload bytes (local only — overflow assembly is a later
    refinement; the common small-row case works now).
  - ``seek(rowid)`` binary-searches within pages and descends through
    interior pages to find the leaf cell with the matching (or first-greater)
    rowid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

from pyturso.errors import Corrupt
from pyturso.io.protocol import Completion, ReadRequest
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import (
    PageType,
    TableInteriorCell,
    TableLeafCell,
    cell_pointer_offsets,
    parse_page_header,
    parse_table_interior_cell,
    parse_table_leaf_cell,
)

__all__ = ["BTreeCursor", "CursorRow"]


@dataclass
class CursorRow:
    """One row the cursor is positioned at: its rowid + payload (local)."""

    rowid: int
    payload: bytes


@dataclass
class _StackFrame:
    """One frame in the cursor's page stack (an interior page)."""

    page_no: int
    cell_index: int  # next cell to visit on this page


class BTreeCursor:
    """A read-only cursor over a table B-tree.

    Constructed with a :class:`Pager` and a root page number. The cursor's
    methods are **generators** that yield :class:`ReadRequest` objects (via
    ``yield from pager.read_page(...)``); the caller drives them with
    :func:`run_to_completion` or :class:`StepDriver`.

    State:
      - ``_root_page``: the root page number.
      - ``_stack``: the interior-page descent stack (each frame knows which
        child to visit next).
      - ``_current_page_no``: the leaf page the cursor is currently on.
      - ``_current_hdr``: the parsed header of the current page.
      - ``_current_ptrs``: the cell pointer array of the current page.
      - ``_cell_index``: the current cell index within the current page.
      - ``_done``: whether the cursor has passed the last row.
    """

    def __init__(self, pager: Pager, root_page: int) -> None:
        self._pager: Pager = pager
        self._root_page: int = root_page
        self._stack: list[_StackFrame] = []
        self._current_page_no: int = 0
        self._current_page: bytes = b""
        self._current_ptrs: list[int] = []
        self._cell_index: int = 0
        self._done: bool = True

    @property
    def done(self) -> bool:
        """True iff the cursor has passed the last row."""
        return self._done

    def rewind(self) -> Generator[ReadRequest, Completion, None]:
        """Position the cursor at the first (smallest rowid) row.

        Descends from the root to the leftmost leaf, pushing interior pages
        onto the stack. A generator that yields page reads.
        """
        self._stack.clear()
        self._done = False
        page_no = self._root_page
        while True:
            page = yield from self._pager.read_page(page_no)
            hdr = parse_page_header(page, page_no=page_no)
            if hdr.is_leaf:
                self._current_page_no = page_no
                self._current_page = page
                self._current_ptrs = cell_pointer_offsets(page, hdr)
                self._cell_index = 0
                if self._current_ptrs:
                    return  # positioned at first cell
                # Empty leaf: advance to find the next non-empty page.
                yield from self._advance()
                return
            # Interior page: push it and descend to the leftmost child.
            ptrs = cell_pointer_offsets(page, hdr)
            if not ptrs:
                # Interior page with no cells → only the rightmost pointer.
                assert hdr.rightmost_pointer is not None
                frame = _StackFrame(page_no=page_no, cell_index=0)
                self._stack.append(frame)
                page_no = hdr.rightmost_pointer
                continue
            # Leftmost child is the first interior cell's left_child_page.
            first_cell = parse_table_interior_cell(page, ptrs[0])
            frame = _StackFrame(page_no=page_no, cell_index=0)
            self._stack.append(frame)
            page_no = first_cell.left_child_page

    def next(self) -> Generator[ReadRequest, Completion, None]:
        """Advance the cursor to the next row.

        A generator that yields page reads when crossing page boundaries.
        Sets ``done`` when the cursor passes the last row.
        """
        if self._done:
            return
        self._cell_index += 1
        if self._cell_index < len(self._current_ptrs):
            return  # still within the current leaf
        # Leaf exhausted: advance to the next page.
        yield from self._advance()

    def _advance(self) -> Generator[ReadRequest, Completion, None]:
        """Move to the next leaf page when the current one is exhausted.

        Pops the stack to the parent interior page, advances to the next child
        (or the rightmost pointer), and descends to the leftmost leaf of that
        child. When the stack is empty, the cursor is done.
        """
        while self._stack:
            frame = self._stack[-1]
            page = yield from self._pager.read_page(frame.page_no)
            hdr = parse_page_header(page, page_no=frame.page_no)
            ptrs = cell_pointer_offsets(page, hdr)
            # frame.cell_index is the next cell to visit on this interior page.
            if frame.cell_index < len(ptrs):
                # Visit the next child (the cell at this index).
                cell = parse_table_interior_cell(page, ptrs[frame.cell_index])
                frame.cell_index += 1
                # Descend to the leftmost leaf of this child.
                yield from self._descend_to_leftmost(cell.left_child_page)
                return
            elif hdr.rightmost_pointer is not None:
                # All cells visited; go to the rightmost child.
                rightmost = hdr.rightmost_pointer
                self._stack.pop()
                yield from self._descend_to_leftmost(rightmost)
                return
            else:
                # No rightmost pointer and no more cells → pop and continue.
                self._stack.pop()
        # Stack empty → cursor done.
        self._done = True

    def _descend_to_leftmost(
        self, page_no: int
    ) -> Generator[ReadRequest, Completion, None]:
        """Descend from ``page_no`` to the leftmost leaf, pushing interior frames."""
        while True:
            page = yield from self._pager.read_page(page_no)
            hdr = parse_page_header(page, page_no=page_no)
            if hdr.is_leaf:
                self._current_page_no = page_no
                self._current_page = page
                self._current_ptrs = cell_pointer_offsets(page, hdr)
                self._cell_index = 0
                if self._current_ptrs:
                    return
                # Empty leaf → advance again (rare).
                yield from self._advance()
                return
            ptrs = cell_pointer_offsets(page, hdr)
            if not ptrs:
                assert hdr.rightmost_pointer is not None
                self._stack.append(_StackFrame(page_no=page_no, cell_index=0))
                page_no = hdr.rightmost_pointer
                continue
            first_cell = parse_table_interior_cell(page, ptrs[0])
            self._stack.append(_StackFrame(page_no=page_no, cell_index=0))
            page_no = first_cell.left_child_page

    def row(self) -> CursorRow:
        """Return the row at the current cursor position.

        Raises ``Corrupt`` if the cursor is done or not positioned. Returns
        the rowid + local payload (overflow assembly is a later refinement).
        """
        if self._done or self._cell_index >= len(self._current_ptrs):
            raise Corrupt("cursor not positioned at a valid row")
        cell = parse_table_leaf_cell(
            self._current_page,
            self._current_ptrs[self._cell_index],
            self._pager.page_size,
        )
        return CursorRow(rowid=cell.rowid, payload=cell.payload)

    def seek(
        self, target_rowid: int
    ) -> Generator[ReadRequest, Completion, bool]:
        """Seek to the row with ``target_rowid`` (or the first greater).

        Binary-searches within pages and descends through interior pages.
        Returns ``True`` if an exact match was found, ``False`` if positioned
        at the first rowid > ``target_rowid`` (or done if none exists).
        A generator that yields page reads.
        """
        self._stack.clear()
        self._done = False
        page_no = self._root_page
        while True:
            page = yield from self._pager.read_page(page_no)
            hdr = parse_page_header(page, page_no=page_no)
            ptrs = cell_pointer_offsets(page, hdr)
            if hdr.is_leaf:
                # Binary search within the leaf for target_rowid.
                self._current_page_no = page_no
                self._current_page = page
                self._current_ptrs = ptrs
                found, idx = self._binary_search_leaf(page, ptrs, target_rowid)
                self._cell_index = idx
                if not found and idx >= len(ptrs):
                    # Past the last cell → advance to the next page (or done).
                    yield from self._advance()
                return found
            # Interior page: binary search for the child to descend.
            child_page, cell_idx = self._binary_search_interior(
                page, ptrs, target_rowid
            )
            self._stack.append(_StackFrame(page_no=page_no, cell_index=cell_idx))
            page_no = child_page

    def _binary_search_leaf(
        self, page: bytes, ptrs: list[int], target: int
    ) -> tuple[bool, int]:
        """Binary search a leaf page for ``target`` rowid. Returns (found, idx)."""
        lo, hi = 0, len(ptrs) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            cell = parse_table_leaf_cell(page, ptrs[mid], self._pager.page_size)
            if cell.rowid == target:
                return True, mid
            elif cell.rowid < target:
                lo = mid + 1
            else:
                hi = mid - 1
        # lo is the insertion point: the first rowid >= target.
        return False, lo

    def _binary_search_interior(
        self, page: bytes, ptrs: list[int], target: int
    ) -> tuple[int, int]:
        """Binary search an interior page; returns (child_page, next_cell_idx).

        The child to descend is the left_child of the first cell whose rowid
        >= target. If all cells have rowid < target, descend the rightmost
        pointer. ``next_cell_idx`` is the index the parent stack frame should
        visit next (for subsequent traversal after this descent).
        """
        lo, hi = 0, len(ptrs) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            cell = parse_table_interior_cell(page, ptrs[mid])
            if cell.rowid == target:
                # Exact match: descend left_child, next visit is mid+1.
                return cell.left_child_page, mid + 1
            elif cell.rowid < target:
                lo = mid + 1
            else:
                hi = mid - 1
        # lo is the first cell with rowid >= target.
        if lo < len(ptrs):
            cell = parse_table_interior_cell(page, ptrs[lo])
            return cell.left_child_page, lo + 1
        # All cells < target → rightmost pointer.
        hdr = parse_page_header(page, page_no=0)
        assert hdr.rightmost_pointer is not None
        return hdr.rightmost_pointer, len(ptrs)