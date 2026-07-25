"""database — one Database per file; owns pager + WAL state; open/close.

Ports: core/lib.rs (Database).
Phase: 5
Status: IMPLEMENTED.

A :class:`Database` owns the I/O backend and the :class:`Pager`. It is the
top-level entry point: ``Database.open(path)`` opens a file, ``connect()``
returns a :class:`Connection` for executing SQL. Multiple connections can share
one database (single-process, no locking — Phase 8 adds transactions).
"""

from __future__ import annotations

from pathlib import Path

from pyturso.io.memory import MemoryIO
from pyturso.io.posix import PosixIO
from pyturso.storage.pager import Pager

__all__ = ["Database"]


class Database:
    """A database file: owns the I/O backend and pager.

    Constructed via :meth:`open` (file path) or :meth:`open_memory` (in-RAM).
    Each :meth:`connect` returns a new :class:`Connection` sharing the same
    pager (single-process, no file locking).
    """

    def __init__(self, io: object, path: str) -> None:
        self._io = io
        self._path = path
        self._pager: Pager | None = None

    @classmethod
    def open(cls, path: str) -> Database:
        """Open a database file at ``path`` (POSIX backend)."""
        io = PosixIO()
        db = cls(io, path)
        db._pager = Pager(io, path)
        db._pager.open()
        return db

    @classmethod
    def open_memory(cls) -> Database:
        """Create an in-memory database (MemoryIO backend)."""
        io = MemoryIO()
        db = cls(io, ":memory:")
        # Create a minimal valid SQLite database (empty sqlite_schema).
        # Write a minimal header to make the pager happy.
        import sqlite3
        import tempfile
        tmp = Path(tempfile.mktemp(suffix=".db"))
        conn = sqlite3.connect(str(tmp))
        conn.execute("PRAGMA page_size=4096")
        conn.execute("CREATE TABLE IF NOT EXISTS _init (x)")
        conn.commit()
        conn.close()
        from pyturso.io.protocol import WriteRequest
        f = io.open_file(":memory:")
        f.pwrite(WriteRequest(f, 0, tmp.read_bytes()))
        tmp.unlink()
        db._pager = Pager(io, ":memory:")
        db._pager.open()
        return db

    @classmethod
    def from_bytes(cls, raw: bytes) -> Database:
        """Open a database from raw bytes (in-memory)."""
        io = MemoryIO()
        f = io.open_file(":memory:")
        from pyturso.io.protocol import WriteRequest
        f.pwrite(WriteRequest(f, 0, raw))
        db = cls(io, ":memory:")
        db._pager = Pager(io, ":memory:")
        db._pager.open()
        return db

    @property
    def pager(self) -> Pager:
        if self._pager is None:
            raise RuntimeError("database not opened")
        return self._pager

    def connect(self) -> Connection:
        """Open a new connection to this database."""
        return Connection(self)

    def close(self) -> None:
        """Close the database (flush + close file handle)."""
        if self._pager is not None:
            self._pager.flush()
            self._pager = None


# Import at the end to avoid circular import.
from pyturso.connection import Connection  # noqa: E402