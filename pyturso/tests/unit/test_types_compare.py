"""Unit tests for pyturso.types.compare — cross-class ordering, collations.

Ports/verified against: core/types.rs ValueRef::Ord, core/numeric/mod.rs
sqlite_int_float_cmp, core/translate/collate.rs compare_strings.
"""

from __future__ import annotations

import pytest

from pyturso.types.compare import (
    Collation,
    compare_strings,
    compare_values,
    sort_key,
)
from pyturso.types.value import Value


# --- cross-class total order: NULL < numeric < TEXT < BLOB ----------------
class TestTotalOrder:
    def test_null_less_than_everything(self) -> None:
        assert compare_values(Value.null(), Value.integer(0)) < 0
        assert compare_values(Value.null(), Value.real(0.0)) < 0
        assert compare_values(Value.null(), Value.text("")) < 0
        assert compare_values(Value.null(), Value.blob(b"")) < 0

    def test_null_equal_null(self) -> None:
        assert compare_values(Value.null(), Value.null()) == 0

    def test_numeric_less_than_text(self) -> None:
        assert compare_values(Value.integer(1), Value.text("0")) < 0
        assert compare_values(Value.real(1.0), Value.text("0")) < 0

    def test_numeric_less_than_blob(self) -> None:
        assert compare_values(Value.integer(1), Value.blob(b"\x00")) < 0

    def test_text_less_than_blob(self) -> None:
        assert compare_values(Value.text("z"), Value.blob(b"\x00")) < 0

    def test_blob_greater_than_everything(self) -> None:
        assert compare_values(Value.blob(b""), Value.text("z")) > 0
        assert compare_values(Value.blob(b""), Value.integer(999)) > 0
        assert compare_values(Value.blob(b""), Value.null()) > 0

    def test_reflexivity(self) -> None:
        for v in [Value.null(), Value.integer(1), Value.real(3.14),
                  Value.text("hi"), Value.blob(b"x")]:
            assert compare_values(v, v) == 0


# --- INTEGER ↔ INTEGER ---------------------------------------------------
class TestIntegerCompare:
    def test_basic(self) -> None:
        assert compare_values(Value.integer(1), Value.integer(2)) < 0
        assert compare_values(Value.integer(2), Value.integer(1)) > 0
        assert compare_values(Value.integer(5), Value.integer(5)) == 0

    def test_negative(self) -> None:
        assert compare_values(Value.integer(-1), Value.integer(0)) < 0
        assert compare_values(Value.integer(-5), Value.integer(-1)) < 0

    def test_i64_boundaries(self) -> None:
        assert compare_values(Value.integer(2**63 - 1), Value.integer(-(2**63))) > 0


# --- REAL ↔ REAL ----------------------------------------------------------
class TestRealCompare:
    def test_basic(self) -> None:
        assert compare_values(Value.real(1.0), Value.real(2.0)) < 0
        assert compare_values(Value.real(3.14), Value.real(3.14)) == 0

    def test_negative_zero(self) -> None:
        assert compare_values(Value.real(-0.0), Value.real(0.0)) == 0

    def test_nan_sorts_lowest(self) -> None:
        assert compare_values(Value.real(float("nan")), Value.real(0.0)) < 0


# --- INTEGER ↔ REAL (the careful case) -----------------------------------
class TestIntFloatCompare:
    def test_equal_value(self) -> None:
        assert compare_values(Value.integer(42), Value.real(42.0)) == 0

    def test_int_less_than_float(self) -> None:
        assert compare_values(Value.integer(41), Value.real(42.0)) < 0

    def test_int_greater_than_float(self) -> None:
        assert compare_values(Value.integer(43), Value.real(42.0)) > 0

    def test_non_integral_float_greater_than_equal_int(self) -> None:
        assert compare_values(Value.integer(42), Value.real(42.5)) < 0

    def test_large_float_outside_i64(self) -> None:
        assert compare_values(Value.integer(2**63 - 1), Value.real(1e20)) < 0
        assert compare_values(Value.integer(-(2**63)), Value.real(-1e20)) > 0

    def test_float_just_below_i64_max(self) -> None:
        assert compare_values(Value.integer(2**63 - 2), Value.real(float(2**63 - 1))) < 0


# --- TEXT ↔ TEXT: BINARY collation (default) -----------------------------
class TestBinaryCollation:
    def test_basic(self) -> None:
        assert compare_values(Value.text("a"), Value.text("b")) < 0
        assert compare_values(Value.text("b"), Value.text("a")) > 0
        assert compare_values(Value.text("abc"), Value.text("abc")) == 0

    def test_case_sensitive(self) -> None:
        # BINARY is case-sensitive: 'A' < 'a'.
        assert compare_values(Value.text("A"), Value.text("a")) < 0

    def test_shorter_prefix_first(self) -> None:
        assert compare_values(Value.text("ab"), Value.text("abc")) < 0


