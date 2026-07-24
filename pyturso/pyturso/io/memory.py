"""memory — in-RAM I/O backend (bytes-backed); primary test backend.

Ports: core/io/memory.rs (``MemoryIO`` / ``MemoryFile`` / ``MemStore``).
Phase: 1
Status: IMPLEMENTED.

A bytes-backed in-memory file store. Rust's ``MemStore`` uses a
``BTreeMap<usize, MemPage>`` (page-aligned); pyturso uses a single
``bytearray`` per file — the idiomatic Python equivalent that preserves the
exact ``os.pread`` semantics the protocol requires:

  - **Read** at/ past EOF returns short data (fewer bytes than requested),
    never an error. Holes (never-written regions) read as zeros (bytearray
    zero-initializes).
  - **Write** places bytes at the offset, extending the file if needed.
  - **Truncate** sets the file length (shrinking drops data, growing
    zero-fills).
  - **Sync** is a no-op (the data is already in RAM).

This mirrors ``MemStore::read_into`` / ``write_at`` / ``truncate`` byte-for-
byte in *behaviour*; the page decomposition is a Rust memory optimization with
no behavioural effect, so pyturso keeps the simpler representation (README:
"concept parity only").

``MemoryIO`` is a dict of named files (ports ``MemoryIO::open_file`` with
``OpenFlags::Create``): opening a new name creates an empty file; re-opening
an existing name returns the same backing store so a pager and a WAL can share
one in-memory database.
"""

from __future__ import annotations

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

__all__ = ["MemoryFile", "MemoryIO"]


class MemoryFile:
    """An in-memory file: a ``bytearray`` store conforming to :class:`File`.

    Constructed by :class:`MemoryIO`; the store is shared across re-openings of
    the same path so the file identity matches the "one backing store per
    name" contract.
    """

    def __init__(self, path: str, store: bytearray) -> None:
        self._path: str = path
        self._store: bytearray = store

    def pread(self, req: ReadRequest) -> Completion:
        """Read ``req.n`` bytes at ``req.offset``; short at EOF, zero-fill holes."""
        store = self._store
        size = len(store)
        if req.offset >= size or req.n == 0:
            return Completion(read_data=b"")
        # Available bytes from offset to EOF; never an error, just fewer.
        avail = size - req.offset
        n = min(req.n, avail)
        return Completion(read_data=bytes(store[req.offset : req.offset + n]))

    def pwrite(self, req: WriteRequest) -> Completion:
        """Write ``req.data`` at ``req.offset``, extending the file if needed."""
        store = self._store
        end = req.offset + len(req.data)
        if end > len(store):
            store.extend(b"\x00" * (end - len(store)))
        store[req.offset : end] = req.data
        return Completion(count=len(req.data))

    def psync(self, req: SyncRequest) -> Completion:
        """No-op: in-RAM data is already durable for the session."""
        return Completion(count=0)

    def ptruncate(self, req: TruncateRequest) -> Completion:
        """Truncate or extend (zero-fill) to ``req.length``."""
        store = self._store
        if req.length < len(store):
            del store[req.length :]
        elif req.length > len(store):
            store.extend(b"\x00" * (req.length - len(store)))
        return Completion(count=0)

    def size(self) -> int:
        return len(self._store)


class MemoryIO:
    """An in-memory :class:`IO` backend: a dict of named :class:`MemoryFile`s.

    ``open_file`` with a new path creates an empty store; re-opening an
    existing path returns a file backed by the *same* store, so concurrent
    handles share one in-memory database (matching SQLite's file identity).
    """

    def __init__(self) -> None:
        self._stores: dict[str, bytearray] = {}

    def open_file(self, path: str, *, flags: int = 0, direct: bool = False) -> File:
        if path not in self._stores:
            self._stores[path] = bytearray()
        return MemoryFile(path, self._stores[path])

    def remove_file(self, path: str) -> None:
        self._stores.pop(path, None)