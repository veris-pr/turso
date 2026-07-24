"""posix — real-file I/O backend via os.pread/pwrite/fsync/ftruncate.

Ports: core/io/unix.rs (``UnixFile`` / ``UnixIO``), concept parity only.
Phase: 1
Status: IMPLEMENTED.

A real-file backend for the :mod:`pyturso.io.protocol`. Each ``pread`` /
``pwrite`` / ``psync`` / ``ptruncate`` calls the matching ``os`` function at
the requested offset, mirroring Rust's ``libc::pread``/``pwrite``/``fsync``/
``ftruncate``. ``size`` is ``os.fstat().st_size``. File handles are kept open
(an ``int`` fd) for the backend's lifetime; the caller closes them by dropping
the :class:`PosixIO` (or via :meth:`PosixIO.close`).

``sync`` honors :class:`FileSyncType` where the platform offers it: on macOS
``FullFsync`` would use ``F_FULLFSYNC`` (flush the disk write cache); pyturso
calls ``os.fsync`` for both variants on all platforms — the distinction is a
platform-specific mechanism with no behavioural effect on Linux, and the
README pins concept parity, not mechanism. Documented in the backend-matrix
reference (a later doc item).

Errors: an ``os`` failure becomes a :class:`CompletionError` (kind
``"io error"`` + the ``os`` error's detail), so engine code's ``unwrap_*``
raises the same exception type regardless of backend. A short read at EOF is
not an error (matches ``os.pread`` and the memory backend).

Thread-safety: ``pread``/``pwrite`` are positional (no shared file offset), so
the backend is safe for concurrent use from multiple generators driven by
different drivers — but pyturso is single-threaded until the MVCC phase
(README), so this is a forward-compatibility note, not a current concern.
"""

from __future__ import annotations

import os
from typing import IO as FileIO  # noqa: F401 — clarity; not used

from .protocol import (
    Completion,
    CompletionError,
    File,
    FileSyncType,
    IO,
    ReadRequest,
    SyncRequest,
    TruncateRequest,
    WriteRequest,
)

__all__ = ["PosixFile", "PosixIO"]

#: Open flags for create+readwrite, the default for a database file.
_DEFAULT_OPEN_FLAGS: int = os.O_RDWR | os.O_CREAT


class PosixFile:
    """A real-file :class:`File` backed by an OS file descriptor.

    Constructed by :class:`PosixIO.open_file`; the fd is owned and closed when
    :meth:`close` is called (or the :class:`PosixIO` that owns it is dropped).
    """

    def __init__(self, path: str, fd: int) -> None:
        self._path: str = path
        self._fd: int = fd
        self._closed: bool = False

    def pread(self, req: ReadRequest) -> Completion:
        """``os.pread`` at ``req.offset``; short at EOF, never an error."""
        try:
            data = os.pread(self._fd, req.n, req.offset)
        except OSError as exc:
            return Completion(error=CompletionError("io error", str(exc)))
        return Completion(read_data=data)

    def pwrite(self, req: WriteRequest) -> Completion:
        """``os.pwrite`` at ``req.offset``; returns bytes written."""
        try:
            written = os.pwrite(self._fd, req.data, req.offset)
        except OSError as exc:
            return Completion(error=CompletionError("io error", str(exc)))
        return Completion(count=written)

    def psync(self, req: SyncRequest) -> Completion:
        """``os.fsync`` — both :class:`FileSyncType` variants map to fsync."""
        try:
            os.fsync(self._fd)
        except OSError as exc:
            return Completion(error=CompletionError("io error", str(exc)))
        return Completion(count=0)

    def ptruncate(self, req: TruncateRequest) -> Completion:
        """``os.ftruncate`` to ``req.length``."""
        try:
            os.ftruncate(self._fd, req.length)
        except OSError as exc:
            return Completion(error=CompletionError("io error", str(exc)))
        return Completion(count=0)

    def size(self) -> int:
        """``os.fstat().st_size`` — synchronous, not a request."""
        return os.fstat(self._fd).st_size

    def close(self) -> None:
        """Close the file descriptor. Idempotent."""
        if not self._closed:
            os.close(self._fd)
            self._closed = True


class PosixIO:
    """A real-file :class:`IO` backend: opens files via ``os.open``.

    ``open_file`` with a new or existing path opens (creating if needed) and
    returns a :class:`PosixFile` wrapping the fd. Re-opening an existing path
    opens a *new* fd (unlike :class:`MemoryIO`'s shared store) — the OS file
    is the shared backing; each handle is its own fd, matching Unix semantics.
    """

    def __init__(self) -> None:
        self._files: list[PosixFile] = []

    def open_file(self, path: str, *, flags: int = 0, direct: bool = False) -> File:
        open_flags = flags if flags != 0 else _DEFAULT_OPEN_FLAGS
        fd = os.open(path, open_flags, 0o644)
        f = PosixFile(path, fd)
        self._files.append(f)
        return f

    def remove_file(self, path: str) -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def close(self) -> None:
        """Close all opened file descriptors."""
        for f in self._files:
            f.close()
        self._files.clear()