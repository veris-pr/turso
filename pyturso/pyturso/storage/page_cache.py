"""page_cache — in-memory cache of decoded pages (dict, no eviction yet).

Ports: core/storage/page_cache.rs (concept; the Rust has an LRU, pyturso
starts with an unbounded dict and records the debt for Phase 7).
Phase: 1
Status: IMPLEMENTED (minimal: dict cache, no eviction). Eviction is a Phase 7
debt — recorded here so it is a decision, not an oversight.

A simple dict keyed by 1-based page number → raw page bytes. The pager checks
here before issuing an I/O read. No eviction policy yet (unbounded growth);
Phase 7 adds LRU when the write path needs cache pressure.
"""

from __future__ import annotations

__all__ = ["PageCache"]


class PageCache:
    """An unbounded page cache (dict of page_no → bytes).

    The pager checks :meth:`get` before reading from the file; :meth:`put`
    stores a freshly read page. No eviction — the cache grows with the
    database. This is fine for the Phase 1 read path (tests + dbdump on small
    fixtures); Phase 7 adds LRU when the write path needs cache pressure.
    """

    def __init__(self) -> None:
        self._pages: dict[int, bytes] = {}

    def get(self, page_no: int) -> bytes | None:
        """Return the cached page bytes for ``page_no``, or ``None`` (miss)."""
        return self._pages.get(page_no)

    def put(self, page_no: int, data: bytes) -> None:
        """Store ``data`` as the page bytes for ``page_no``."""
        self._pages[page_no] = data

    def __len__(self) -> int:
        return len(self._pages)

    def __contains__(self, page_no: int) -> bool:
        return page_no in self._pages