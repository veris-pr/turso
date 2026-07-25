"""record — record (row) build/parse on storage varints + types serial.

Ports: core/types.rs ``ImmutableRecord`` / ``Record`` build/parse paths.
Phase: 2
Status: IMPLEMENTED.

A SQLite record is a header (serial-type varints) followed by the values in
order. Phase 1 had an inline ``parse_record`` in ``storage/sqlite3_ondisk.py``;
this module is the canonical home — it uses the varint code from storage and
the serial encode/decode from :mod:`pyturso.types.serial`, so there is one
record implementation, not two.

Build (:func:`build_record`): takes a list of :class:`Value` objects, encodes
each to its serial type + payload, builds the header (header_size varint +
serial-type varints), and returns the complete record bytes.

Parse (:func:`parse_record`): takes record bytes, reads the header_size
varint, reads each serial-type varint, then decodes each value from the body.
Returns a list of :class:`Value` objects.

The Phase 1 ``parse_record`` in ``sqlite3_ondisk.py`` returns a ``Record``
with raw Python values (``int``/``float``/``str``/``bytes``/``None``); this
module returns typed :class:`Value` objects. The refactor to make Phase 1 use
this module is the TODO's next step (delete the Phase 1 copy).
"""

from __future__ import annotations

from pyturso.errors import Corrupt
from pyturso.storage.sqlite3_ondisk import read_varint, write_varint
from pyturso.types.serial import decode_value, encode_value, serial_type_size
from pyturso.types.value import Value

__all__ = ["Record", "build_record", "parse_record"]

#: A record is a list of Values.
class Record:
    """A decoded record: a list of typed :class:`Value` objects."""

    __slots__ = ("values",)

    def __init__(self, values: list[Value]) -> None:
        self.values: list[Value] = values

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, idx: int) -> Value:
        return self.values[idx]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Record):
            return NotImplemented
        return self.values == other.values

    def __repr__(self) -> str:  # pragma: no cover
        return f"Record({self.values!r})"


def build_record(values: list[Value]) -> bytes:
    """Build a record from a list of :class:`Value` objects.

    The record format: header (header_size varint + serial-type varints) then
    the payload bytes (each value's encoded bytes in order).
    """
    # Encode each value to (serial_type, payload).
    encoded: list[tuple[int, bytes]] = [encode_value(v) for v in values]

    # Build the header: serial-type varints (header_size filled after).
    header: bytearray = bytearray()
    serial_types: list[int] = []
    for st, _ in encoded:
        serial_types.append(st)
    # Compute header bytes (without the header_size varint itself).
    serial_bytes: bytearray = bytearray()
    for st in serial_types:
        scratch = bytearray(9)  # write_varint needs >= 9 bytes
        n = write_varint(scratch, st)
        serial_bytes.extend(scratch[:n])
    # header_size = len(header_size varint) + len(serial_bytes).
    # The header_size varint encodes the total header size including itself.
    # Try increasing varint lengths until the encoded size is self-consistent.
    header = bytearray()
    for guess_len in range(1, 5):
        header_size = guess_len + len(serial_bytes)
        hs_buf = bytearray(9)
        n = write_varint(hs_buf, header_size)
        if n == guess_len:
            header = bytearray(hs_buf[:n]) + serial_bytes
            break
    else:
        raise Corrupt("header size varint computation failed")

    # Body: concatenate payloads.
    body: bytearray = bytearray()
    for _, payload in encoded:
        body.extend(payload)

    return bytes(header) + bytes(body)


def parse_record(buf: bytes) -> Record:
    """Parse a record from ``buf`` into a :class:`Record` of :class:`Value`.

    Reads the header_size varint, then each serial-type varint, then decodes
    each value from the body. Returns a :class:`Record` with typed Values.
    """
    header_size, n = read_varint(buf)
    pos = n
    serial_types: list[int] = []
    while pos < header_size:
        st, n = read_varint(buf[pos:])
        serial_types.append(st)
        pos += n
    if pos != header_size:
        raise Corrupt(
            f"record header size mismatch: declared {header_size}, "
            f"consumed {pos}"
        )
    # Values follow the header.
    value_pos = header_size
    values: list[Value] = []
    for st in serial_types:
        size = serial_type_size(st)
        if value_pos + size > len(buf):
            raise Corrupt(
                f"record body too short: need {size} bytes at {value_pos}, "
                f"have {len(buf) - value_pos}"
            )
        values.append(decode_value(st, buf[value_pos : value_pos + size]))
        value_pos += size
    return Record(values)