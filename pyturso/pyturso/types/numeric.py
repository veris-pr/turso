"""numeric — text→number conversion, i64 bounds, overflow-to-REAL.

Ports: core/vdbe/affinity.rs ``try_for_float`` + ``NumericParseResult`` +
``apply_numeric_affinity``; core/numeric/mod.rs i64 bounds handling.
Phase: 2
Status: IMPLEMENTED.

SQLite's text→number conversion is a **prefix parser** (ports
``try_for_float``): it reads the leading numeric characters, not the whole
string. ``"123abc"`` parses to ``123`` (a valid prefix); ``"abc"`` is not
numeric. This differs from Python's ``int()``/``float()`` which require the
whole string to be valid.

Key rules ported from the Rust:
  - Leading whitespace is skipped.
  - Optional ``+``/``-`` sign.
  - Digits before/after ``.``, optional ``e``/``E`` exponent.
  - A valid prefix that consumes the *entire* string → ``PureInteger`` or
    ``HasDecimalOrExp``. A valid prefix with trailing non-numeric →
    ``ValidPrefixOnly`` (SQLite's affinity conversion does NOT convert
    prefix-only text — it requires the whole string to be a number).
  - Integers that overflow i64 → REAL (f64).
  - Hex integers (``0x...``) → stay as TEXT (historical compatibility).
"""

from __future__ import annotations

import re
from enum import Enum

from pyturso.types.value import StorageClass, Value

__all__ = [
    "NumericParseResult",
    "try_parse_number",
    "text_to_numeric",
    "to_i64",
    "I64_MIN",
    "I64_MAX",
]

#: i64 bounds (ports Rust's i64 type).
I64_MIN: int = -(2**63)
I64_MAX: int = 2**63 - 1


class NumericParseResult(str, Enum):
    """How much of the input was a valid number. Ports the Rust enum."""

    NOT_NUMERIC = "NotNumeric"
    VALID_PREFIX_ONLY = "ValidPrefixOnly"
    PURE_INTEGER = "PureInteger"
    HAS_DECIMAL_OR_EXP = "HasDecimalOrExp"


#: Regex for the complete-number check (after strip): optional sign, digits,
#: optional decimal + digits, optional exponent. Matches the *entire* string.
_COMPLETE_NUMBER_RE: re.Pattern[str] = re.compile(
    r"^[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?$|^[+-]?\.\d+(?:[eE][+-]?\d+)?$"
)

#: Regex for the prefix check: what a valid numeric prefix looks like.
_PREFIX_RE: re.Pattern[str] = re.compile(
    r"^\s*[+-]?(\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
)

#: Hex integers — SQLite stores these as TEXT (historical compatibility).
_HEX_RE: re.Pattern[str] = re.compile(r"^\s*[+-]?0[xX][0-9a-fA-F]+\s*$")


def try_parse_number(s: str) -> tuple[NumericParseResult, Value | None]:
    """Parse ``s`` as a number, returning the parse classification + result.

    Ports ``try_for_float``. Returns ``(classification, Value)``:
      - ``NOT_NUMERIC`` → ``(NotNumeric, None)`` — not a number at all.
      - ``VALID_PREFIX_ONLY`` → ``(ValidPrefixOnly, Value)`` — has a valid
        numeric prefix but trailing non-numeric chars. SQLite's affinity
        conversion does NOT convert this (it stays text), but the value is
        returned so callers can decide.
      - ``PURE_INTEGER`` → ``(PureInteger, Value.integer(i))`` or
        ``Value.real(f)`` if the integer overflows i64.
      - ``HAS_DECIMAL_OR_EXP`` → ``(HasDecimalOrExp, Value.real(f))``.
    """
    s_stripped = s.strip()
    if not s_stripped:
        return NumericParseResult.NOT_NUMERIC, None

    # Hex integers stay as TEXT (historical).
    if _HEX_RE.match(s):
        return NumericParseResult.NOT_NUMERIC, None

    # Check if the entire string is a complete number.
    is_complete = bool(_COMPLETE_NUMBER_RE.match(s_stripped))

    # Extract the numeric prefix.
    m = _PREFIX_RE.match(s)
    if m is None:
        return NumericParseResult.NOT_NUMERIC, None

    prefix = m.group(0)
    # Determine if there's trailing junk after the prefix.
    remaining = s[m.end():].strip()
    if remaining and not is_complete:
        return NumericParseResult.VALID_PREFIX_ONLY, _parse_value(prefix)

    if not is_complete:
        return NumericParseResult.VALID_PREFIX_ONLY, _parse_value(prefix)

    # Complete number: classify as PureInteger or HasDecimalOrExp.
    # Classification is based on the input string (does it have . or e?),
    # NOT the parsed Value's storage class — an overflow integer becomes
    # REAL but is still a PureInteger (ports the Rust's classification).
    value = _parse_value(prefix)
    assert value is not None
    if "." not in prefix and "e" not in prefix and "E" not in prefix:
        return NumericParseResult.PURE_INTEGER, value
    return NumericParseResult.HAS_DECIMAL_OR_EXP, value


def _parse_value(s: str) -> Value | None:
    """Parse a clean numeric string (no whitespace) to a Value.

    Integers that fit i64 → Value.integer; overflow → Value.real.
    Reals → Value.real.
    """
    s = s.strip()
    # Try integer first.
    if "." not in s and "e" not in s and "E" not in s:
        try:
            i = int(s)
            if I64_MIN <= i <= I64_MAX:
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


def text_to_numeric(s: str) -> Value | None:
    """Convert text to a numeric Value, or None if not convertible.

    This is the affinity-application path (ports ``apply_numeric_affinity``):
    only **complete** numbers are converted (``PURE_INTEGER`` or
    ``HAS_DECIMAL_OR_EXP``); prefix-only strings stay as text (return None).
    """
    result, value = try_parse_number(s)
    if result in (NumericParseResult.PURE_INTEGER, NumericParseResult.HAS_DECIMAL_OR_EXP):
        return value
    return None


def to_i64(value: int) -> int:
    """Emulate i64 arithmetic: raise OverflowError if outside i64 range.

    Python ints don't wrap — the Rust uses i64 which wraps/overflows. This
    function checks bounds explicitly wherever the Rust does i64 arithmetic.
    Use it at the points where the Rust would overflow (e.g. integer
    addition, multiplication that might overflow).
    """
    if value < I64_MIN or value > I64_MAX:
        raise OverflowError(f"integer overflow: {value} outside i64 range")
    return value