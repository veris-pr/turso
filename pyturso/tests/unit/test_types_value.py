"""Unit tests for pyturso.types.value — the tagged Value type.

Ports/verified against: core/types.rs Value, ValueType, Numeric.
"""

from __future__ import annotations

import pytest

from pyturso.types.value import StorageClass, Value


# --- constructors set the right storage class + payload --------------------
class TestConstructors:
    def test_null(self) -> None:
        v = Value.null()
        assert v.storage_class is StorageClass.NULL
        assert v.payload is None
        assert v.is_null

    def test_integer(self) -> None:
        v = Value.integer(42)
        assert v.storage_class is StorageClass.INTEGER
        assert v.payload == 42
        assert v.is_integer
        assert v.is_numeric

    def test_real(self) -> None:
        v = Value.real(3.14)
        assert v.storage_class is StorageClass.REAL
        assert v.payload == 3.14
        assert v.is_real
        assert v.is_numeric

    def test_text(self) -> None:
        v = Value.text("hello")
        assert v.storage_class is StorageClass.TEXT
        assert v.payload == "hello"
        assert v.is_text

    def test_blob(self) -> None:
        v = Value.blob(b"\x00\xff")
        assert v.storage_class is StorageClass.BLOB
        assert v.payload == b"\x00\xff"
        assert v.is_blob

    def test_negative_int(self) -> None:
        v = Value.integer(-1)
        assert v.payload == -1

    def test_zero_int(self) -> None:
        v = Value.integer(0)
        assert v.payload == 0
        assert v.is_integer

    def test_negative_zero_real(self) -> None:
        v = Value.real(-0.0)
        assert v.payload == -0.0
        assert v.is_real


# --- type_of / typeof -----------------------------------------------------
class TestTypeOf:
    def test_type_of_returns_storage_class(self) -> None:
        assert Value.null().type_of() is StorageClass.NULL
        assert Value.integer(1).type_of() is StorageClass.INTEGER
        assert Value.real(1.0).type_of() is StorageClass.REAL
        assert Value.text("x").type_of() is StorageClass.TEXT
        assert Value.blob(b"x").type_of() is StorageClass.BLOB

    def test_typeof_property(self) -> None:
        assert StorageClass.NULL.typeof == "null"
        assert StorageClass.INTEGER.typeof == "integer"
        assert StorageClass.REAL.typeof == "real"
        assert StorageClass.TEXT.typeof == "text"
        assert StorageClass.BLOB.typeof == "blob"


# --- equality (no cross-coercion) -----------------------------------------
class TestEquality:
    def test_same_class_same_value_equal(self) -> None:
        assert Value.integer(1) == Value.integer(1)
        assert Value.real(1.0) == Value.real(1.0)
        assert Value.text("a") == Value.text("a")
        assert Value.blob(b"x") == Value.blob(b"x")
        assert Value.null() == Value.null()

    def test_same_class_different_value_not_equal(self) -> None:
        assert Value.integer(1) != Value.integer(2)
        assert Value.real(1.0) != Value.real(2.0)
        assert Value.text("a") != Value.text("b")
        assert Value.blob(b"x") != Value.blob(b"y")

    def test_integer_not_equal_real_even_same_number(self) -> None:
        # The defining contract: no cross-coercion. 1 (int) != 1.0 (real).
        assert Value.integer(1) != Value.real(1.0)

    def test_text_not_equal_integer_even_if_numeric(self) -> None:
        assert Value.text("10") != Value.integer(10)

    def test_null_not_equal_anything(self) -> None:
        assert Value.null() != Value.integer(0)
        assert Value.null() != Value.text("")
        assert Value.null() != Value.blob(b"")

    def test_value_not_equal_non_value(self) -> None:
        assert Value.integer(1) != 1
        assert Value.text("x") != "x"


# --- hashing (for multiset/distinct) --------------------------------------
class TestHashing:
    def test_same_value_same_hash(self) -> None:
        assert hash(Value.integer(42)) == hash(Value.integer(42))
        assert hash(Value.text("hi")) == hash(Value.text("hi"))

    def test_different_storage_class_different_hash(self) -> None:
        # integer(1) and real(1.0) have different storage classes → different hash.
        assert hash(Value.integer(1)) != hash(Value.real(1.0))

    def test_hashable_in_set(self) -> None:
        s = {Value.integer(1), Value.integer(1), Value.text("1")}
        assert len(s) == 2


# --- immutability (frozen dataclass) --------------------------------------
class TestImmutability:
    def test_cannot_mutate_payload(self) -> None:
        v = Value.integer(42)
        with pytest.raises(Exception):  # FrozenInstanceError
            v.payload = 99  # type: ignore[misc]

    def test_cannot_mutate_storage_class(self) -> None:
        v = Value.integer(42)
        with pytest.raises(Exception):  # FrozenInstanceError
            v.storage_class = StorageClass.NULL  # type: ignore[misc]


# --- i64 boundary values (not enforced here, but representable) -----------
class TestI64Boundaries:
    def test_i64_max(self) -> None:
        v = Value.integer(2**63 - 1)
        assert v.payload == 2**63 - 1

    def test_i64_min(self) -> None:
        v = Value.integer(-(2**63))
        assert v.payload == -(2**63)

    def test_above_i64_representable_but_unchecked(self) -> None:
        # Python ints are unbounded; the Value type does not enforce i64.
        # The numeric module handles bounds at arithmetic/serialization time.
        v = Value.integer(2**64)
        assert v.payload == 2**64
        assert v.is_integer