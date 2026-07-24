"""Unit tests for pyturso.io.posix — real-file I/O backend.

Verified against: core/io/unix.rs (pread/pwrite/fsync/ftruncate/size) and the
os.pread contract (short read at EOF, positional writes, ftruncate semantics).
The same suite runs against the memory backend — both must agree on behaviour.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pyturso.io.posix import PosixFile, PosixIO
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
def io(tmp_path: Path) -> PosixIO:
    return PosixIO()


@pytest.fixture
def file(io: PosixIO, tmp_path: Path) -> PosixFile:
    return io.open_file(str(tmp_path / "test.db"))  # type: ignore[return-value]


# --- protocol conformance --------------------------------------------------
class TestProtocol:
    def test_posix_file_is_a_file(self, file: PosixFile) -> None:
        assert isinstance(file, File)

    def test_posix_io_is_an_io(self, io: PosixIO) -> None:
        assert isinstance(io, IO)


# --- read: short-at-EOF (os.pread semantics) -------------------------------
class TestRead:
    def test_read_empty_file_returns_empty(self, file: PosixFile) -> None:
        c = file.pread(ReadRequest(file, 0, 10))
        assert c.unwrap_read() == b""

    def test_read_short_at_eof(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"abc"

    def test_read_partial_within_file(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"hello world"))
        assert file.pread(ReadRequest(file, 6, 5)).unwrap_read() == b"world"

    def test_read_at_past_eof_returns_empty(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.pread(ReadRequest(file, 3, 10)).unwrap_read() == b""
        assert file.pread(ReadRequest(file, 100, 10)).unwrap_read() == b""

    def test_read_zero_bytes(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"abc"))
        assert file.pread(ReadRequest(file, 0, 0)).unwrap_read() == b""


# --- write: extends, overwrites, positional --------------------------------
class TestWrite:
    def test_write_returns_byte_count(self, file: PosixFile) -> None:
        assert file.pwrite(WriteRequest(file, 0, b"abc")).unwrap_count() == 3

    def test_write_then_read_round_trip(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"hello"))
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"hello"

    def test_write_at_offset_extends(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 10, b"xy"))
        assert file.size() >= 12
        assert file.pread(ReadRequest(file, 10, 2)).unwrap_read() == b"xy"

    def test_write_overwrites(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"aaaa"))
        file.pwrite(WriteRequest(file, 1, b"bb"))
        assert file.pread(ReadRequest(file, 0, 4)).unwrap_read() == b"abba"

    def test_write_empty_data(self, file: PosixFile) -> None:
        assert file.pwrite(WriteRequest(file, 0, b"")).unwrap_count() == 0


# --- truncate --------------------------------------------------------------
class TestTruncate:
    def test_truncate_shrinks(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"hello world"))
        file.ptruncate(TruncateRequest(file, 5))
        assert file.size() == 5
        assert file.pread(ReadRequest(file, 0, 10)).unwrap_read() == b"hello"

    def test_truncate_grows(self, file: PosixFile) -> None:
        file.pwrite(WriteRequest(file, 0, b"ab"))
        file.ptruncate(TruncateRequest(file, 5))
        assert file.size() == 5


# --- sync is callable (no assertion on what it does) -----------------------
class TestSync:
    def test_sync_returns_zero(self, file: PosixFile) -> None:
        for st in (FileSyncType.Fsync, FileSyncType.FullFsync):
            assert file.psync(SyncRequest(file, st)).unwrap_count() == 0


# --- persistence: data survives reopen (real file) -------------------------
class TestPersistence:
    def test_data_survives_reopen(
        self, io: PosixIO, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "persist.db")
        f1: PosixFile = io.open_file(path)  # type: ignore[assignment]
        f1.pwrite(WriteRequest(f1, 0, b"persistent"))
        f1.close()

        io2 = PosixIO()
        f2 = io2.open_file(path)
        assert f2.pread(ReadRequest(f2, 0, 20)).unwrap_read() == b"persistent"
        io2.close()

    def test_two_handles_share_file(
        self, io: PosixIO, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "shared.db")
        f1: PosixFile = io.open_file(path)  # type: ignore[assignment]
        f1.pwrite(WriteRequest(f1, 0, b"via f1"))
        f2: PosixFile = io.open_file(path)  # type: ignore[assignment]
        # f2 sees f1's writes (same underlying OS file, different fd).
        assert f2.pread(ReadRequest(f2, 0, 10)).unwrap_read() == b"via f1"


# --- error handling --------------------------------------------------------
class TestErrors:
    def test_read_on_closed_fd_raises_completionerror(
        self, file: PosixFile
    ) -> None:
        file.close()
        c = file.pread(ReadRequest(file, 0, 10))
        assert c.is_error
        with pytest.raises(Exception):  # CompletionError
            c.unwrap_read()