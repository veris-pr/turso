"""compare — cross-class total order, collations.

Ports: core/types.rs (``ValueRef::Ord``), core/numeric/mod.rs
(``sqlite_int_float_cmp``, ``Numeric::Ord``), core/translate/collate.rs
(``CollationSeq``, ``compare_strings``).
Phase: 2
Status: IMPLEMENTED.

The cross-class total order (ports ``ValueRef::cmp``):

  - ``NULL < INTEGER/REAL < TEXT < BLOB``
  - Within numerics: INTEGER↔INTEGER = int compare; REAL↔REAL = float
    compare; INTEGER↔REAL uses ``sqlite_int_float_cmp`` (careful at large
    magnitudes where float precision degrades — the Rust converts the float
    to i64 when it's in range, compares as int first, then falls back to
    float-vs-float if the i64 conversion is exact).
  - Within TEXT: collation-dependent (BINARY = byte comparison; NOCASE =
    ASCII-only lowercasing; RTRIM = strip trailing spaces then BINARY).
  - Within BLOB: byte comparison.

NaN is treated as NULL (SQLite convention: NaN sorts lowest and compares
equal to nothing — ports the Rust's ``NonNan`` guard).
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Union

from pyturso.types.value import StorageClass, Value

__all__ = ["Collation", "compare_values", "compare_strings", "sort_key"]


class Collation(str, Enum):
    """Collation sequence. Ports ``CollationSeq`` (the three built-in ones)."""

    BINARY = "BINARY"
    NOCASE = "NOCASE"
    RTRIM = "RTRIM"


def compare_values(a: Value, b: Value, collation: Collation = Collation.BINARY) -> int:
    """Compare two :class:`Value`s, returning -1/0/+1 (a < b / == / >).

    The cross-class total order: NULL < numeric < TEXT < BLOB. Within TEXT,
    the ``collation`` applies. Within numerics, INTEGER↔REAL uses the careful
    ``sqlite_int_float_cmp`` (ports the Rust's precision handling at large
    magnitudes).
    """
    return _ordering_to_int(_cmp_values(a, b, collation))


def _cmp_values(a: Value, b: Value, collation: Collation) -> int:
    """Return Python's -1/0/1 ordering (ports ``Ord::cmp``)."""
    sa, sb = a.storage_class, b.storage_class

    # NULL handling: NULL < everything; NULL == NULL.
    if sa is StorageClass.NULL and sb is StorageClass.NULL:
        return 0
    if sa is StorageClass.NULL:
        return -1
    if sb is StorageClass.NULL:
        return 1

    # Numeric < TEXT < BLOB.
    if a.is_numeric and not b.is_numeric:
        return -1
    if b.is_numeric and not a.is_numeric:
        return 1

    # Both numeric: INTEGER↔INTEGER, REAL↔REAL, INTEGER↔REAL.
    if a.is_numeric and b.is_numeric:
        return _cmp_numeric(a, b)

    # Both TEXT: collation comparison.
    if sa is StorageClass.TEXT and sb is StorageClass.TEXT:
        return compare_strings(a.payload, b.payload, collation)  # type: ignore[arg-type]

    # Both BLOB: byte comparison.
    if sa is StorageClass.BLOB and sb is StorageClass.BLOB:
        return _memcmp(a.payload, b.payload)  # type: ignore[arg-type]

    # TEXT < BLOB.
    if sa is StorageClass.TEXT:
        return -1
    return 1  # sa is BLOB, sb is TEXT


def _cmp_numeric(a: Value, b: Value) -> int:
    """Compare two numeric Values (INTEGER↔INTEGER, REAL↔REAL, INTEGER↔REAL).

    Ports ``Numeric::cmp`` + ``sqlite_int_float_cmp``. The int↔float case
    handles large magnitudes carefully: if the float is outside i64 range,
    the int wins by magnitude; if the float is in range, convert to i64 and
    compare as integers, falling back to float comparison when the i64
    conversion is exact.
    """
    if a.is_integer and b.is_integer:
        ia = a.payload
        ib = b.payload
        assert isinstance(ia, int) and isinstance(ib, int)
        return (ia > ib) - (ia < ib)

    if a.is_real and b.is_real:
        fa = a.payload
        fb = b.payload
        assert isinstance(fa, (int, float)) and isinstance(fb, (int, float))
        fa, fb = float(fa), float(fb)
        # SQLite treats NaN as NULL (sorts lowest); NonNan guarantees no NaN
        # in the Rust. In Python, check explicitly.
        if math.isnan(fa) and math.isnan(fb):
            return 0
        if math.isnan(fa):
            return -1
        if math.isnan(fb):
            return 1
        return (fa > fb) - (fa < fb)

    # Mixed: one INTEGER, one REAL.
    if a.is_integer and b.is_real:
        return _sqlite_int_float_cmp(a.payload, float(b.payload))  # type: ignore[arg-type]
    return _sqlite_int_float_cmp(b.payload, float(a.payload))  # type: ignore[arg-type]


