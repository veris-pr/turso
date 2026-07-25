"""Unit tests for pyturso.io.memory — the in-RAM I/O backend.

Verified against: core/io/memory.rs MemStore (read_into/write_at/truncate
behaviour: short read at EOF, zero-fill holes, write extends, truncate
shrinks/grows) and the os.pread contract (never an error at EOF).
"""

from __future__ import annotations

import pytest

from pyturso.io.memory import MemoryFile, MemoryIO
from pyturso.io.protocol import (
    Completion,
    File,
    FileSyncType,
    IO,
    ReadRequest,
    SyncRequest,
    TruncateRequest,
    WriteRequest,
)


@pytest.fixture
def io() -> MemoryIO:
    return MemoryIO()


@pytest.fixture
def file(io: MemoryIO) -> MemoryFile:
    return io.open_file("test.db")  # type: ignore[return-value]


# --- protocol conformance --------------------------------------------------
class TestProtocol:
    def test_memory_file_is_a_file(self, file: MemoryFile) -> None:
        assert isinstance(file, File)

    def test_memory_io_is_an_io(self, io: MemoryIO) -> None:
        assert isinstance(io, IO)


# --- read: short-at-EOF, zero-fill holes -----------------------------------
class TestRead:
    def test_read_empty_file_returns_empty(self, file: MemoryFile) -> None:
        c = file.pread(ReadRequest(file, 0, 10))
        assert c.unwrap_read() == b""

    def test_read_at_or_past_eof_returns_empty(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.pread(ReadRequest(file, 3, 10)).unwrap_read() == b""
        assert file.pread(ReadRequest(file, 100, 10)).unwrap_read() == b""

    def test_read_short_at_eof(self, file: MemoryFile) -> None:
        # 3 bytes written, request 10 from offset 0 → get 3 (short read, no error).
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"abc"

    def test_read_partial_within_file(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"hello world"))
        assert file.pread(ReadRequest(file, 6, 5)).unwrap_read() == b"world"

    def test_read_zero_bytes(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.pread(ReadRequest(file, 0, 0)).unwrap_read() == b""

    def test_read_hole_zero_fills(self, file: MemoryFile) -> None:
        # Write at offset 10 (leaving a hole 0..10), then read from 0 → zeros.
        file.pwrite(WriteRequest(file, 10, b"x"))
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"\x00" * 10


# --- write: extends, overwrites --------------------------------------------
class TestWrite:
    def test_write_returns_byte_count(self, file: MemoryFile) -> None:
        assert file.pwrite(WriteRequest(file, 0, b"abc")).unwrap_count() == 3

    def test_write_extends_file(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.size() == 3
        file.pwrite(WriteRequest(file, 3, b"def"))
        assert file.size() == 6

    def test_write_at_offset_extends_with_hole(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 10, b"xy"))
        assert file.size() == 12
        # Hole is zero-filled.
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"\x00" * 10

    def test_write_overwrites_existing(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"aaaa"))
        file.pwrite(WriteRequest(file, 1, b"bb"))
        assert file.pread(ReadRequest(file, 0, 4)).unwrap_read() == b"abba"

    def test_write_empty_data(self, file: MemoryFile) -> None:
        assert file.pwrite(WriteRequest(file, 0, b"")).unwrap_count() == 0
        assert file.size() == 0


# --- truncate --------------------------------------------------------------
class TestTruncate:
    def test_truncate_shrinks(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"hello world"))
        file.ptruncate(TruncateRequest(file, 5))
        assert file.size() == 5
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"hello"

    def test_truncate_grows_zero_fill(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"ab"))
        file.ptruncate(TruncateRequest(file, 5))
        assert file.size() == 5
        assert file.pread(ReadRequest(file, 0, 5)).unwrap_read() == b"ab\x00\x00\x00"

    def test_truncate_to_same_size_noop(self, file: MemoryFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        file.ptruncate(TruncateRequest(file, 3))
        assert file.size() == 3


# --- sync is a no-op -------------------------------------------------------
class TestSync:
    def test_sync_returns_zero(self, file: MemoryFile) -> None:
        for st in (FileSyncType.Fsync, FileSyncType.FullFsync):
            assert file.psync(SyncRequest(file, st)).unwrap_count() == 0


# --- MemoryIO: file identity -----------------------------------------------
class TestMemoryIO:
    def test_reopen_same_path_shares_store(self, io: MemoryIO) -> None:
        f1 = io.open_file("db")
        f1.pwrite(WriteRequest(f1, 0, b"shared"))
        f2 = io.open_file("db")
        # Same backing store: f2 sees f1's writes.
        assert f2.pread(ReadRequest(f2, 0, 10)).unwrap_read() == b"shared"

    def test_different_paths_independent(self, io: MemoryIO) -> None:
        f1 = io.open_file("a")
        f2 = io.open_file("b")
        f1.pwrite(WriteRequest(f1, 0, b"aaa"))
        assert f2.size() == 0

    def test_remove_file(self, io: MemoryIO) -> None:
        io.open_file("x").pwrite(WriteRequest(io.open_file("x"), 0, b"data"))
        io.remove_file("x")
        # Re-open after remove → fresh empty store.
        assert io.open_file("x").size() == 0