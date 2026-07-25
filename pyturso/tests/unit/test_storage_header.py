"""Unit tests for pyturso.storage.sqlite3_ondisk header parsing.

Ports/verified against: core/storage/sqlite3_ondisk.rs DatabaseHeader + PageSize.
Uses a real sqlite3-built database as the source of truth for field values
(the whole port is verified against real .db files — tools.mkdb built one).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import (
    HEADER_MAGIC,
    HEADER_SIZE,
    DatabaseHeader,
    TextEncoding,
    Version,
    parse_header,
)


@pytest.fixture
def real_db(tmp_path: Path) -> bytes:
    """Build a real sqlite3 db and return its first 100 bytes."""
    db = tmp_path / "real.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()
    return db.read_bytes()[:HEADER_SIZE]


# --- magic / corrupt detection --------------------------------------------
class TestMagicAndCorrupt:
    def test_bad_magic_raises_corrupt(self) -> None:
        bad = bytearray(b"SQLite format 3\x00" + b"\x00" * 84)
        bad[0:16] = b"NOT A DATABASE\x00\x00"
        with pytest.raises(Corrupt, match="File is not a database"):
            parse_header(bytes(bad))

    def test_good_magic_does_not_raise(self, real_db: bytes) -> None:
        parse_header(real_db)  # no exception

    def test_magic_constant(self) -> None:
        assert HEADER_MAGIC == b"SQLite format 3\x00"
        assert len(HEADER_MAGIC) == 16

    def test_short_buffer_raises_corrupt(self) -> None:
        with pytest.raises(Corrupt, match="too short"):
            parse_header(b"SQLite format 3\x00" + b"\x00" * 50)

    def test_empty_raises_corrupt(self) -> None:
        with pytest.raises(Corrupt):
            parse_header(b"")


# --- page size decode (the PageSize rule) ---------------------------------
class TestPageSize:
    def _hdr_with_page_size(self, raw_ps: int) -> bytes:
        buf = bytearray(HEADER_MAGIC + b"\x00" * 84)
        buf[16:18] = raw_ps.to_bytes(2, "big")
        return bytes(buf)

    def test_value_1_means_65536(self) -> None:
        h = parse_header(self._hdr_with_page_size(1))
        assert h.page_size == 65536

    def test_power_of_two_valid(self) -> None:
        # 65536 is stored as the value 1 (doesn't fit in 2 bytes) — covered by
        # test_value_1_means_65536. Here we test the storable power-of-two range.
        for ps in (512, 1024, 2048, 4096, 8192, 16384, 32768):
            assert parse_header(self._hdr_with_page_size(ps)).page_size == ps

    def test_not_power_of_two_raises(self) -> None:
        for bad in (300, 1000, 4095, 4097, 33333):
            with pytest.raises(Corrupt, match="invalid page size"):
                parse_header(self._hdr_with_page_size(bad))

    def test_below_minimum_raises(self) -> None:
        with pytest.raises(Corrupt):
            parse_header(self._hdr_with_page_size(256))

    def test_real_db_page_size(self, real_db: bytes) -> None:
        assert parse_header(real_db).page_size == 4096


# --- field decode (real db round-trip) ------------------------------------
class TestFieldDecode:
    def test_returns_database_header(self, real_db: bytes) -> None:
        assert isinstance(parse_header(real_db), DatabaseHeader)

    def test_versions_from_real_db(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        # sqlite3 writes 1 (legacy) for a fresh db without WAL.
        assert h.write_version in (Version.LEGACY, Version.WAL)
        assert h.read_version in (Version.LEGACY, Version.WAL)

    def test_reserved_space_usually_zero(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        assert h.reserved_space == 0

    def test_payload_fractions_canonical(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        assert h.max_embed_frac == 64
        assert h.min_embed_frac == 32
        assert h.leaf_frac == 32

    def test_database_size_in_pages(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        assert h.database_size >= 1

    def test_schema_format(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        # SQLite supports schema formats 1-4; modern sqlite3 writes 4.
        assert h.schema_format in (1, 2, 3, 4)

    def test_text_encoding_is_utf8(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        assert TextEncoding.is_utf8(h.text_encoding)

    def test_reserved_padding_is_20_bytes(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        assert len(h.reserved_padding) == 20

    def test_usable_page_size_minus_reserved(self, real_db: bytes) -> None:
        h = parse_header(real_db)
        assert h.usable_page_size() == h.page_size - h.reserved_space


# --- Version / TextEncoding helpers ---------------------------------------
class TestVersionEncoding:
    def test_version_wal(self) -> None:
        assert Version.is_wal(Version.WAL)
        assert not Version.is_wal(Version.LEGACY)

    def test_version_legacy(self) -> None:
        assert Version.is_legacy(Version.LEGACY)
        assert not Version.is_legacy(Version.WAL)

    def test_text_encoding_unset_is_utf8(self) -> None:
        assert TextEncoding.is_utf8(TextEncoding.UNSET)

    def test_text_encoding_utf8(self) -> None:
        assert TextEncoding.is_utf8(TextEncoding.UTF8)

    def test_text_encoding_utf16_not_utf8(self) -> None:
        assert not TextEncoding.is_utf8(TextEncoding.UTF16LE)
        assert not TextEncoding.is_utf8(TextEncoding.UTF16BE)


# --- header is exactly 100 bytes ------------------------------------------
class TestHeaderSize:
    def test_header_size_constant(self) -> None:
        assert HEADER_SIZE == 100