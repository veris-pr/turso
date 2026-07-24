"""protocol — IO/File Protocols, request dataclasses, completion types.

Ports: core/io/mod.rs (``File``/``IO`` traits, ``FileSyncType``),
core/io/completions.rs (``Completion`` / ``CompletionType`` /
``CompletionError``).
Phase: 1
Status: IMPLEMENTED.

This is the keystone convention of the port: engine code **never blocks on I/O
directly** — it yields request objects and is resumed with a completion, so
every I/O boundary is explicit (mirroring Rust's ``IOResult``). The shape is::

    def read_page(file: File, page_size: int, page_no: int) -> Iterator[Request]:
        buf = yield ReadRequest(file, offset=(page_no - 1) * page_size, n=page_size)
        ...  # buf is the Completion carrying the read bytes

Rust's completion is callback-driven and carries an ``Arc<Buffer>`` + ``i32``
status (or a ``CompletionError``). pyturso's generators are pull-shaped: a
driver ``send()``s a :class:`Completion` back into the generator, which
unpacks it via :meth:`Completion.unwrap_read` / :meth:`Completion.unwrap_count`.
A failure completion carries the :class:`CompletionError` (ported from
``core/error.rs``'s ``CompletionError``) and raises it on unwrap — so
engine code's happy path reads ``buf = yield req`` and errors propagate
through the generator as exceptions, exactly as Rust's ``?`` does through a
state machine.

Requests are *dumb data* (frozen dataclasses): they describe the operation,
never how to perform it. Backends (``memory.py``, ``posix.py``) consume them.
``File`` and ``IO`` are :class:`typing.Protocol`s (structural), matching the
Rust traits — backends conform without inheritance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Union, runtime_checkable

__all__ = [
    "FileSyncType",
    "ReadRequest",
    "WriteRequest",
    "SyncRequest",
    "TruncateRequest",
    "Request",
    "CompletionError",
    "Completion",
    "File",
    "IO",
]


# ---------------------------------------------------------------------------
# FileSyncType — ports core/io/mod.rs `FileSyncType`.
# ---------------------------------------------------------------------------
class FileSyncType(Enum):
    """How thoroughly to flush on sync (ports ``FileSyncType``).

    ``Fsync`` is the regular fsync (may not flush the disk write cache on
    macOS); ``FullFsync`` flushes it (``F_FULLFSYNC`` on macOS). On other
    platforms both behave the same. pyturso's backends honor the distinction
    where the platform offers it and otherwise treat both as fsync.
    """

    Fsync = "fsync"
    FullFsync = "full_fsync"


# ---------------------------------------------------------------------------
# Request dataclasses — ports the (op, pos, buf/len) tuples of the Rust trait
# methods, lifted to first-class values so a generator can yield them.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReadRequest:
    """Read ``n`` bytes from ``file`` starting at byte ``offset``.

    On success the completion carries the bytes read (which may be shorter
    than ``n`` at/ past EOF — backends mimic ``os.pread``: never an error,
    just fewer bytes).
    """

    file: "File"
    offset: int
    n: int


@dataclass(frozen=True)
class WriteRequest:
    """Write ``data`` to ``file`` starting at byte ``offset``.

    On success the completion carries the number of bytes written.
    """

    file: "File"
    offset: int
    data: bytes


@dataclass(frozen=True)
class SyncRequest:
    """Flush ``file`` (data, and metadata where the platform allows).

    Carries the sync type so a backend can pick ``fsync`` vs ``fdatasync`` /
    ``F_FULLFSYNC`` as appropriate.
    """

    file: "File"
    sync_type: FileSyncType


@dataclass(frozen=True)
class TruncateRequest:
    """Truncate (or extend) ``file`` to exactly ``length`` bytes."""

    file: "File"
    length: int


#: Any request a generator may yield. A backend dispatches on the concrete type.
Request = Union[ReadRequest, WriteRequest, SyncRequest, TruncateRequest]


# ---------------------------------------------------------------------------
# CompletionError — ports core/error.rs `CompletionError` (the subset pyturso
# surfaces through the generator protocol). Kept here (not in pyturso.errors)
# because it is the I/O layer's own failure vocabulary, mirroring how Rust
# nests CompletionError inside LimboError.
# ---------------------------------------------------------------------------
class CompletionError(Exception):
    """An I/O completion failed. Ports ``core::CompletionError``.

    The payload carries a short label (``"short read"`` / ``"io error"`` / …)
    plus the failing detail, so a higher layer can raise the right
    :class:`pyturso.errors` class (the mapping lives in ``pyturso.errors``).
    """

    def __init__(self, kind: str, detail: str = "") -> None:
        self.kind: str = kind
        self.detail: str = detail
        msg = f"{kind}" if not detail else f"{kind}: {detail}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Completion — the value a driver send()s back into a generator to resume it.
# Ports the Rust completion's result branch: success carries a payload
# (read bytes or a count), failure carries a CompletionError.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Completion:
    """The result of one I/O request, sent back into the yielding generator.

    Exactly one of ``read_data`` / ``count`` / ``error`` is set:
      - ``read_data``: bytes returned by a successful :class:`ReadRequest`.
      - ``count``: the integer result of a successful :class:`WriteRequest`
        (bytes written), :class:`SyncRequest` (0), or
        :class:`TruncateRequest` (0).
      - ``error``: a :class:`CompletionError` for a failed completion.

    Generators unpack via :meth:`unwrap_read` / :meth:`unwrap_count`, which
    raise the carried error on a failure completion — so engine code's happy
    path reads ``buf = yield req`` and errors propagate as exceptions,
    exactly as Rust's ``?`` does.
    """

    read_data: bytes | None = None
    count: int | None = None
    error: CompletionError | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def unwrap_read(self) -> bytes:
        """Return the read bytes, or raise the carried :class:`CompletionError`.

        Raises :class:`TypeError` if this completion is not a read (a
        generator mis-matched request and completion type — a programming
        error, caught loudly rather than returning ``None`` as garbage).
        """
        if self.error is not None:
            raise self.error
        if self.read_data is None:
            raise TypeError("completion is not a read result")
        return self.read_data

    def unwrap_count(self) -> int:
        """Return the write/sync/truncate count, or raise the carried error.

        Raises :class:`TypeError` if this completion carries neither a count
        nor an error (a request/completion type mismatch).
        """
        if self.error is not None:
            raise self.error
        if self.count is None:
            raise TypeError("completion has no count result")
        return self.count


# ---------------------------------------------------------------------------
# File Protocol — ports core/io/mod.rs `trait File` (the read/write/sync/
# truncate surface; locking is deferred per the README parity notes).
# ---------------------------------------------------------------------------
@runtime_checkable
class File(Protocol):
    """A backend file handle. Ports ``core::io::File`` (subset).

    Backends implement these four methods; they take a request and return a
    :class:`Completion` synchronously (the generator convention is the
    engine's concern, not the backend's — a backend just performs the op).
    ``size`` is separate (not a request): it is a synchronous query used by
    the pager, not a resumable operation.
    """

    def pread(self, req: ReadRequest) -> Completion:
        """Read ``req.n`` bytes at ``req.offset``; return a read completion."""
        ...

    def pwrite(self, req: WriteRequest) -> Completion:
        """Write ``req.data`` at ``req.offset``; return a count completion."""
        ...

    def psync(self, req: SyncRequest) -> Completion:
        """Sync per ``req.sync_type``; return a count completion (0)."""
        ...

    def ptruncate(self, req: TruncateRequest) -> Completion:
        """Truncate to ``req.length``; return a count completion (0)."""
        ...

    def size(self) -> int:
        """Current file length in bytes (synchronous — not a request)."""
        ...


# ---------------------------------------------------------------------------
# IO Protocol — ports core/io/mod.rs `trait IO` (the file-factory + clock
# surface). Clock is layered in via #20 (clock.py); here IO is the file factory.
# ---------------------------------------------------------------------------
@runtime_checkable
class IO(Protocol):
    """An I/O backend: a factory of :class:`File` handles.

    Ports the ``open_file``/``create_file`` surface of ``core::io::IO``.
    ``direct`` (Rust's O_DIRECT path) is accepted and ignored by the in-process
    backends — concept parity only, no kernel direct-I/O (README parity notes).
    """

    def open_file(self, path: str, *, flags: int = 0, direct: bool = False) -> File:
        """Open (and create if needed, per flags) a file at ``path``."""
        ...