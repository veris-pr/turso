"""Unit tests for pyturso.storage.sqlite3_ondisk varints.

Ports/verified against: core/storage/sqlite3_ondisk.rs (read_varint,
write_varint, varint_len). Boundary-focused: 1–9 byte widths and ±1 at every
width edge, per the storage TODO.

Varint encoding (SQLite format): bytes 1–8 carry 7 payload bits each (high bit
= continuation); the optional 9th byte carries a full 8 bits. So 1 byte encodes
0..127, 2 bytes 128..16383, …, 8 bytes up to 2**56-1, 9 bytes 2**56..2**64-1.
"""

from __future__ import annotations

import pytest

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import (
    MAX_VARINT_LEN,
    read_varint,
    varint_len,
    write_varint,
)

#: The width edges — the largest value encodable in N bytes (N=1..9) and the
#: value one past it. Every edge ±1 is exercised.
WIDTH_EDGES = [
    # (n_bytes, max_in_n_bytes, min_in_next_width)
    (1, 0x7F, 0x80),            # 0..127 / 128..
    (2, 0x3FFF, 0x4000),        # 16383 / 16384
    (3, 0x1F_FFFF, 0x20_0000),  # 2097151 / 2097152
    (4, 0x0FFF_FFFF, 0x1000_0000),
    (5, 0x07_FFFF_FFFF, 0x08_0000_0000),
    (6, 0x03_FFFF_FFFF_FF, 0x04_0000_000000),
    (7, 0x01_FFFF_FFFF_FFFF, 0x02_0000_00000000),
    (8, (1 << 56) - 1, 1 << 56),  # 8 bytes max / 9 bytes min
    (9, (1 << 64) - 1, None),     # 9 bytes max; no next width
]


# --- round-trip across all widths + edges ----------------------------------
class TestRoundTrip:
    @pytest.mark.parametrize(
        "value",
        [
            0, 1, 127, 128, 16383, 16384,
            2097151, 2097152,
            (1 << 32), (1 << 48),
            (1 << 56) - 1, (1 << 56),       # 8/9 byte boundary
            (1 << 63), (1 << 64) - 1,       # near u64 max
        ],
    )
    def test_write_then_read_round_trips(self, value: int) -> None:
        buf = bytearray(MAX_VARINT_LEN)
        n = write_varint(buf, value)
        decoded, n_read = read_varint(bytes(buf[:n]))
        assert decoded == value
        assert n_read == n

    def test_full_u64_max(self) -> None:
        value = (1 << 64) - 1
        buf = bytearray(MAX_VARINT_LEN)
        n = write_varint(buf, value)
        assert n == 9
        assert read_varint(bytes(buf[:9])) == (value, 9)


# --- width edges ±1 (the TODO's specific requirement) ---------------------
class TestWidthEdges:
    @pytest.mark.parametrize("n_bytes,max_val,next_val", WIDTH_EDGES)
    def test_max_of_width_uses_n_bytes(self, n_bytes: int, max_val: int, next_val: int) -> None:
        assert varint_len(max_val) == n_bytes
        buf = bytearray(MAX_VARINT_LEN)
        assert write_varint(buf, max_val) == n_bytes

    @pytest.mark.parametrize("n_bytes,max_val,next_val", WIDTH_EDGES)
    def test_plus_one_at_edge_grows_width(self, n_bytes: int, max_val: int, next_val: int) -> None:
        if next_val is None:
            pytest.skip("no next width above 9 bytes")
        assert varint_len(max_val) == n_bytes
        assert varint_len(next_val) == n_bytes + 1
        buf = bytearray(MAX_VARINT_LEN)
        assert write_varint(buf, next_val) == n_bytes + 1

    @pytest.mark.parametrize("n_bytes,max_val,next_val", WIDTH_EDGES)
    def test_minus_one_at_edge_stays_in_width(self, n_bytes: int, max_val: int, next_val: int) -> None:
        if max_val == 0:
            pytest.skip("nothing below 0")
        assert varint_len(max_val) == n_bytes
        assert varint_len(max_val - 1) == n_bytes

    def test_each_width_is_represented(self) -> None:
        # Sanity: every length 1..9 is reachable.
        lengths = set()
        for n, mx, _ in WIDTH_EDGES:
            lengths.add(varint_len(mx))
        assert lengths == set(range(1, 10))


