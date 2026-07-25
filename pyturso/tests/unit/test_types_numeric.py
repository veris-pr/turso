"""Unit tests for pyturso.types.numeric — text→number, i64 bounds, overflow.

Ports/verified against: core/vdbe/affinity.rs try_for_float +
NumericParseResult + apply_numeric_affinity; core/numeric/mod.rs i64 bounds.
"""

from __future__ import annotations

import pytest

from pyturso.types.numeric import (
    I64_MAX,
    I64_MIN,
    NumericParseResult,
    text_to_numeric,
    to_i64,
    try_parse_number,
)
from pyturso.types.value import StorageClass, Value


# --- try_parse_number: classification --------------------------------------
class TestClassification:
    def test_empty_string_not_numeric(self) -> None:
        r, v = try_parse_number("")
        assert r is NumericParseResult.NOT_NUMERIC
        assert v is None

    def test_non_numeric(self) -> None:
        r, v = try_parse_number("abc")
        assert r is NumericParseResult.NOT_NUMERIC
        assert v is None

    def test_pure_integer(self) -> None:
        r, v = try_parse_number("42")
        assert r is NumericParseResult.PURE_INTEGER
        assert v == Value.integer(42)

    def test_negative_integer(self) -> None:
        r, v = try_parse_number("-7")
        assert r is NumericParseResult.PURE_INTEGER
        assert v == Value.integer(-7)

    def test_has_decimal(self) -> None:
        r, v = try_parse_number("3.14")
        assert r is NumericParseResult.HAS_DECIMAL_OR_EXP
        assert v == Value.real(3.14)

    def test_has_exponent(self) -> None:
        r, v = try_parse_number("1e5")
        assert r is NumericParseResult.HAS_DECIMAL_OR_EXP
        assert v == Value.real(1e5)

    def test_has_decimal_and_exp(self) -> None:
        r, v = try_parse_number("3.0e+2")
        assert r is NumericParseResult.HAS_DECIMAL_OR_EXP
        assert v == Value.real(300.0)

    def test_prefix_only(self) -> None:
        r, v = try_parse_number("123abc")
        assert r is NumericParseResult.VALID_PREFIX_ONLY

    def test_leading_whitespace(self) -> None:
        r, v = try_parse_number("  42  ")
        assert r is NumericParseResult.PURE_INTEGER
        assert v == Value.integer(42)

    def test_plus_sign(self) -> None:
        r, v = try_parse_number("+5")
        assert r is NumericParseResult.PURE_INTEGER
        assert v == Value.integer(5)

    def test_dot_without_digits_before(self) -> None:
        r, v = try_parse_number(".5")
        assert r is NumericParseResult.HAS_DECIMAL_OR_EXP
        assert v == Value.real(0.5)


# --- hex integers stay as TEXT (historical) --------------------------------
class TestHex:
    def test_hex_is_not_numeric(self) -> None:
        r, v = try_parse_number("0xFF")
        assert r is NumericParseResult.NOT_NUMERIC
        assert v is None

    def test_hex_uppercase(self) -> None:
        r, v = try_parse_number("0X1A")
        assert r is NumericParseResult.NOT_NUMERIC


# --- overflow-to-REAL -----------------------------------------------------
class TestOverflow:
    def test_integer_overflow_to_real(self) -> None:
        r, v = try_parse_number(str(2**63 + 1))
        assert r is NumericParseResult.PURE_INTEGER
        assert v is not None
        assert v.storage_class is StorageClass.REAL

    def test_large_negative_overflow(self) -> None:
        r, v = try_parse_number(str(-(2**63) - 1))
        assert r is NumericParseResult.PURE_INTEGER
        assert v is not None
        assert v.storage_class is StorageClass.REAL

    def test_i64_max_is_integer(self) -> None:
        r, v = try_parse_number(str(I64_MAX))
        assert v == Value.integer(I64_MAX)

    def test_i64_min_is_integer(self) -> None:
        r, v = try_parse_number(str(I64_MIN))
        assert v == Value.integer(I64_MIN)

    def test_i64_max_plus_one_overflows(self) -> None:
        r, v = try_parse_number(str(I64_MAX + 1))
        assert v is not None
        assert v.storage_class is StorageClass.REAL


# --- text_to_numeric (affinity application) -------------------------------
class TestTextToNumeric:
    def test_pure_integer_converts(self) -> None:
        v = text_to_numeric("42")
        assert v == Value.integer(42)

    def test_decimal_converts(self) -> None:
        v = text_to_numeric("3.14")
        assert v == Value.real(3.14)

    def test_prefix_only_returns_none(self) -> None:
        assert text_to_numeric("123abc") is None

    def test_non_numeric_returns_none(self) -> None:
        assert text_to_numeric("hello") is None

    def test_empty_returns_none(self) -> None:
        assert text_to_numeric("") is None

    def test_hex_returns_none(self) -> None:
        assert text_to_numeric("0xFF") is None

    def test_overflow_converts_to_real(self) -> None:
        v = text_to_numeric(str(2**63 + 1))
        assert v is not None
        assert v.storage_class is StorageClass.REAL


# --- to_i64 (bounds emulation) --------------------------------------------
class TestToI64:
    def test_in_range(self) -> None:
        assert to_i64(42) == 42
        assert to_i64(I64_MIN) == I64_MIN
        assert to_i64(I64_MAX) == I64_MAX

    def test_overflow_raises(self) -> None:
        with pytest.raises(OverflowError):
            to_i64(I64_MAX + 1)
        with pytest.raises(OverflowError):
            to_i64(I64_MIN - 1)
        with pytest.raises(OverflowError):
            to_i64(2**64)

    def test_zero(self) -> None:
        assert to_i64(0) == 0