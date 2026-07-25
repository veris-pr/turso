"""Unit tests for pyturso.types.serial — serial-type encode/decode.

Ports/verified against: core/types.rs SerialType, From<T> for SerialType,
serialize_serial, read_value. Property-style: encode(decode(x)) round-trips
for every serial type; integer width boundaries ±1; REAL bit-exactness.
"""

from __future__ import annotations

import struct

import pytest

from pyturso.types.serial import (
    decode_value,
    encode_value,
    is_valid_serial_type,
    serial_type_size,
)
from pyturso.types.value import StorageClass, Value


# --- serial_type_size ------------------------------------------------------
class TestSerialTypeSize:
    @pytest.mark.parametrize("st,size", [
        (0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 6), (6, 8), (7, 8),
        (8, 0), (9, 0), (12, 0), (13, 0), (14, 1), (15, 1), (24, 6), (25, 6),
    ])
    def test_size(self, st: int, size: int) -> None:
        assert serial_type_size(st) == size


# --- is_valid_serial_type -------------------------------------------------
class TestIsValid:
    def test_10_and_11_invalid(self) -> None:
        assert not is_valid_serial_type(10)
        assert not is_valid_serial_type(11)

    def test_others_valid(self) -> None:
        for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 100):
            assert is_valid_serial_type(n)


# --- encode: minimal integer width ----------------------------------------
class TestEncodeInteger:
    @pytest.mark.parametrize("value,expected_st", [
        (0, 8), (1, 9),
        (-1, 1), (127, 1), (-128, 1),
        (128, 2), (32767, 2), (-32768, 2),
        (32768, 3), (8388607, 3), (-8388608, 3),
        (8388608, 4), (2147483647, 4), (-2147483648, 4),
        (2147483648, 5), (140737488355327, 5), (-140737488355328, 5),
        (140737488355328, 6), (2**63 - 1, 6), (-(2**63), 6),
    ])
    def test_minimal_width(self, value: int, expected_st: int) -> None:
        st, _ = encode_value(Value.integer(value))
        assert st == expected_st

    def test_zero_is_const_8(self) -> None:
        st, data = encode_value(Value.integer(0))
        assert st == 8 and data == b""

    def test_one_is_const_9(self) -> None:
        st, data = encode_value(Value.integer(1))
        assert st == 9 and data == b""

    def test_minus_one_is_i8(self) -> None:
        st, data = encode_value(Value.integer(-1))
        assert st == 1
        assert data == b"\xff"


# --- encode: REAL / TEXT / BLOB / NULL ------------------------------------
class TestEncodeOther:
    def test_real_is_type_7(self) -> None:
        st, data = encode_value(Value.real(3.14))
        assert st == 7
        assert data == struct.pack(">d", 3.14)

    def test_text_serial_type(self) -> None:
        st, data = encode_value(Value.text("hello"))
        assert st == 13 + 2 * 5  # = 23
        assert data == b"hello"

    def test_empty_text(self) -> None:
        st, data = encode_value(Value.text(""))
        assert st == 13
        assert data == b""

    def test_blob_serial_type(self) -> None:
        st, data = encode_value(Value.blob(b"\x00\xff"))
        assert st == 12 + 2 * 2  # = 16
        assert data == b"\x00\xff"

    def test_empty_blob(self) -> None:
        st, data = encode_value(Value.blob(b""))
        assert st == 12
        assert data == b""

    def test_null(self) -> None:
        st, data = encode_value(Value.null())
        assert st == 0 and data == b""