# --- varint_len contract ---------------------------------------------------
class TestVarintLen:
    @pytest.mark.parametrize("value", [-1, -127])
    def test_negative_raises(self, value: int) -> None:
        with pytest.raises(ValueError):
            varint_len(value)

    def test_one_byte_values(self) -> None:
        for v in (0, 1, 0x7E, 0x7F):
            assert varint_len(v) == 1

    def test_nine_byte_values(self) -> None:
        assert varint_len(1 << 56) == 9
        assert varint_len((1 << 64) - 1) == 9


# --- read_varint: continuation bit + corrupt detection ---------------------
class TestReadVarint:
    def test_single_byte_no_continuation(self) -> None:
        assert read_varint(b"\x05") == (5, 1)

    def test_two_bytes_with_continuation(self) -> None:
        # 0x81 0x00 -> (1<<7) + 0 = 128
        assert read_varint(b"\x81\x00") == (128, 2)

    def test_reads_only_needed_bytes(self) -> None:
        # Extra trailing bytes must be ignored (only the varint is consumed).
        assert read_varint(b"\x05\xff\xff") == (5, 1)

    def test_too_short_raises_corrupt(self) -> None:
        with pytest.raises(Corrupt, match="Invalid varint"):
            read_varint(b"")

    def test_truncated_continuation_raises_corrupt(self) -> None:
        # High bit set but no following byte.
        with pytest.raises(Corrupt):
            read_varint(b"\x80")

    def test_9_byte_with_zero_top_bits_is_corrupt(self) -> None:
        # A 9-byte varint must encode >= 2**56; if the top 8 bits are zero it
        # is an invalid (wasteful) encoding — Rust bails Corrupt.
        # Build: 8 continuation bytes that accumulate to a small value, + 9th.
        # 0x80 0x80 ... 0x80 0x00 accumulates v=0 after 8 bytes → top bits zero.
        with pytest.raises(Corrupt):
            read_varint(b"\x80" * 8 + b"\x00")

    def test_valid_9_byte_varint(self) -> None:
        # Encode 2**56 and read it back — must be 9 bytes, value exact.
        buf = bytearray(MAX_VARINT_LEN)
        n = write_varint(buf, 1 << 56)
        assert n == 9
        v, n_read = read_varint(bytes(buf[:9]))
        assert v == 1 << 56 and n_read == 9


# --- write_varint: buffer contract ----------------------------------------
class TestWriteVarint:
    def test_writes_into_first_bytes(self) -> None:
        buf = bytearray(b"\xff" * 9)
        n = write_varint(buf, 5)
        assert buf[0] == 5
        assert buf[1] == 0xFF  # untouched beyond n
        assert n == 1

    def test_negative_raises(self) -> None:
        buf = bytearray(9)
        with pytest.raises(ValueError):
            write_varint(buf, -1)

    def test_too_short_buffer_raises(self) -> None:
        with pytest.raises(ValueError):
            write_varint(bytearray(2), 0x4000)

    def test_continuation_bits_set_correctly(self) -> None:
        # 2-byte varint for 128: high bit set on byte 0, clear on byte 1.
        buf = bytearray(9)
        write_varint(buf, 128)
        assert buf[0] & 0x80  # continuation
        assert not (buf[1] & 0x80)  # terminal: no continuation


# --- cross-check: varint_len matches write_varint output ------------------
class TestLenMatchesWrite:
    @pytest.mark.parametrize("value", [0, 1, 127, 128, 16383, 16384, 1 << 32,
                                       (1 << 56) - 1, 1 << 56, (1 << 64) - 1])
    def test_len_equals_bytes_written(self, value: int) -> None:
        buf = bytearray(MAX_VARINT_LEN)
        written = write_varint(buf, value)
        assert varint_len(value) == written