"""checksum — WAL checksum algorithm.

Ports: core/storage/sqlite3_ondisk.rs (``checksum_wal``).
Phase: 8
Status: IMPLEMENTED.

The WAL checksum is a Fibonacci-weighted running sum over 32-bit words:
  s0 += x[0] + s1
  s1 += x[1] + s0
iterated in pairs (8 bytes at a time). All arithmetic is wrapping (u32
overflow wraps around, like C). The checksum is **cumulative**: each frame's
checksum includes all previous frames' data, making torn-frame detection
possible (a partially written frame will have a wrong checksum).

The byte order of the 32-bit words is determined by the WAL header's magic:
  - ``0x377f0683`` (big-endian magic): checksum words are big-endian.
  - ``0x377f0682`` (little-endian magic): checksum words are little-endian.
"""

from __future__ import annotations

import struct

__all__ = ["checksum_wal", "WAL_MAGIC_BE", "WAL_MAGIC_LE"]

#: Big-endian magic → checksums use big-endian byte order.
WAL_MAGIC_BE: int = 0x377F0683

#: Little-endian magic → checksums use little-endian byte order.
WAL_MAGIC_LE: int = 0x377F0682

#: u32 mask for wrapping arithmetic.
_U32_MASK: int = 0xFFFFFFFF


def checksum_wal(
    buf: bytes,
    initial: tuple[int, int],
    big_endian: bool,
) -> tuple[int, int]:
    """Compute the WAL checksum over ``buf`` starting from ``initial``.

    Args:
        buf: data to checksum (must be a multiple of 8 bytes).
        initial: ``(s0, s1)`` — the running checksum from the previous frame
            or the WAL header.
        big_endian: if True, 32-bit words are big-endian; if False,
            little-endian. Determined by the WAL header's magic number.

    Returns:
        ``(s0, s1)`` — the updated running checksum.

    Ports ``checksum_wal``. The algorithm:
      s0 += x[i] + s1
      s1 += x[i+1] + s0
    with wrapping u32 arithmetic, iterated over 8-byte pairs.
    """
    if len(buf) % 8 != 0:
        raise ValueError(f"checksum buffer must be a multiple of 8 bytes, got {len(buf)}")

    s0 = initial[0] & _U32_MASK
    s1 = initial[1] & _U32_MASK
    fmt = ">I" if big_endian else "<I"

    i = 0
    n = len(buf)
    while i < n:
        v0 = struct.unpack_from(fmt, buf, i)[0]
        v1 = struct.unpack_from(fmt, buf, i + 4)[0]
        s0 = (s0 + v0 + s1) & _U32_MASK
        s1 = (s1 + v1 + s0) & _U32_MASK
        i += 8

    return s0, s1