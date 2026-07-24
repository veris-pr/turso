"""serial — serial-type table: encode/decode between Value and record bytes.

Ports: core/types.rs (``SerialType``, ``SerialTypeKind``, ``From<T> for
SerialType``, ``serialize_serial``, ``read_value``).
Phase: 2
Status: IMPLEMENTED.

The serial type is the on-disk encoding tag per value in a record. This module
owns the *full* encode/decode between :class:`pyturso.types.value.Value` and
raw bytes — the decode side was inlined in ``storage/sqlite3_ondisk.py`` during
Phase 1; the TODO's next step (record.py) refactors that onto this module so
there is one implementation, not two.

Encoding rules (ports ``From<T> for SerialType``):

  - ``NULL``   → serial type 0, 0 payload bytes
  - ``INTEGER`` → minimal-width signed type:
      0 → type 8 (const 0, 0 bytes)
      1 → type 9 (const 1, 0 bytes)
      [-128, 127]         → type 1 (i8,  1 byte)
      [-32768, 32767]     → type 2 (i16, 2 bytes)
      [-8388608, 8388607] → type 3 (i24, 3 bytes)
      [-2^31, 2^31-1]     → type 4 (i32, 4 bytes)
      [-2^47, 2^47-1]     → type 5 (i48, 6 bytes)
      otherwise           → type 6 (i64, 8 bytes)
  - ``REAL``   → serial type 7, 8 bytes (f64 BE)
  - ``TEXT``   → type 13 + 2*len (odd ≥13), ``len`` payload bytes (UTF-8)
  - ``BLOB``   → type 12 + 2*len (even ≥12), ``len`` payload bytes

Decode reverses this: given a serial type and a byte slice, produce a
:class:`Value`. All multi-byte integers are big-endian two's complement,
matching the Rust exactly.
"""

from __future__ import annotations

import struct

from pyturso.errors import Corrupt
from pyturso.types.value import StorageClass, Value

__all__ = [
    "serial_type_size",
    "encode_value",
    "decode_value",
    "is_valid_serial_type",
]

# ---------------------------------------------------------------------------
# Integer width boundaries (ports core/types.rs constants).
# ---------------------------------------------------------------------------
_I8_LOW: int = -128
_I8_HIGH: int = 127
_I16_LOW: int = -32768
_I16_HIGH: int = 32767
_I24_LOW: int = -8388608
_I24_HIGH: int = 8388607
_I32_LOW: int = -(2**31)
_I32_HIGH: int = 2**31 - 1
_I48_LOW: int = -(2**47)
_I48_HIGH: int = 2**47 - 1


def is_valid_serial_type(n: int) -> bool:
    """Ports ``SerialType::u64_is_valid_serial_type`` — 10 and 11 are invalid."""
    return n != 10 and n != 11


def serial_type_size(st: int) -> int:
    """Bytes a value of serial type ``st`` occupies on disk.

    Ports ``SerialType::size``. Identical to the Phase 1
    ``sqlite3_ondisk.serial_type_size``; kept here as the canonical home.
    """
    if st == 0:
        return 0
    if st == 1:
        return 1
    if st == 2:
        return 2
    if st == 3:
        return 3
    if st == 4:
        return 4
    if st == 5:
        return 6
    if st == 6:
        return 8
    if st == 7:
        return 8
    if st in (8, 9):
        return 0
    if st in (10, 11):
        raise Corrupt(f"Invalid serial type: {st}")
    return (st - 12) // 2 if st % 2 == 0 else (st - 13) // 2


# ---------------------------------------------------------------------------
# Encode: Value → (serial_type, bytes)
# ---------------------------------------------------------------------------
def encode_value(v: Value) -> tuple[int, bytes]:
    """Encode ``v`` to its ``(serial_type, payload_bytes)`` pair.

    Ports ``From<T> for SerialType`` + ``Value::serialize_serial``. Chooses
    the minimal integer width exactly as the Rust does (const 0/1, then
    i8/i16/i24/i32/i48/i64 by range).
    """
    sc = v.storage_class
    if sc is StorageClass.NULL:
        return 0, b""
    if sc is StorageClass.INTEGER:
        i = v.payload
        assert isinstance(i, int)
        return _encode_integer(i)
    if sc is StorageClass.REAL:
        f = v.payload
        assert isinstance(f, (int, float))
        return 7, struct.pack(">d", float(f))
    if sc is StorageClass.TEXT:
        s = v.payload
        assert isinstance(s, str)
        data = s.encode("utf-8")
        return 13 + 2 * len(data), data
    if sc is StorageClass.BLOB:
        b = v.payload
        assert isinstance(b, bytes)
        return 12 + 2 * len(b), b
    raise Corrupt(f"unknown storage class: {sc}")


