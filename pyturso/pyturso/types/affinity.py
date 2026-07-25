"""affinity — column-type → affinity resolution + application rules.

Ports: core/vdbe/affinity.rs (``Affinity``, ``Affinity::affinity``,
``Affinity::convert``, ``apply_numeric_affinity``).
Phase: 2
Status: IMPLEMENTED.

SQLite's affinity system determines how values are coerced when stored in or
compared against a column. The affinity is derived from the column's declared
type name via a fixed rule order (the spec — *rule order is the spec*):

  1. Contains ``INT`` → ``INTEGER`` affinity
  2. Contains ``CHAR`` or ``CLOB`` or ``TEXT`` → ``TEXT`` affinity
  3. Contains ``BLOB`` or empty → ``BLOB`` affinity (historically "NONE")
  4. Contains ``REAL`` or ``FLOA`` or ``DOUB`` → ``REAL`` affinity
  5. Otherwise → ``NUMERIC`` affinity

Application (coercion) rules — when a value is stored in a column with an
affinity:

  - ``TEXT``: integers/reals → text representation; text stays text; NULL/BLOB
    unchanged.
  - ``NUMERIC`` / ``INTEGER``: text → integer or real (in that preference); if
    text is a well-formed integer that fits i64 → INTEGER; if a well-formed
    real → REAL; otherwise stays TEXT. Hex integers stay TEXT (historical).
  - ``REAL``: like NUMERIC but forces integers to REAL.
  - ``BLOB``: no conversion (values stored as-is).

The text→number parsing rules (prefix parsing, overflow-to-REAL) are in
:mod:`pyturso.types.numeric` (the next item); this module calls into it
for the conversion.
"""

from __future__ import annotations

from enum import Enum
from typing import Union

from pyturso.types.value import StorageClass, Value

__all__ = ["Affinity", "affinity_from_type_name", "apply_affinity"]


class Affinity(str, Enum):
    """The five column affinities. Ports ``core::Affinity``."""

    TEXT = "TEXT"
    NUMERIC = "NUMERIC"
    INTEGER = "INTEGER"
    REAL = "REAL"
    BLOB = "BLOB"

    @property
    def has_affinity(self) -> bool:
        """True iff this is not BLOB (i.e. the column coerces values)."""
        return self is not Affinity.BLOB


def affinity_from_type_name(datatype: str) -> Affinity:
    """Resolve a column's declared type name to its affinity.

    Ports ``Affinity::affinity``. The rule order IS the spec — changing the
    order changes behavior. Rules are case-insensitive substring matches.
    """
    dt = datatype.upper()

    # Rule 1: INT → INTEGER
    if "INT" in dt:
        return Affinity.INTEGER

    # Rule 2: CHAR / CLOB / TEXT → TEXT
    if "CHAR" in dt or "CLOB" in dt or "TEXT" in dt:
        return Affinity.TEXT

    # Rule 3: BLOB or empty → BLOB (historically NONE)
    if "BLOB" in dt or dt == "":
        return Affinity.BLOB

    # Rule 4: REAL / FLOA / DOUB → REAL
    if "REAL" in dt or "FLOA" in dt or "DOUB" in dt:
        return Affinity.REAL

    # Rule 5: otherwise → NUMERIC
    return Affinity.NUMERIC


def apply_affinity(value: Value, aff: Affinity) -> Value:
    """Apply column affinity to a :class:`Value`, returning the coerced value.

    Ports ``Affinity::convert`` + ``apply_numeric_affinity``. Returns the
    input unchanged if no coercion applies (e.g. BLOB affinity, or a value
    already in the right form).

    Note: the text→number conversion is a simplified version here; the full
    parsing rules (prefix parsing, hex, overflow-to-REAL) land in
    :mod:`pyturso.types.numeric` (the next TODO item). Until then, this
    handles the common cases and delegates to ``float()``/``int()`` parsing.
    """
    if aff is Affinity.BLOB:
        return value  # no conversion

    if aff is Affinity.TEXT:
        return _apply_text_affinity(value)

    if aff is Affinity.NUMERIC or aff is Affinity.INTEGER:
        return _apply_numeric_affinity(value)

    if aff is Affinity.REAL:
        return _apply_real_affinity(value)

    return value  # unreachable (enum exhaustiveness)


def _apply_text_affinity(value: Value) -> Value:
    """TEXT affinity: convert numeric values to their text representation."""
    sc = value.storage_class
    if sc is StorageClass.INTEGER:
        i = value.payload
        assert isinstance(i, int)
        return Value.text(str(i))
    if sc is StorageClass.REAL:
        f = value.payload
        assert isinstance(f, (int, float))
        return Value.text(_format_float(f))
    return value  # TEXT, BLOB, NULL unchanged


def _apply_numeric_affinity(value: Value) -> Value:
    """NUMERIC/INTEGER affinity: convert text to integer or real if possible."""
    if value.storage_class is not StorageClass.TEXT:
        return value  # non-text unchanged
    s = value.payload
    assert isinstance(s, str)
    parsed = _try_parse_numeric(s)
    if parsed is not None:
        return parsed
    return value  # not a well-formed number → stays TEXT


def _apply_real_affinity(value: Value) -> Value:
    """REAL affinity: like NUMERIC but forces integers to REAL."""
    if value.storage_class is StorageClass.INTEGER:
        i = value.payload
        assert isinstance(i, int)
        return Value.real(float(i))
    if value.storage_class is StorageClass.TEXT:
        s = value.payload
        assert isinstance(s, str)
        parsed = _try_parse_numeric(s)
        if parsed is not None:
            # Force to REAL even if it parsed as INTEGER.
            if parsed.storage_class is StorageClass.INTEGER:
                i = parsed.payload
                assert isinstance(i, int)
                return Value.real(float(i))
            return parsed
    return value


def _try_parse_numeric(s: str) -> Value | None:
    """Try to parse ``s`` as an integer or real Value.

    Simplified for now: tries int first, then float. The full parsing rules
    (prefix parsing, hex, overflow-to-REAL, i64 bounds) land in the
    :mod:`pyturso.types.numeric` module (next TODO item).
    """
    s = s.strip()
    if not s:
        return None
    # Try integer first (NUMERIC prefers INTEGER).
    try:
        i = int(s)
        # Check i64 bounds — overflow to REAL if too large.
        if -(2**63) <= i <= 2**63 - 1:
            return Value.integer(i)
        return Value.real(float(i))
    except ValueError:
        pass
    # Try float.
    try:
        f = float(s)
        return Value.real(f)
    except ValueError:
        return None


def _format_float(f: float) -> str:
    """Format a float for TEXT affinity (matches SQLite's %.15g convention)."""
    return "%.15g" % f