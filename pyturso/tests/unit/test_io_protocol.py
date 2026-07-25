"""Unit tests for pyturso.io.protocol — requests, completion, protocols.

Ports/verified against: core/io/mod.rs (File/IO traits, FileSyncType) and
core/io/completions.rs (Completion result branches, CompletionError).
"""

from __future__ import annotations

import pytest

from pyturso.io.protocol import (
    Completion,
    CompletionError,
    File,
    FileSyncType,
    IO,
    ReadRequest,
    Request,
    SyncRequest,
    TruncateRequest,
    WriteRequest,
)


class _FakeFile:
    """A minimal File: satisfies the Protocol structurally."""

    def pread(self, req: ReadRequest) -> Completion:
        return Completion(read_data=b"")

    def pwrite(self, req: WriteRequest) -> Completion:
        return Completion(count=len(req.data))

    def psync(self, req: SyncRequest) -> Completion:
        return Completion(count=0)

    def ptruncate(self, req: TruncateRequest) -> Completion:
        return Completion(count=0)

    def size(self) -> int:
        return 0


class _FakeIO:
    """A minimal IO: satisfies the Protocol structurally."""

    def open_file(self, path: str, *, flags: int =  0, direct: bool = False) -> File:
        return _FakeFile()


class _NoFile:
    """Wrong shape: missing methods."""

    def read(self, n: int) -> bytes:
        return b""


class _NoIO:
    def open(self, path: str) -> None:
        return None


# --- FileSyncType ----------------------------------------------------------
class TestFileSyncType:
    def test_two_variants(self) -> None:
        assert {FileSyncType.Fsync, FileSyncType.FullFsync} == set(FileSyncType)
        assert len(set(FileSyncType)) == 2


# --- request dataclasses (dumb data, frozen, fields) ---------------------
class TestRequests:
    def test_read_request_fields(self) -> None:
        f = _FakeFile()
        r = ReadRequest(file=f, offset=4096, n=100)
        assert r.file is f and r.offset == 4096 and r.n == 100

    def test_write_request_fields(self) -> None:
        f = _FakeFile()
        w = WriteRequest(file=f, offset=0, data=b"abc")
        assert w.file is f and w.offset == 0 and w.data == b"abc"

    def test_sync_request_fields(self) -> None:
        f = _FakeFile()
        s = SyncRequest(file=f, sync_type=FileSyncType.FullFsync)
        assert s.file is f and s.sync_type is FileSyncType.FullFsync

    def test_truncate_request_fields(self) -> None:
        f = _FakeFile()
        t = TruncateRequest(file=f, length=8192)
        assert t.file is f and t.length == 8192

    @pytest.mark.parametrize(
        "req", [
            ReadRequest(_FakeFile(), 0, 1),
            WriteRequest(_FakeFile(), 0, b""),
            SyncRequest(_FakeFile(), FileSyncType.Fsync),
            TruncateRequest(_FakeFile(), 0),
        ],
    )
    def test_requests_are_frozen(self, req: Request) -> None:
        import dataclasses
        with pytest.raises(dataclasses.FrozenInstanceError):
            # Frozen dataclass: any assignment raises. Use `file` (all have it).
            req.file = _FakeFile()  # type: ignore[misc]

    def test_requests_equal_by_value(self) -> None:
        f = _FakeFile()
        assert ReadRequest(f, 0, 1) == ReadRequest(f, 0, 1)
        assert ReadRequest(f, 0, 1) != ReadRequest(f, 0, 2)


# --- Completion: success payloads -----------------------------------------
class TestCompletionSuccess:
    def test_read_success_unwrap(self) -> None:
        c = Completion(read_data=b"hello")
        assert not c.is_error
        assert c.unwrap_read() == b"hello"

    def test_count_success_unwrap(self) -> None:
        c = Completion(count=42)
        assert not c.is_error
        assert c.unwrap_count() == 42

    def test_zero_count_is_valid(self) -> None:
        # sync/truncate return 0 — must not be treated as falsy/missing.
        assert Completion(count=0).unwrap_count() == 0

    def test_empty_read_is_valid(self) -> None:
        # EOF short read returns b"" — must unwrap cleanly.
        assert Completion(read_data=b"").unwrap_read() == b""


# --- Completion: error propagation ---------------------------------------
class TestCompletionError:
    def test_error_is_error(self) -> None:
        c = Completion(error=CompletionError("short read", "page 5"))
        assert c.is_error

    def test_unwrap_read_raises_completionerror(self) -> None:
        err = CompletionError("io error", "bad")
        with pytest.raises(CompletionError, match="io error"):
            Completion(error=err).unwrap_read()

    def test_unwrap_count_raises_completionerror(self) -> None:
        err = CompletionError("short write")
        with pytest.raises(CompletionError):
            Completion(error=err).unwrap_count()

    def test_completion_error_carries_kind_and_detail(self) -> None:
        e = CompletionError("short read", "expected 4096 got 10")
        assert e.kind == "short read"
        assert e.detail == "expected 4096 got 10"
        assert "short read" in str(e)


# --- Completion: type-mismatch (programming error) ------------------------
class TestCompletionTypeMismatch:
    def test_unwrap_read_on_count_raises_typeerror(self) -> None:
        with pytest.raises(TypeError):
            Completion(count=1).unwrap_read()

    def test_unwrap_count_on_read_raises_typeerror(self) -> None:
        with pytest.raises(TypeError):
            Completion(read_data=b"x").unwrap_count()

    def test_unwrap_read_on_empty_completion_raises_typeerror(self) -> None:
        with pytest.raises(TypeError):
            Completion().unwrap_read()


# --- Protocol structural conformance --------------------------------------
class TestProtocols:
    def test_fake_file_is_a_file(self) -> None:
        assert isinstance(_FakeFile(), File)

    def test_fake_io_is_an_io(self) -> None:
        assert isinstance(_FakeIO(), IO)

    def test_nonconforming_file_is_not_a_file(self) -> None:
        assert not isinstance(_NoFile(), File)

    def test_nonconforming_io_is_not_an_io(self) -> None:
        assert not isinstance(_NoIO(), IO)

    def test_protocols_are_runtime_checkable(self) -> None:
        assert getattr(File, "_is_runtime_protocol", False)
        assert getattr(IO, "_is_runtime_protocol", False)