def _encode_integer(i: int) -> tuple[int, bytes]:
    """Encode an integer to its minimal-width serial type + payload bytes."""
    if i == 0:
        return 8, b""
    if i == 1:
        return 9, b""
    if _I8_LOW <= i <= _I8_HIGH:
        return 1, i.to_bytes(1, "big", signed=True)
    if _I16_LOW <= i <= _I16_HIGH:
        return 2, i.to_bytes(2, "big", signed=True)
    if _I24_LOW <= i <= _I24_HIGH:
        return 3, i.to_bytes(4, "big", signed=True)[1:]  # drop top byte
    if _I32_LOW <= i <= _I32_HIGH:
        return 4, i.to_bytes(4, "big", signed=True)
    if _I48_LOW <= i <= _I48_HIGH:
        return 5, i.to_bytes(8, "big", signed=True)[2:]  # drop top 2 bytes
    return 6, i.to_bytes(8, "big", signed=True)


# ---------------------------------------------------------------------------
# Decode: (serial_type, bytes) → Value
# ---------------------------------------------------------------------------
def decode_value(serial_type: int, buf: bytes) -> Value:
    """Decode a value of ``serial_type`` from ``buf``.

    Ports ``read_value``. Returns a :class:`Value`. Raises :class:`Corrupt` on
    truncated input or invalid serial type (10/11).
    """
    if serial_type == 0:
        return Value.null()
    if serial_type == 1:
        if len(buf) < 1:
            raise Corrupt("Invalid UInt8 value")
        return Value.integer(int.from_bytes(buf[0:1], "big", signed=True))
    if serial_type == 2:
        if len(buf) < 2:
            raise Corrupt("Invalid BEInt16 value")
        return Value.integer(int.from_bytes(buf[0:2], "big", signed=True))
    if serial_type == 3:
        if len(buf) < 3:
            raise Corrupt("Invalid BEInt24 value")
        b = buf[0:3]
        sign = 0xFF if b[0] & 0x80 else 0x00
        return Value.integer(
            int.from_bytes(bytes([sign, b[0], b[1], b[2]]), "big", signed=True)
        )
    if serial_type == 4:
        if len(buf) < 4:
            raise Corrupt("Invalid BEInt32 value")
        return Value.integer(int.from_bytes(buf[0:4], "big", signed=True))
    if serial_type == 5:
        if len(buf) < 6:
            raise Corrupt("Invalid BEInt48 value")
        b = buf[0:6]
        sign = 0xFF if b[0] & 0x80 else 0x00
        return Value.integer(
            int.from_bytes(
                bytes([sign, sign, b[0], b[1], b[2], b[3], b[4], b[5]]),
                "big", signed=True,
            )
        )
    if serial_type == 6:
        if len(buf) < 8:
            raise Corrupt("Invalid BEInt64 value")
        return Value.integer(int.from_bytes(buf[0:8], "big", signed=True))
    if serial_type == 7:
        if len(buf) < 8:
            raise Corrupt("Invalid BEFloat64 value")
        return Value.real(struct.unpack(">d", buf[0:8])[0])
    if serial_type == 8:
        return Value.integer(0)
    if serial_type == 9:
        return Value.integer(1)
    if serial_type in (10, 11):
        raise Corrupt(f"Invalid serial type: {serial_type}")
    # BLOB (even ≥12) or TEXT (odd ≥13).
    size = serial_type_size(serial_type)
    if len(buf) < size:
        raise Corrupt(f"value too short for serial type {serial_type}")
    if serial_type % 2 == 0:
        return Value.blob(bytes(buf[0:size]))
    return Value.text(buf[0:size].decode("utf-8"))