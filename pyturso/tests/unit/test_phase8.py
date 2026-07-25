"""Unit tests for Phase 8: WAL checksum, header/frame parse, append, recovery."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

from pyturso.errors import Corrupt
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.checksum import WAL_MAGIC_BE, WAL_MAGIC_LE, checksum_wal
from pyturso.storage.wal import (
    WAL, WAL_FRAME_HEADER_SIZE, WAL_HEADER_SIZE,
    WalFrame, WalHeader, parse_wal_header, parse_wal_frames,
)


# --- checksum ---
class TestChecksum:
    def test_empty_buffer(self) -> None:
        s0, s1 = checksum_wal(b"", (0, 0), big_endian=True)
        assert s0 == 0 and s1 == 0

    def test_known_values(self) -> None:
        # Simple 8-byte buffer, big-endian.
        buf = struct.pack(">II", 1, 2)
        s0, s1 = checksum_wal(buf, (0, 0), big_endian=True)
        # s0 = 0 + 1 + 0 = 1; s1 = 0 + 2 + 1 = 3
        assert s0 == 1
        assert s1 == 3

    def test_two_pairs(self) -> None:
        buf = struct.pack(">IIII", 1, 2, 3, 4)
        s0, s1 = checksum_wal(buf, (0, 0), big_endian=True)
        # First pair: s0=1, s1=3
        # Second pair: s0 = 1 + 3 + 3 = 7; s1 = 3 + 4 + 7 = 14
        assert s0 == 7
        assert s1 == 14

    def test_wrapping(self) -> None:
        # Large values to test u32 wrapping.
        buf = struct.pack(">II", 0xFFFFFFFF, 0xFFFFFFFF)
        s0, s1 = checksum_wal(buf, (0xFFFFFFFF, 0xFFFFFFFF), big_endian=True)
        # All wrapping — just check no Python int overflow.
        assert 0 <= s0 <= 0xFFFFFFFF
        assert 0 <= s1 <= 0xFFFFFFFF

    def test_little_endian(self) -> None:
        buf = struct.pack("<II", 1, 2)
        s0, s1 = checksum_wal(buf, (0, 0), big_endian=False)
        assert s0 == 1
        assert s1 == 3

    def test_non_multiple_of_8_raises(self) -> None:
        with pytest.raises(ValueError):
            checksum_wal(b"\x00" * 7, (0, 0), big_endian=True)


# --- WAL header parse ---
class TestWalHeader:
    def test_parse_valid(self) -> None:
        magic = WAL_MAGIC_BE
        header_bytes = (
            magic.to_bytes(4, "big")
            + (3007000).to_bytes(4, "big")
            + (4096).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + (0x12345678).to_bytes(4, "big")
            + (0xDEADBEEF).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
            + (0).to_bytes(4, "big")
        )
        hdr = parse_wal_header(header_bytes)
        assert hdr.magic == WAL_MAGIC_BE
        assert hdr.page_size == 4096
        assert hdr.salt_1 == 0x12345678
        assert hdr.salt_2 == 0xDEADBEEF
        assert hdr.big_endian is True

    def test_invalid_magic_raises(self) -> None:
        bad = (0x12345678).to_bytes(4, "big") + b"\x00" * 28
        with pytest.raises(Corrupt, match="magic"):
            parse_wal_header(bad)

    def test_short_buffer_raises(self) -> None:
        with pytest.raises(Corrupt):
            parse_wal_header(b"\x00" * 10)


# --- WAL append + read ---
class TestWalAppendRead:
    def test_create_and_append(self) -> None:
        """Create a WAL, append a frame, read it back."""
        io = MemoryIO()
        wal = WAL(io, "test.wal")
        header = wal.create(page_size=4096, salt_1=42, salt_2=99)
        assert header.page_size == 4096
        assert header.salt_1 == 42

        # Append a non-commit frame.
        page_data = b"\x01" * 4096
        wal.append_frame(page_no=2, page_data=page_data, db_size=0)
        assert len(wal.frames) == 1
        assert not wal.frames[0].is_commit

        # Append a commit frame.
        page_data2 = b"\x02" * 4096
        wal.append_frame(page_no=2, page_data=page_data2, db_size=5)
        assert len(wal.frames) == 2
        assert wal.frames[1].is_commit

        # The latest page 2 should be page_data2 (latest-frame-wins).
        result = wal.get_page(2)
        assert result == page_data2

    def test_reopen_and_read(self) -> None:
        """Create a WAL, append frames, reopen and read them back."""
        io = MemoryIO()
        wal = WAL(io, "test.wal")
        wal.create(page_size=4096, salt_1=1, salt_2=2)
        wal.append_frame(page_no=1, page_data=b"\xAA" * 4096, db_size=0)
        wal.append_frame(page_no=2, page_data=b"\xBB" * 4096, db_size=3)  # commit

        # Reopen.
        wal2 = WAL(io, "test.wal")
        header = wal2.open()
        assert header is not None
        assert len(wal2.frames) == 2
        assert wal2.get_page(1) == b"\xAA" * 4096
        assert wal2.get_page(2) == b"\xBB" * 4096

    def test_torn_frame_detection(self) -> None:
        """A frame with a wrong checksum is treated as the end of the WAL."""
        io = MemoryIO()
        wal = WAL(io, "test.wal")
        wal.create(page_size=4096)
        wal.append_frame(page_no=1, page_data=b"\x00" * 4096, db_size=1)  # commit

        # Corrupt the frame data (flip a byte in the page data).
        f = io.open_file("test.wal")
        data = bytearray(b"\x00" * 0)  # can't read from memory easily
        # Instead, just write bad data at the frame's page data offset.
        frame_data_offset = WAL_HEADER_SIZE + WAL_FRAME_HEADER_SIZE
        f.pwrite(WriteRequest(f, offset=frame_data_offset, data=b"\xFF" * 4096))

        # Reopen — the corrupted frame should be detected.
        wal2 = WAL(io, "test.wal")
        header = wal2.open()
        assert header is not None
        # The frame checksum won't match → 0 frames parsed.
        assert len(wal2.frames) == 0

    def test_empty_wal(self) -> None:
        """Opening a non-existent/empty WAL returns None."""
        io = MemoryIO()
        io.open_file("empty.wal")
        wal = WAL(io, "empty.wal")
        assert wal.open() is None

    def test_no_commit_frame(self) -> None:
        """Without a commit frame, get_page returns None (uncommitted data)."""
        io = MemoryIO()
        wal = WAL(io, "test.wal")
        wal.create(page_size=4096)
        wal.append_frame(page_no=1, page_data=b"\x00" * 4096, db_size=0)  # no commit
        assert wal.get_page(1) is None  # uncommitted → not visible