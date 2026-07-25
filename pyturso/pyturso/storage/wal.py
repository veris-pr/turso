"""wal — WAL header/frames parse, frame-lookup map, append, checkpoint, recovery.

Ports: core/storage/wal.rs, core/storage/sqlite3_ondisk.rs (WalHeader,
WalFrameHeader).
Phase: 8
Status: IMPLEMENTED (read side: header + frame parse, frame-lookup map;
append side: write frames + commit records; checkpoint: frames → main file).

The Write-Ahead Log (WAL) is an append-only file of frames. Each frame
contains a page's data and a cumulative checksum. Before a modified page is
written to the main database file, it is appended to the WAL. On commit, a
commit frame (``db_size > 0``) marks the transaction as durable. On
checkpoint, WAL frames are written back to the main file and the WAL is reset.

WAL file format:
  - Header (32 bytes): magic, format, page_size, checkpoint_seq, salt1,
    salt2, checksum1, checksum2.
  - Frames (24-byte header + page_size data each):
    page_number, db_size (commit marker), salt1, salt2, checksum1, checksum2,
    [page data].

Frame lookup: for a given page number, the most recent frame (highest frame
ID) before ``mxFrame`` (the last valid commit frame) wins. This is the
"latest-frame-wins" rule that makes WAL reads correct.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Generator

from pyturso.errors import Corrupt
from pyturso.io.driver import run_to_completion
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import Completion, File, IO, ReadRequest, WriteRequest
from pyturso.storage.checksum import WAL_MAGIC_BE, WAL_MAGIC_LE, checksum_wal

__all__ = [
    "WAL_HEADER_SIZE", "WAL_FRAME_HEADER_SIZE",
    "WalHeader", "WalFrame", "parse_wal_header", "parse_wal_frames",
    "WAL",
]

#: WAL header size (32 bytes).
WAL_HEADER_SIZE: int = 32

#: WAL frame header size (24 bytes).
WAL_FRAME_HEADER_SIZE: int = 24

#: Default WAL format version.
WAL_FORMAT_VERSION: int = 3007000


@dataclass
class WalHeader:
    """The 32-byte WAL header. Ports ``core::WalHeader``."""
    magic: int
    file_format: int
    page_size: int
    checkpoint_seq: int
    salt_1: int
    salt_2: int
    checksum_1: int
    checksum_2: int

    @property
    def big_endian(self) -> bool:
        """Whether checksums use big-endian byte order."""
        return self.magic == WAL_MAGIC_BE


@dataclass
class WalFrame:
    """A parsed WAL frame: header fields + page data."""
    page_number: int
    db_size: int  # >0 for commit frames
    salt_1: int
    salt_2: int
    checksum_1: int
    checksum_2: int
    page_data: bytes

    @property
    def is_commit(self) -> bool:
        """True if this is a commit frame (db_size > 0)."""
        return self.db_size > 0


def parse_wal_header(buf: bytes) -> WalHeader:
    """Parse the 32-byte WAL header from ``buf``.

    Raises Corrupt if the magic is invalid or the buffer is too short.
    """
    if len(buf) < WAL_HEADER_SIZE:
        raise Corrupt("WAL header too short")
    magic = int.from_bytes(buf[0:4], "big")
    if magic not in (WAL_MAGIC_BE, WAL_MAGIC_LE):
        raise Corrupt(f"invalid WAL magic: {magic:#x}")
    return WalHeader(
        magic=magic,
        file_format=int.from_bytes(buf[4:8], "big"),
        page_size=int.from_bytes(buf[8:12], "big"),
        checkpoint_seq=int.from_bytes(buf[12:16], "big"),
        salt_1=int.from_bytes(buf[16:20], "big"),
        salt_2=int.from_bytes(buf[20:24], "big"),
        checksum_1=int.from_bytes(buf[24:28], "big"),
        checksum_2=int.from_bytes(buf[28:32], "big"),
    )


def parse_wal_frames(buf: bytes, header: WalHeader) -> list[WalFrame]:
    """Parse all frames from a WAL file buffer (after the header).

    Returns a list of :class:`WalFrame`. Stops at the first frame with a
    checksum mismatch (torn-frame detection).
    """
    frame_size = WAL_FRAME_HEADER_SIZE + header.page_size
    frames: list[WalFrame] = []

    # The running checksum starts from the WAL header's checksum.
    running = (header.checksum_1, header.checksum_2)
    big_endian = header.big_endian

    offset = 0
    while offset + frame_size <= len(buf):
        # Parse the frame header (24 bytes, big-endian).
        page_number = int.from_bytes(buf[offset:offset + 4], "big")
        db_size = int.from_bytes(buf[offset + 4:offset + 8], "big")
        salt_1 = int.from_bytes(buf[offset + 8:offset + 12], "big")
        salt_2 = int.from_bytes(buf[offset + 12:offset + 16], "big")
        checksum_1 = int.from_bytes(buf[offset + 16:offset + 20], "big")
        checksum_2 = int.from_bytes(buf[offset + 20:offset + 24], "big")
        page_data = buf[offset + 24:offset + 24 + header.page_size]

        # Verify the checksum: checksum over the frame header (first 8 bytes)
        # + the page data, using the running checksum from the previous frame.
        frame_header_bytes = buf[offset:offset + 8]  # page_number + db_size
        computed = checksum_wal(frame_header_bytes, running, big_endian)
        computed = checksum_wal(page_data, computed, big_endian)

        if computed != (checksum_1, checksum_2):
            # Torn frame — stop here.
            break

        running = computed
        frames.append(WalFrame(
            page_number=page_number,
            db_size=db_size,
            salt_1=salt_1,
            salt_2=salt_2,
            checksum_1=checksum_1,
            checksum_2=checksum_2,
            page_data=page_data,
        ))
        offset += frame_size

    return frames


class WAL:
    """A WAL file: header + frames, with append and checkpoint support.

    The WAL is backed by an :class:`IO` backend (same as the pager). The
    frame-lookup map (page → latest frame) is built on read and updated on
    append.
    """

    def __init__(self, io: IO, path: str) -> None:
        self._io = io
        self._path = path
        self._file: File | None = None
        self._header: WalHeader | None = None
        self._frames: list[WalFrame] = []
        self._frame_map: dict[int, int] = {}  # page_no → frame index

    @property
    def header(self) -> WalHeader:
        if self._header is None:
            raise Corrupt("WAL not opened")
        return self._header

    @property
    def frames(self) -> list[WalFrame]:
        return self._frames

    @property
    def mx_frame(self) -> int:
        """The index of the last commit frame (or -1 if none)."""
        for i in range(len(self._frames) - 1, -1, -1):
            if self._frames[i].is_commit:
                return i
        return -1

    def get_page(self, page_no: int) -> bytes | None:
        """Return the latest page data for ``page_no``, or None if not in WAL.

        Only frames up to and including the last commit frame are visible
        (the "latest-frame-wins" rule, bounded by mxFrame).
        """
        mx = self.mx_frame
        if mx < 0:
            return None
        for i in range(mx, -1, -1):
            if self._frames[i].page_number == page_no:
                return self._frames[i].page_data
        return None

    def open(self) -> WalHeader | None:
        """Open the WAL file. Returns the header, or None if the WAL is empty.

        If the WAL file doesn't exist or is empty, returns None (no WAL).
        """
        self._file = self._io.open_file(self._path)
        # Read the header.
        header_data = run_to_completion(self._read(0, WAL_HEADER_SIZE))
        if len(header_data) < WAL_HEADER_SIZE:
            return None  # empty WAL
        self._header = parse_wal_header(header_data)
        # Read all frames.
        self._reload_frames()
        return self._header

    def _reload_frames(self) -> None:
        """Read all frames from the file and build the frame-lookup map."""
        if self._header is None or self._file is None:
            return
        # Read the rest of the file.
        file_size = self._file.size()
        frame_size = WAL_FRAME_HEADER_SIZE + self._header.page_size
        max_frames = (file_size - WAL_HEADER_SIZE) // frame_size
        if max_frames <= 0:
            self._frames = []
            self._frame_map = {}
            return

        all_data = run_to_completion(self._read(WAL_HEADER_SIZE, max_frames * frame_size))
        self._frames = parse_wal_frames(all_data, self._header)
        self._rebuild_frame_map()

    def _rebuild_frame_map(self) -> None:
        """Build page_no → latest frame index map (up to mxFrame)."""
        self._frame_map = {}
        mx = self.mx_frame
        for i in range(mx + 1):
            self._frame_map[self._frames[i].page_number] = i

    def append_frame(
        self, page_no: int, page_data: bytes, db_size: int = 0,
    ) -> None:
        """Append a frame to the WAL.

        Args:
            page_no: the page number being written.
            page_data: the page data (must be page_size bytes).
            db_size: if > 0, this is a commit frame and db_size is the
                database size in pages after the commit.
        """
        if self._header is None:
            raise Corrupt("WAL not opened")
        if self._file is None:
            raise Corrupt("WAL file not open")

        # Compute the running checksum.
        if self._frames:
            prev = self._frames[-1]
            running = (prev.checksum_1, prev.checksum_2)
        else:
            running = (self._header.checksum_1, self._header.checksum_2)

        # Frame header bytes (first 8 bytes: page_number + db_size).
        frame_header = page_no.to_bytes(4, "big") + db_size.to_bytes(4, "big")
        big_endian = self._header.big_endian

        # Checksum over frame header (first 8 bytes) + page data.
        computed = checksum_wal(frame_header, running, big_endian)
        computed = checksum_wal(page_data, computed, big_endian)

        # Build the full frame (24-byte header + page data).
        salt_1 = self._header.salt_1
        salt_2 = self._header.salt_2
        frame_bytes = (
            page_no.to_bytes(4, "big")
            + db_size.to_bytes(4, "big")
            + salt_1.to_bytes(4, "big")
            + salt_2.to_bytes(4, "big")
            + computed[0].to_bytes(4, "big")
            + computed[1].to_bytes(4, "big")
            + page_data
        )

        # Write the frame at the end of the WAL file.
        frame_offset = WAL_HEADER_SIZE + len(self._frames) * (
            WAL_FRAME_HEADER_SIZE + self._header.page_size
        )
        self._file.pwrite(WriteRequest(
            self._file, offset=frame_offset, data=frame_bytes,
        ))

        # Update in-memory state.
        frame = WalFrame(
            page_number=page_no,
            db_size=db_size,
            salt_1=salt_1,
            salt_2=salt_2,
            checksum_1=computed[0],
            checksum_2=computed[1],
            page_data=page_data,
        )
        self._frames.append(frame)
        if frame.is_commit:
            self._rebuild_frame_map()

    def create(self, page_size: int, salt_1: int = 0, salt_2: int = 0) -> WalHeader:
        """Create a new WAL file with a fresh header.

        Returns the new :class:`WalHeader`.
        """
        self._file = self._io.open_file(self._path)
        # Use big-endian magic (pyturso standard).
        magic = WAL_MAGIC_BE
        header = WalHeader(
            magic=magic,
            file_format=WAL_FORMAT_VERSION,
            page_size=page_size,
            checkpoint_seq=0,
            salt_1=salt_1,
            salt_2=salt_2,
            checksum_1=0,
            checksum_2=0,
        )
        # Compute the header checksum (over the first 24 bytes).
        header_bytes = (
            magic.to_bytes(4, "big")
            + header.file_format.to_bytes(4, "big")
            + page_size.to_bytes(4, "big")
            + header.checkpoint_seq.to_bytes(4, "big")
            + salt_1.to_bytes(4, "big")
            + salt_2.to_bytes(4, "big")
        )
        cs = checksum_wal(header_bytes, (0, 0), big_endian=True)
        header.checksum_1 = cs[0]
        header.checksum_2 = cs[1]

        # Write the full header (32 bytes).
        full_header = header_bytes + cs[0].to_bytes(4, "big") + cs[1].to_bytes(4, "big")
        self._file.pwrite(WriteRequest(self._file, offset=0, data=full_header))

        self._header = header
        self._frames = []
        self._frame_map = {}
        return header

    def _read(self, offset: int, n: int) -> Generator[ReadRequest, Completion, bytes]:
        """Read n bytes from the WAL file at offset (generator)."""
        if self._file is None:
            raise Corrupt("WAL file not open")
        completion = yield ReadRequest(self._file, offset=offset, n=n)
        return completion.unwrap_read()