def _sqlite_int_float_cmp(int_val: int, float_val: float) -> int:
    """Compare an i64 with an f64 (ports ``sqlite_int_float_cmp``).

    Handles NaN (treated as NULL → int is greater) and large magnitudes
    (if the float is outside i64 range, the int wins by sign). When the
    float is in i64 range, converts to i64 and compares; if equal, falls
    back to float comparison to detect non-integral parts.
    """
    if math.isnan(float_val):
        return 1  # int > NaN (NaN treated as NULL)

    # Float outside i64 range → int wins by magnitude.
    if float_val < -9223372036854775808.0:
        return 1  # int > float (float is very negative)
    if float_val >= 9223372036854775808.0:
        return -1  # int < float (float is very large)

    # Float is in i64 range: convert to int and compare.
    float_as_int = int(float_val)
    if int_val > float_as_int:
        return 1
    if int_val < float_as_int:
        return -1
    # Equal as ints: check if the float has a fractional part.
    int_as_float = float(int_val)
    return (int_as_float > float_val) - (int_as_float < float_val)


def compare_strings(lhs: str, rhs: str, collation: Collation = Collation.BINARY) -> int:
    """Compare two strings with the given collation. Returns -1/0/+1.

    Ports ``CollationSeq::compare_strings``.
    """
    if collation is Collation.BINARY:
        return _memcmp_str(lhs, rhs)
    if collation is Collation.NOCASE:
        return _nocase_cmp(lhs, rhs)
    if collation is Collation.RTRIM:
        return _memcmp_str(lhs.rstrip(" "), rhs.rstrip(" "))
    return _memcmp_str(lhs, rhs)  # default


def _memcmp(a: bytes, b: bytes) -> int:
    """Byte comparison (ports Rust ``slice::cmp``)."""
    return (a > b) - (a < b)


def _memcmp_str(a: str, b: str) -> int:
    """String byte comparison (ports ``str::cmp`` — compares UTF-8 bytes)."""
    return (a > b) - (a < b)


def _nocase_cmp(lhs: str, rhs: str) -> int:
    """ASCII-only case-insensitive comparison (ports ``nocase_cmp``).

    NOCASE lowercases only ASCII A-Z; non-ASCII bytes compare as-is (SQLite's
    NOCASE is ASCII-only — documented as a gotcha).
    """
    for left, right in zip(lhs.encode("utf-8"), rhs.encode("utf-8")):
        lo = left | 0x20 if 0x41 <= left <= 0x5A else left  # ASCII tolower
        ro = right | 0x20 if 0x41 <= right <= 0x5A else right
        if lo != ro:
            return (lo > ro) - (lo < ro)
    return (len(lhs) > len(rhs)) - (len(lhs) < len(rhs))


def sort_key(v: Value, collation: Collation = Collation.BINARY) -> tuple[int, object]:
    """Return a sort key for ``v`` that respects the total order.

    Used for ORDER BY: returns a tuple ``(class_rank, within_class_key)``
    where ``class_rank`` is 0/1/2/3 for NULL/numeric/TEXT/BLOB, and
    ``within_class_key`` is the comparable key within that class. This lets
    ``sorted()`` produce the correct cross-class ordering in one pass.
    """
    sc = v.storage_class
    if sc is StorageClass.NULL:
        return (0, 0)
    if sc is StorageClass.INTEGER:
        return (1, v.payload)
    if sc is StorageClass.REAL:
        return (1, v.payload)
    if sc is StorageClass.TEXT:
        s = v.payload
        assert isinstance(s, str)
        if collation is Collation.NOCASE:
            return (2, s.lower())
        if collation is Collation.RTRIM:
            return (2, s.rstrip(" "))
        return (2, s)
    if sc is StorageClass.BLOB:
        return (3, v.payload)
    return (4, 0)  # unreachable


def _ordering_to_int(cmp: int) -> int:
    """Normalize a comparison result to -1/0/+1."""
    return (cmp > 0) - (cmp < 0)