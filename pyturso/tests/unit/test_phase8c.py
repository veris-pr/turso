"""Unit tests for WAL pager integration and remaining items."""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="attr-defined"

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.pager import Pager
from pyturso.storage.wal import WAL
from pyturso.storage.wal_pager import WALPager
from pyturso.storage.checkpoint import checkpoint
from pyturso.io.driver import run_to_completion
from pyturso.types.value import Value


# --- WAL pager integration ---
class TestWALPager:
    def test_cache_hit(self) -> None:
        """Cache hit: no WAL or file read needed."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\x00" * 8192))
        pager = Pager(io, "db", page_size=4096)
        pager._file = f
        pager._page_size = 4096
        pager._header = None

        wal_pager = WALPager(pager)
        # Write a page to cache.
        wal_pager.write_page(1, b"\xAA" * 4096)
        # Read it back — should come from cache (no I/O).
        data = run_to_completion(wal_pager.read_page(1))
        assert data == b"\xAA" * 4096

    def test_wal_hit(self) -> None:
        """WAL hit: page is in the WAL, not the main file."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\x00" * 8192))
        pager = Pager(io, "db", page_size=4096)
        pager._file = f
        pager._page_size = 4096
        pager._header = None

        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        # Append a page to the WAL.
        wal.append_frame(page_no=1, page_data=b"\xBB" * 4096, db_size=2)  # commit

        wal_pager = WALPager(pager, wal)
        # Read page 1 — should come from the WAL.
        data = run_to_completion(wal_pager.read_page(1))
        assert data == b"\xBB" * 4096

    def test_file_fallback(self) -> None:
        """File fallback: page not in cache or WAL, read from main file."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\xCC" * 4096 + b"\xDD" * 4096))
        pager = Pager(io, "db", page_size=4096)
        pager._file = f
        pager._page_size = 4096
        pager._header = None

        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        # No frames in the WAL.

        wal_pager = WALPager(pager, wal)
        # Read page 2 — should come from the main file.
        data = run_to_completion(wal_pager.read_page(2))
        assert data == b"\xDD" * 4096

    def test_wal_overrides_file(self) -> None:
        """WAL takes precedence over the main file."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\xCC" * 4096 + b"\xDD" * 4096))
        pager = Pager(io, "db", page_size=4096)
        pager._file = f
        pager._page_size = 4096
        pager._header = None

        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        # Write a new version of page 1 to the WAL.
        wal.append_frame(page_no=1, page_data=b"\xEE" * 4096, db_size=2)  # commit

        wal_pager = WALPager(pager, wal)
        # Read page 1 — should get the WAL version (\xEE), not the file (\xCC).
        data = run_to_completion(wal_pager.read_page(1))
        assert data == b"\xEE" * 4096

    def test_checkpoint_makes_wal_page_visible_in_file(self) -> None:
        """After checkpoint, WAL pages are in the main file."""
        io = MemoryIO()
        f = io.open_file("db")
        f.pwrite(WriteRequest(f, 0, b"\x00" * 8192))
        pager = Pager(io, "db", page_size=4096)
        pager._file = f
        pager._page_size = 4096
        pager._header = None

        wal = WAL(io, "wal")
        wal.create(page_size=4096)
        wal.append_frame(page_no=2, page_data=b"\xFF" * 4096, db_size=2)  # commit

        wal_pager = WALPager(pager, wal)

        # Read via WAL pager — gets WAL version.
        data = run_to_completion(wal_pager.read_page(2))
        assert data == b"\xFF" * 4096

        # Checkpoint: write WAL frames to main file.
        checkpoint(pager, wal)
        assert len(wal.frames) == 0  # WAL cleared

        # Clear the cache to force a file read.
        pager._cache._pages.clear()  # type: ignore[attr-defined]

        # Read again — should get the file version (now \xFF after checkpoint).
        data = run_to_completion(wal_pager.read_page(2))
        assert data == b"\xFF" * 4096


# --- crash injection (simplified) ---
class TestCrashInjection:
    def test_torn_wal_recovery(self) -> None:
        """A torn WAL (incomplete last frame) is detected on recovery."""
        io = MemoryIO()
        wal = WAL(io, "wal")
        wal.create(page_size=4096)

        # Append a committed frame.
        wal.append_frame(page_no=1, page_data=b"\xAA" * 4096, db_size=1)

        # Append an incomplete frame (simulating a crash mid-write).
        # We simulate this by writing a partial frame to the file.
        f = io.open_file("wal")
        frame_offset = 32 + 24 + 4096  # header + one full frame
        # Write just the frame header (no page data) — simulates a torn write.
        partial = (2).to_bytes(4, "big") + (0).to_bytes(4, "big") + b"\x00" * 16
        f.pwrite(WriteRequest(f, offset=frame_offset, data=partial))

        # Reopen the WAL — the torn frame should be detected.
        wal2 = WAL(io, "wal")
        header = wal2.open()
        assert header is not None
        # Only the first (committed) frame should be parsed.
        assert len(wal2.frames) == 1
        assert wal2.frames[0].page_data == b"\xAA" * 4096