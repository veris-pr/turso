"""pager — page authority: fetch via cache → file (WAL added Phase 8).

Ports: core/storage/pager.rs (read path only — fetch, cache, header).
Phase: 1 (fetch) / 7 (write: dirty, allocate, free, flush) / 8 (WAL).
Status: IMPLEMENTED (read path: open file, parse header, read_page generator).
The write path and WAL are later phases.

The pager is the layer between the B-tree and the io backends. It owns the
file handle, the page cache, and the parsed database header. ``read_page(n)``
is a **generator** (the io convention — see ``pyturso/io/HOWTO.md``): it yields
a :class:`ReadRequest` for pages not in the cache, and is resumed with a
:class:`Completion` carrying the page bytes. The caller drives it with
``run_to_completion`` (everyday) or ``StepDriver`` (tests).

Fetch order: **cache → file**. Phase 8 inserts WAL between them
(cache → WAL → file). No I/O happens when the page is already cached.
"""

from __future__ import annotations

from typing import Generator

from pyturso.errors import Corrupt
from pyturso.io.protocol import (
    Completion,
    File,
    IO,
    ReadRequest,
)
from pyturso.io.driver import run_to_completion
from pyturso.storage.page_cache import PageCache
from pyturso.storage.sqlite3_ondisk import DatabaseHeader, HEADER_SIZE, parse_header

__all__ = ["Pager"]


class Pager:
    """The page authority: owns file, cache, header; yields page reads.

    Constructed with an :class:`IO` backend and a path; :meth:`open` opens the
    file and parses the 100-byte header from page 1. :meth:`read_page` is the
    generator-based fetch (cache → file). Callers drive it with
    :func:`run_to_completion` or :class:`StepDriver`.
    """

    def __init__(self, io: IO, path: str, *, page_size: int | None = None) -> None:
        self._io: IO = io
        self._path: str = path
        self._file: File | None = None
        self._cache: PageCache = PageCache()
        self._header: DatabaseHeader | None = None
        self._page_size: int | None = page_size  # override for headerless open

    @property
    def page_size(self) -> int:
        """The page size in bytes (from the header, or the override)."""
        if self._page_size is not None:
            return self._page_size
        if self._header is not None:
            return self._header.page_size
        raise Corrupt("page_size requested before open() or header parse")

    @property
    def header(self) -> DatabaseHeader:
        """The parsed database header (raises if not yet opened)."""
        if self._header is None:
            raise Corrupt("pager not opened — call open() first")
        return self._header

    @property
    def cache(self) -> PageCache:
        """The page cache (for inspection / test assertions)."""
        return self._cache

    def open(self) -> DatabaseHeader:
        """Open the file and parse the header from page 1.

        Returns the parsed :class:`DatabaseHeader`. The file handle is kept
        open for the pager's lifetime.
        """
        self._file = self._io.open_file(self._path)
        # Read page 1 (at least the 100-byte header) to parse it.
        page1_bytes = run_to_completion(self._read_raw(1, HEADER_SIZE))
        self._header = parse_header(page1_bytes)
        # Cache the partial page-1 read (header only); the full page is read
        # on demand via read_page(1).
        return self._header

    def read_page(self, page_no: int) -> Generator[ReadRequest, Completion, bytes]:
        """Fetch page ``page_no`` (1-based), cache → file. A generator.

        Yields a :class:`ReadRequest` for the page if it is not cached; is
        resumed with a :class:`Completion` carrying the page bytes. Returns
        the page bytes (the full page, ``page_size`` long). On cache hit, no
        I/O is yielded (the generator returns immediately).

        Raises:
            Corrupt: the read returned fewer bytes than ``page_size`` (a short
                read that is not at EOF — ports the pager's integrity check).
        """
        cached = self._cache.get(page_no)
        if cached is not None:
            return cached
        data = yield from self._read_raw_gen(page_no, self.page_size)
        self._cache.put(page_no, data)
        return data

    def _read_raw(self, page_no: int, n: int) -> Generator[ReadRequest, Completion, bytes]:
        """Read ``n`` bytes at the page's file offset (generator, no cache)."""
        return (yield from self._read_raw_gen(page_no, n))

    def _read_raw_gen(
        self, page_no: int, n: int
    ) -> Generator[ReadRequest, Completion, bytes]:
        """Internal: yield a ReadRequest for page_no's bytes, unwrap it."""
        if self._file is None:
            raise Corrupt("pager file not open")
        offset = (page_no - 1) * self.page_size if page_no > 1 else 0
        # For page 1 with a header override, use offset 0 directly.
        if page_no == 1:
            offset = 0
        completion = yield ReadRequest(self._file, offset=offset, n=n)
        return completion.unwrap_read()