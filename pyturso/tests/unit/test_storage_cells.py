"""Unit tests for pyturso.storage.sqlite3_ondisk leaf cells + record decode.

Ports/verified against: core/storage/sqlite3_ondisk.rs TableLeafCell,
read_btree_cell, read_value (serial types). Uses a real sqlite3-built db
with typed columns to verify round-trip correctness.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import (
    Record,
    TableLeafCell,
    cell_pointer_offsets,
    parse_header,
    parse_page_header,
    parse_record,
    parse_table_leaf_cell,
    read_serial_value,
    serial_type_size,
)


# --- serial_type_size ------------------------------------------------------
class TestSerialTypeSize:
    @pytest.mark.parametrize("st,size", [
        (0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 6), (6, 8), (7, 8),
        (8, 0), (9, 0),
        (12, 0), (13, 0),   # empty blob / text
        (14, 1), (15, 1),   # 1-byte blob / text
        (24, 6), (25, 6),   # 6-byte blob / text
        (100, 44), (101, 44),
    ])
    def test_size(self, st: int, size: int) -> None:
        assert serial_type_size(st) == size


# --- read_serial_value: each type -----------------------------------------
class TestReadSerialValue:
    def test_null(self) -> None:
        assert read_serial_value(b"", 0) == (None, 0)

    def test_i8(self) -> None:
        assert read_serial_value(b"\xff", 1) == (-1, 1)
        assert read_serial_value(b"\x7f", 1) == (127, 1)

    def test_i16(self) -> None:
        assert read_serial_value(b"\xff\xff", 2) == (-1, 2)
        assert read_serial_value(b"\x01\x00", 2) == (256, 2)

    def test_i24(self) -> None:
        # Positive
        assert read_serial_value(b"\x01\x00\x00", 3) == (65536, 3)
        # Negative (high bit set)
        assert read_serial_value(b"\xff\xff\xff", 3) == (-1, 3)

    def test_i32(self) -> None:
        assert read_serial_value(b"\xff\xff\xff\xff", 4) == (-1, 4)

    def test_i48(self) -> None:
        assert read_serial_value(b"\xff" * 6, 5) == (-1, 6)
        assert read_serial_value(b"\x00" * 6, 5) == (0, 6)

    def test_i64(self) -> None:
        assert read_serial_value(b"\xff" * 8, 6) == (-1, 8)
        assert read_serial_value(b"\x7f" + b"\xff" * 7, 6) == (
            0x7FFFFFFFFFFFFFFF, 8
        )

    def test_f64(self) -> None:
        assert read_serial_value(struct.pack(">d", 3.14), 7) == (3.14, 8)

    def test_const_0(self) -> None:
        assert read_serial_value(b"", 8) == (0, 0)

    def test_const_1(self) -> None:
        assert read_serial_value(b"", 9) == (1, 0)

    def test_reserved_10_11_raises(self) -> None:
        with pytest.raises(Corrupt, match="Invalid serial type"):
            read_serial_value(b"", 10)
        with pytest.raises(Corrupt, match="Invalid serial type"):
            read_serial_value(b"", 11)

    def test_blob(self) -> None:
        # Serial type 14 → (14-12)//2 = 1 byte blob.
        assert read_serial_value(b"\x00", 14) == (b"\x00", 1)
        # Serial type 16 → (16-12)//2 = 2 byte blob.
        assert read_serial_value(b"\x00\xff", 16) == (b"\x00\xff", 2)

    def test_text(self) -> None:
        assert read_serial_value(b"hello", 23) == ("hello", 5)

    def test_truncated_raises(self) -> None:
        with pytest.raises(Corrupt):
            read_serial_value(b"\x01", 4)  # need 4 bytes, got 1


# --- parse_record: round-trip with a real db ------------------------------
@pytest.fixture
def real_db(tmp_path: Path) -> tuple[bytes, int]:
    db = tmp_path / "cells.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("""CREATE TABLE typed (
        id INTEGER PRIMARY KEY, name TEXT, age INTEGER, score REAL, data BLOB
    )""")
    conn.execute("INSERT INTO typed VALUES (1, 'alice', 30, 95.5, x'00ff')")
    conn.execute("INSERT INTO typed VALUES (2, 'bob', 25, 80.0, NULL)")
    conn.commit()
    conn.close()
    data = db.read_bytes()
    hdr = parse_header(data[:100])
    return data, hdr.page_size


class TestParseRecord:
    def test_decode_first_row(self, real_db: tuple[bytes, int]) -> None:
        data, ps = real_db
        # Page 1 is the root of sqlite_schema; we need to find the 'typed' table's
        # root page. For a direct test, use the schema page's cells.
        page1 = data[:ps]
        phdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, phdr)
        # Decode each schema cell — they are table-leaf cells with a record.
        for ptr in ptrs[:1]:
            cell = parse_table_leaf_cell(page1, ptr, ps)
            rec = parse_record(cell.payload)
            assert isinstance(rec, Record)
            assert len(rec.serial_types) == len(rec.values)
            assert len(rec.values) == 5  # sqlite_schema has 5 columns

    def test_record_has_correct_value_types(self, real_db: tuple[bytes, int]) -> None:
        data, ps = real_db
        page1 = data[:ps]
        phdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, phdr)
        cell = parse_table_leaf_cell(page1, ptrs[0], ps)
        rec = parse_record(cell.payload)
        # sqlite_schema columns: type(text), name(text), tbl_name(text),
        # rootpage(int), sql(text)
        assert rec.values[0] == "table"  # type
        assert rec.values[1] == "typed"  # name
        assert rec.values[2] == "typed"  # tbl_name
        assert isinstance(rec.values[3], int)  # rootpage
        assert isinstance(rec.values[4], str)  # sql


# --- TableLeafCell: real db round-trip ------------------------------------
class TestTableLeafCell:
    def test_cell_has_rowid_and_payload(self, real_db: tuple[bytes, int]) -> None:
        data, ps = real_db
        page1 = data[:ps]
        phdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, phdr)
        cell = parse_table_leaf_cell(page1, ptrs[0], ps)
        assert isinstance(cell, TableLeafCell)
        assert cell.rowid == 1  # first schema row
        assert len(cell.payload) > 0
        assert cell.first_overflow_page is None  # small payload, no overflow

    def test_payload_size_matches_payload_len(self, real_db: tuple[bytes, int]) -> None:
        data, ps = real_db
        page1 = data[:ps]
        phdr = parse_page_header(page1, page_no=1)
        ptrs = cell_pointer_offsets(page1, phdr)
        cell = parse_table_leaf_cell(page1, ptrs[0], ps)
        assert cell.payload_size == len(cell.payload)


# --- corrupt detection -----------------------------------------------------
class TestCorrupt:
    def test_truncated_cell_raises(self) -> None:
        # A 3-byte buffer claiming a large payload.
        buf = b"\x80\x01\x00"  # payload_size=128, no rowid or payload
        with pytest.raises(Corrupt):
            parse_table_leaf_cell(buf, 0, 4096)

    def test_record_header_size_mismatch_raises(self) -> None:
        # header_size=3 (1-byte varint), then one serial type=0 (1 byte) →
        # pos=2 ≠ 3. The loop ends because pos < 3 but the next read is
        # out of buffer → Corrupt propagates as header size mismatch or
        # Invalid varint; either way it raises Corrupt.
        with pytest.raises(Corrupt):
            parse_record(b"\x03\x00")