# --- TEXT ↔ TEXT: NOCASE collation (ASCII-only!) --------------------------
class TestNocaseCollation:
    def test_case_insensitive(self) -> None:
        assert compare_values(Value.text("Hello"), Value.text("HELLO"),
                              Collation.NOCASE) == 0
        assert compare_values(Value.text("abc"), Value.text("ABC"),
                              Collation.NOCASE) == 0

    def test_ordering(self) -> None:
        assert compare_values(Value.text("abc"), Value.text("abd"),
                              Collation.NOCASE) < 0
        # NOCASE: 'B' → 'b', 'a' → 'a', so 'B' > 'a' (b > a).
        assert compare_values(Value.text("B"), Value.text("a"),
                              Collation.NOCASE) > 0

    def test_ascii_only(self) -> None:
        # NOCASE only lowercases ASCII A-Z; non-ASCII compares as-is.
        # 'É' (U+00C9) is not lowered by NOCASE.
        assert compare_values(Value.text("É"), Value.text("é"),
                              Collation.NOCASE) != 0


# --- TEXT ↔ TEXT: RTRIM collation ----------------------------------------
class TestRtrimCollation:
    def test_trailing_spaces_ignored(self) -> None:
        assert compare_values(Value.text("abc   "), Value.text("abc"),
                              Collation.RTRIM) == 0
        assert compare_values(Value.text("abc"), Value.text("abc   "),
                              Collation.RTRIM) == 0

    def test_ordering_after_trim(self) -> None:
        assert compare_values(Value.text("ab  "), Value.text("abc"),
                              Collation.RTRIM) < 0
        assert compare_values(Value.text("abd  "), Value.text("abc"),
                              Collation.RTRIM) > 0

    def test_all_spaces_equal_empty(self) -> None:
        assert compare_values(Value.text("   "), Value.text(""),
                              Collation.RTRIM) == 0


# --- BLOB ↔ BLOB ----------------------------------------------------------
class TestBlobCompare:
    def test_byte_comparison(self) -> None:
        assert compare_values(Value.blob(b"\x00"), Value.blob(b"\x01")) < 0
        assert compare_values(Value.blob(b"\xff"), Value.blob(b"\x00")) > 0
        assert compare_values(Value.blob(b"abc"), Value.blob(b"abc")) == 0

    def test_shorter_first(self) -> None:
        assert compare_values(Value.blob(b"ab"), Value.blob(b"abc")) < 0


# --- compare_strings standalone --------------------------------------------
class TestCompareStrings:
    def test_binary(self) -> None:
        assert compare_strings("a", "b", Collation.BINARY) < 0
        assert compare_strings("b", "a", Collation.BINARY) > 0
        assert compare_strings("x", "x", Collation.BINARY) == 0

    def test_nocase(self) -> None:
        assert compare_strings("A", "a", Collation.NOCASE) == 0
        assert compare_strings("a", "B", Collation.NOCASE) < 0

    def test_rtrim(self) -> None:
        assert compare_strings("x  ", "x", Collation.RTRIM) == 0


# --- sort_key (for ORDER BY) ----------------------------------------------
class TestSortKey:
    def test_null_sorts_first(self) -> None:
        vals = [Value.integer(1), Value.null(), Value.text("a")]
        sorted_vals = sorted(vals, key=lambda v: sort_key(v))
        assert sorted_vals[0].is_null
        assert sorted_vals[1].is_integer
        assert sorted_vals[2].is_text

    def test_cross_class_order(self) -> None:
        vals = [
            Value.blob(b"x"), Value.null(), Value.integer(1),
            Value.text("a"), Value.real(2.0),
        ]
        sorted_vals = sorted(vals, key=lambda v: sort_key(v))
        assert sorted_vals[0].is_null
        assert sorted_vals[1].is_numeric  # integer or real
        assert sorted_vals[2].is_numeric
        assert sorted_vals[3].is_text
        assert sorted_vals[4].is_blob

    def test_integer_and_real_same_rank(self) -> None:
        # Both numeric → same class rank; sorted by value.
        vals = [Value.real(2.0), Value.integer(1), Value.real(3.0)]
        sorted_vals = sorted(vals, key=lambda v: sort_key(v))
        assert sorted_vals[0] == Value.integer(1)
        assert sorted_vals[1] == Value.real(2.0)
        assert sorted_vals[2] == Value.real(3.0)