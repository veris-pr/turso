"""Unit tests for pyturso.types.affinity — rule order + application.

Ports/verified against: core/vdbe/affinity.rs Affinity::affinity (rule order
IS the spec) + Affinity::convert + apply_numeric_affinity.
"""

from __future__ import annotations

import pytest

from pyturso.types.affinity import (
    Affinity,
    affinity_from_type_name,
    apply_affinity,
)
from pyturso.types.value import StorageClass, Value


# --- affinity resolution (rule order is the spec) -------------------------
class TestAffinityResolution:
    @pytest.mark.parametrize("typename,expected", [
        # Rule 1: INT → INTEGER
        ("INT", Affinity.INTEGER),
        ("INTEGER", Affinity.INTEGER),
        ("BIGINT", Affinity.INTEGER),
        ("TINYINT", Affinity.INTEGER),
        ("SMALLINT", Affinity.INTEGER),
        # Rule 2: CHAR/CLOB/TEXT → TEXT
        ("TEXT", Affinity.TEXT),
        ("VARCHAR", Affinity.TEXT),
        ("CHARACTER", Affinity.TEXT),
        ("CLOB", Affinity.TEXT),
        ("NCHAR", Affinity.TEXT),
        # Rule 3: BLOB or empty → BLOB
        ("BLOB", Affinity.BLOB),
        ("", Affinity.BLOB),
        # Rule 4: REAL/FLOA/DOUB → REAL
        ("REAL", Affinity.REAL),
        ("FLOAT", Affinity.REAL),
        ("DOUBLE", Affinity.REAL),
        ("DOUBLE PRECISION", Affinity.REAL),
        # Rule 5: otherwise → NUMERIC
        ("NUMERIC", Affinity.NUMERIC),
        ("DECIMAL", Affinity.NUMERIC),
        ("BOOLEAN", Affinity.NUMERIC),
        ("DATE", Affinity.NUMERIC),
    ])
    def test_resolution(self, typename: str, expected: Affinity) -> None:
        assert affinity_from_type_name(typename) is expected

    def test_case_insensitive(self) -> None:
        assert affinity_from_type_name("int") is Affinity.INTEGER
        assert affinity_from_type_name("text") is Affinity.TEXT
        assert affinity_from_type_name("Float") is Affinity.REAL

    def test_rule_order_int_before_text(self) -> None:
        # "INT" in "POINT" → INTEGER wins over any TEXT match.
        # But "POINT" has no CHAR/CLOB/TEXT → rule 1 applies.
        assert affinity_from_type_name("POINT") is Affinity.INTEGER

    def test_rule_order_char_before_blob(self) -> None:
        # "CHARBLOB" → CHAR matches rule 2 before BLOB matches rule 3.
        assert affinity_from_type_name("CHARBLOB") is Affinity.TEXT

    def test_has_affinity(self) -> None:
        assert Affinity.TEXT.has_affinity
        assert Affinity.NUMERIC.has_affinity
        assert not Affinity.BLOB.has_affinity


# --- apply_affinity: TEXT --------------------------------------------------
class TestApplyText:
    def test_integer_to_text(self) -> None:
        v = apply_affinity(Value.integer(42), Affinity.TEXT)
        assert v == Value.text("42")

    def test_real_to_text(self) -> None:
        v = apply_affinity(Value.real(3.14), Affinity.TEXT)
        assert v == Value.text("3.14")

    def test_zero_to_text(self) -> None:
        v = apply_affinity(Value.integer(0), Affinity.TEXT)
        assert v == Value.text("0")

    def test_text_unchanged(self) -> None:
        v = apply_affinity(Value.text("hello"), Affinity.TEXT)
        assert v == Value.text("hello")

    def test_null_unchanged(self) -> None:
        v = apply_affinity(Value.null(), Affinity.TEXT)
        assert v == Value.null()

    def test_blob_unchanged(self) -> None:
        v = apply_affinity(Value.blob(b"x"), Affinity.TEXT)
        assert v == Value.blob(b"x")


# --- apply_affinity: NUMERIC/INTEGER ---------------------------------------
class TestApplyNumeric:
    def test_text_integer_to_integer(self) -> None:
        v = apply_affinity(Value.text("42"), Affinity.NUMERIC)
        assert v == Value.integer(42)

    def test_text_real_to_real(self) -> None:
        v = apply_affinity(Value.text("3.14"), Affinity.NUMERIC)
        assert v == Value.real(3.14)

    def test_text_not_number_stays_text(self) -> None:
        v = apply_affinity(Value.text("hello"), Affinity.NUMERIC)
        assert v == Value.text("hello")

    def test_integer_unchanged(self) -> None:
        v = apply_affinity(Value.integer(42), Affinity.NUMERIC)
        assert v == Value.integer(42)

    def test_real_unchanged(self) -> None:
        v = apply_affinity(Value.real(3.14), Affinity.NUMERIC)
        assert v == Value.real(3.14)

    def test_null_unchanged(self) -> None:
        v = apply_affinity(Value.null(), Affinity.NUMERIC)
        assert v == Value.null()

    def test_blob_unchanged(self) -> None:
        v = apply_affinity(Value.blob(b"x"), Affinity.NUMERIC)
        assert v == Value.blob(b"x")

    def test_integer_affinity_same_as_numeric(self) -> None:
        # INTEGER affinity behaves like NUMERIC for storage.
        v = apply_affinity(Value.text("42"), Affinity.INTEGER)
        assert v == Value.integer(42)


# --- apply_affinity: REAL --------------------------------------------------
class TestApplyReal:
    def test_integer_to_real(self) -> None:
        v = apply_affinity(Value.integer(42), Affinity.REAL)
        assert v == Value.real(42.0)

    def test_text_integer_to_real(self) -> None:
        v = apply_affinity(Value.text("42"), Affinity.REAL)
        assert v == Value.real(42.0)

    def test_text_real_to_real(self) -> None:
        v = apply_affinity(Value.text("3.14"), Affinity.REAL)
        assert v == Value.real(3.14)

    def test_text_not_number_stays_text(self) -> None:
        v = apply_affinity(Value.text("hello"), Affinity.REAL)
        assert v == Value.text("hello")


# --- apply_affinity: BLOB (no conversion) ---------------------------------
class TestApplyBlob:
    def test_no_conversion(self) -> None:
        for v in [Value.integer(1), Value.text("x"), Value.real(1.0),
                  Value.null(), Value.blob(b"y")]:
            assert apply_affinity(v, Affinity.BLOB) == v