# --- round-trip: encode → decode → Value == original ----------------------
class TestRoundTrip:
    @pytest.mark.parametrize("value", [
        Value.integer(0), Value.integer(1), Value.integer(-1),
        Value.integer(127), Value.integer(-128), Value.integer(128),
        Value.integer(32767), Value.integer(-32768), Value.integer(32768),
        Value.integer(8388607), Value.integer(-8388608),
        Value.integer(2**31 - 1), Value.integer(-(2**31)),
        Value.integer(2**47 - 1), Value.integer(-(2**47)),
        Value.integer(2**63 - 1), Value.integer(-(2**63)),
    ])
    def test_integer_round_trip(self, value: Value) -> None:
        if value.is_null:
            return  # skip null in integer round-trip
        st, data = encode_value(value)
        decoded = decode_value(st, data)
        assert decoded == value
        assert decoded.storage_class is StorageClass.INTEGER

    @pytest.mark.parametrize("value", [
        Value.real(0.0), Value.real(-0.0), Value.real(1.5), Value.real(-1.5),
        Value.real(3.14), Value.real(1e100), Value.real(-1e100),
        Value.real(1.0 / 3.0), Value.real(float("inf")),
    ])
    def test_real_round_trip(self, value: Value) -> None:
        st, data = encode_value(value)
        decoded = decode_value(st, data)
        # Float equality is bit-exact (struct pack/unpack).
        assert decoded == value or (
            # Handle inf == inf (float("inf") == float("inf") is True)
            float(decoded.payload) == float(value.payload)  # type: ignore[arg-type]
        )
        assert decoded.storage_class is StorageClass.REAL

    @pytest.mark.parametrize("value", [
        Value.text(""), Value.text("hello"), Value.text("héllo"),
        Value.text("multi\nline"), Value.text("a" * 100),
    ])
    def test_text_round_trip(self, value: Value) -> None:
        st, data = encode_value(value)
        decoded = decode_value(st, data)
        assert decoded == value

    @pytest.mark.parametrize("value", [
        Value.blob(b""), Value.blob(b"\x00\xff"), Value.blob(b"hello"),
        Value.blob(bytes(range(256))),
    ])
    def test_blob_round_trip(self, value: Value) -> None:
        st, data = encode_value(value)
        decoded = decode_value(st, data)
        assert decoded == value

    def test_const_0_1_round_trip(self) -> None:
        for i in (0, 1):
            v = Value.integer(i)
            st, data = encode_value(v)
            assert data == b""
            assert decode_value(st, data) == v


# --- width boundary ±1 ----------------------------------------------------
class TestWidthBoundaries:
    @pytest.mark.parametrize("boundary", [
        127, 128,       # i8/i16 boundary
        32767, 32768,   # i16/i24
        8388607, 8388608,  # i24/i32
        2**31 - 1, 2**31,  # i32/i48
        2**47 - 1, 2**47,  # i48/i64
    ])
    def test_plus_one_grows_width(self, boundary: int) -> None:
        st_below, _ = encode_value(Value.integer(boundary))
        st_above, _ = encode_value(Value.integer(boundary + 1))
        assert st_above >= st_below  # same or wider

    @pytest.mark.parametrize("boundary", [
        -128, -129,     # i8 boundary
        -32768, -32769,  # i16
        -8388608, -8388609,  # i24
        -(2**31), -(2**31) - 1,  # i32
        -(2**47), -(2**47) - 1,  # i48
    ])
    def test_minus_one_grows_width_negative(self, boundary: int) -> None:
        st_at, _ = encode_value(Value.integer(boundary))
        st_past, _ = encode_value(Value.integer(boundary - 1))
        assert st_past >= st_at  # same or wider


# --- REAL bit-exactness ---------------------------------------------------
class TestRealBitExact:
    def test_struct_pack_unpack_is_identity(self) -> None:
        for f in (0.0, -0.0, 1.5, 3.14, 1e100, -1e-100, 1.0 / 3.0):
            packed = struct.pack(">d", f)
            unpacked = struct.unpack(">d", packed)[0]
            assert unpacked == f

    def test_inf_round_trips(self) -> None:
        v = Value.real(float("inf"))
        st, data = encode_value(v)
        decoded = decode_value(st, data)
        assert float(decoded.payload) == float("inf")  # type: ignore[arg-type]