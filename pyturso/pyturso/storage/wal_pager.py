"""WAL pager integration — cache → WAL → file fetch order.

Ports: core/storage/pager.rs (WAL integration in read path).
Phase: 8
Status: IMPLEMENTED (pager checks WAL before main file).

When a WAL is active, the pager's read path checks the WAL for a page before
reading the main database file. The order is: cache → WAL → file. This makes
recently committed changes visible without a checkpoint.

This module provides a :class:`WALPager` that wraps a :class:`Pager` and a
:class:`WAL`, implementing the three-tier fetch.
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"

from typing import Generator

from pyturso.io.protocol import Completion, ReadRequest
from pyturso.storage.pager import Pager
from pyturso.storage.wal import WAL

__all__ = ["WALPager"]


class WALPager:
    """A pager wrapper that checks the WAL before the main file.

    Fetch order: cache → WAL → file. Writes go through the pager (which
    caches + marks dirty); the WAL is used for reading uncommitted-but-
    committed-to-WAL pages.

    This class wraps a :class:`Pager` and a :class:`WAL`, delegating to the
    pager for writes and cache, and to the WAL for reads of pages that have
    been written to the WAL but not yet checkpointed.
    """

    def __init__(self, pager: Pager, wal: WAL | None = None) -> None:
        self._pager = pager
        self._wal = wal

    @property
    def pager(self) -> Pager:
        return self._pager

    @property
    def wal(self) -> WAL | None:
        return self._wal

    @property
    def page_size(self) -> int:
        return self._pager.page_size

    @property
    def header(self):
        return self._pager.header

    @property
    def num_pages(self) -> int:
        return self._pager.num_pages

    @property
    def cache(self):
        return self._pager.cache

    @property
    def dirty_pages(self):
        return self._pager.dirty_pages

    def read_page(self, page_no: int) -> Generator[ReadRequest, Completion, bytes]:
        """Fetch page ``page_no``: cache → WAL → file. A generator."""
        # 1. Check cache.
        cached = self._pager.cache.get(page_no)
        if cached is not None:
            return cached

        # 2. Check WAL (if active).
        if self._wal is not None:
            wal_data = self._wal.get_page(page_no)
            if wal_data is not None:
                self._pager.cache.put(page_no, wal_data)
                return wal_data

        # 3. Read from main file.
        data = yield from self._pager.read_page(page_no)
        return data

    def write_page(self, page_no: int, data: bytes) -> None:
        """Write page data to the cache + mark dirty (same as pager)."""
        self._pager.write_page(page_no, data)

    def allocate_page(self) -> int:
        """Allocate a new page (grows the file)."""
        return self._pager.allocate_page()

    def flush(self) -> None:
        """Flush dirty pages to the main file."""
        self._pager.flush()

    def open(self):
        """Open the pager (and WAL if set)."""
        return self._pager.open()