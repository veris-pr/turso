"""pager — page authority: fetch via cache → file; dirty tracking, allocate, flush.

Ports: core/storage/pager.rs (read path + write path subset).
Phase: 1 (fetch) / 7 (write: dirty, allocate, flush) / 8 (WAL).
Status: IMPLEMENTED (read path + Phase 7 write subset: dirty pages,
allocate_page by growing the file, flush dirty pages to the file).

Phase 7 additions:
  - ``dirty_pages``: set of page numbers that have been modified.
  - ``write_page(page_no, data)``: update a page in cache + mark dirty.
  - ``allocate_page()``: grow the file by one page (simplified — no freelist).
  - ``flush()``: write all dirty pages to the file + update header.
  - ``num_pages``: the current page count (from header, updated on grow).
"""

from __future__ import annotations

from typing import Generator

from pyturso.errors import Corrupt
from pyturso.io.protocol import (
    Completion, File, IO, ReadRequest, WriteRequest,
)
from pyturso.io.driver import run_to_completion
from pyturso.storage.page_cache import PageCache
from pyturso.storage.sqlite3_ondisk import (
    DatabaseHeader, HEADER_SIZE, parse_header,
)

__all__ = ["Pager"]


class Pager:
    """The page authority: owns file, cache, header; reads + writes pages.

    Phase 7 write support: dirty tracking, allocate_page (grow), flush.
    """

    def __init__(self, io: IO, path: str, *, page_size: int | None = None) -> None:
        self._io: IO = io
        self._path: str = path
        self._file: File | None = None
        self._cache: PageCache = PageCache()
        self._header: DatabaseHeader | None = None
        self._page_size: int | None = page_size
        self._dirty_pages: set[int] = set()

    @property
    def page_size(self) -> int:
        if self._page_size is not None:
            return self._page_size
        if self._header is not None:
            return self._header.page_size
        raise Corrupt("page_size requested before open()")

    @property
    def header(self) -> DatabaseHeader:
        if self._header is None:
            raise Corrupt("pager not opened — call open() first")
        return self._header

    @property
    def cache(self) -> PageCache:
        return self._cache

    @property
    def dirty_pages(self) -> set[int]:
        """Set of page numbers that have been modified and need flushing."""
        return self._dirty_pages

    @property
    def num_pages(self) -> int:
        """Current page count (from header, updated on allocate)."""
        if self._header is not None:
            return self._header.database_size
        return 0

    def open(self) -> DatabaseHeader:
        """Open the file and parse the header from page 1."""
        self._file = self._io.open_file(self._path)
        page1_bytes = run_to_completion(self._read_raw(1, HEADER_SIZE))
        self._header = parse_header(page1_bytes)
        return self._header

    def read_page(self, page_no: int) -> Generator[ReadRequest, Completion, bytes]:
        """Fetch page ``page_no`` (1-based), cache → file. A generator."""
        cached = self._cache.get(page_no)
        if cached is not None:
            return cached
        data = yield from self._read_raw_gen(page_no, self.page_size)
        self._cache.put(page_no, data)
        return data

    def write_page(self, page_no: int, data: bytes) -> None:
        """Write page data into the cache and mark it dirty.

        The data is not written to disk until :meth:`flush` is called.
        The data must be exactly ``page_size`` bytes.
        """
        if len(data) != self.page_size:
            raise ValueError(
                f"page data must be {self.page_size} bytes, got {len(data)}"
            )
        self._cache.put(page_no, data)
        self._dirty_pages.add(page_no)

    def allocate_page(self) -> int:
        """Allocate a new page by growing the file. Returns the new page number.

        Simplified Phase 7: no freelist — always grows the file. The new page
        is initialized to all zeros and cached. The header's database_size is
        updated.
        """
        new_page_no = self.num_pages + 1
        empty = bytes(self.page_size)
        self._cache.put(new_page_no, empty)
        self._dirty_pages.add(new_page_no)
        if self._header is not None:
            self._header.database_size = new_page_no
        return new_page_no

    def flush(self) -> None:
        """Write all dirty pages to the file and clear the dirty set.

        Also writes the updated header (page 1) if the header fields changed
        (e.g. database_size from allocate_page).
        """
        if self._file is None:
            raise Corrupt("pager file not open")

        # Write the header back to page 1 if it's dirty or the size changed.
        if self._header is not None:
            self._write_header()

        # Write each dirty page.
        for page_no in sorted(self._dirty_pages):
            data = self._cache.get(page_no)
            if data is not None:
                offset = (page_no - 1) * self.page_size
                from pyturso.io.protocol import WriteRequest as WR
                # Use synchronous write (the io backend handles it).
                self._file.pwrite(WR(self._file, offset=offset, data=data))

        self._dirty_pages.clear()

    def _write_header(self) -> None:
        """Write the updated header back into page 1's cache + mark dirty."""
        if self._header is None:
            return
        # Get page 1 from cache (or read it).
        page1 = self._cache.get(1)
        if page1 is None:
            page1 = run_to_completion(self.read_page(1))

        # Update the header fields in page 1.
        buf = bytearray(page1)
        h = self._header
        # database_size (offset 28, 4 bytes BE).
        buf[28:32] = h.database_size.to_bytes(4, "big")
        # schema_cookie (offset 40, 4 bytes BE) — updated when schema changes.
        buf[40:44] = h.schema_cookie.to_bytes(4, "big")

        self._cache.put(1, bytes(buf))
        self._dirty_pages.add(1)

    def _read_raw(self, page_no: int, n: int) -> Generator[ReadRequest, Completion, bytes]:
        return (yield from self._read_raw_gen(page_no, n))

    def _read_raw_gen(
        self, page_no: int, n: int
    ) -> Generator[ReadRequest, Completion, bytes]:
        if self._file is None:
            raise Corrupt("pager file not open")
        offset = (page_no - 1) * self.page_size if page_no > 1 else 0
        if page_no == 1:
            offset = 0
        completion = yield ReadRequest(self._file, offset=offset, n=n)
        return completion.unwrap_read()