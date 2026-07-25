"""Unit tests for pyturso.errors — hierarchy, messages, comparison-class map.

Ports/verified against: core/error.rs.
"""

from __future__ import annotations

import pytest

import pyturso.errors as errors
from pyturso.errors import (
    COMPARISON_CLASSES,
    ERROR_CLASS,
    TursoError,
    comparison_class,
)

# The concrete public error classes exported from pyturso.errors (excluding the
# base TursoError itself and the non-class symbols).
# The concrete public error classes exported from pyturso.errors: subclasses of
# TursoError that are not the base itself and not private helper bases
# (underscore-prefixed). Private bases like `_FixedTursoError` are not leaves
# and are intentionally absent from ERROR_CLASS.
_PUBLIC_ERROR_CLASSES = [
    obj
    for name, obj in vars(errors).items()
    if not name.startswith("_")
    and isinstance(obj, type)
    and issubclass(obj, TursoError)
    and obj is not TursoError
]


# --- hierarchy shape -------------------------------------------------------
class TestHierarchy:
    def test_turso_error_is_exception(self) -> None:
        assert issubclass(TursoError, Exception)

    @pytest.mark.parametrize("cls", _PUBLIC_ERROR_CLASSES)
    def test_every_exported_error_subclasses_turso_error(self, cls: type) -> None:
        assert issubclass(cls, TursoError), f"{cls.__name__} must subclass TursoError"

    def test_constraint_subclasses_are_distinct_classes(self) -> None:
        # Spot-check a few names exist and are classes (mirrors Rust variants).
        for name in (
            "Corrupt",
            "NotADB",
            "ParseError",
            "Constraint",
            "ForeignKeyConstraint",
            "Busy",
            "NotSupported",
            "OutOfMemory",
            "ShortRead",
            "ChecksumMismatch",
        ):
            cls = getattr(errors, name)
            assert isinstance(cls, type) and issubclass(cls, TursoError)


# --- message rendering (ports Rust #[error("...")] templates) --------------
class TestMessages:
    def test_payload_error_wraps_detail(self) -> None:
        err = errors.Corrupt("bad page 3")
        assert str(err) == "Corrupt database: bad page 3"
        assert err.detail == "bad page 3"

    def test_fixed_message_error_ignores_detail(self) -> None:
        assert str(errors.NotADB()) == "File is not a database"
        assert str(errors.Busy()) == "Database is busy"
        assert str(errors.IntegerOverflow()) == "Runtime error: integer overflow"
        assert str(errors.OutOfMemory()) == "Out of memory"

    def test_raise_carries_resolve_type_and_message(self) -> None:
        err = errors.Raise("ROLLBACK", "boom")
        assert err.resolve_type == "ROLLBACK"
        assert str(err) == "Runtime error: boom"

    def test_statements_in_progress_wraps_op(self) -> None:
        assert str(errors.StatementsInProgress("COMMIT")) == (
            "COMMIT - SQL statements in progress"
        )

    def test_invalid_blob_size_renders_expected(self) -> None:
        assert str(errors.InvalidBlobSize(12)) == "Invalid blob size, expected 12"

    def test_unsupported_encoding_template(self) -> None:
        assert str(errors.UnsupportedEncoding("latin-1")) == (
            "Unsupported text encoding: latin-1. Only UTF-8 is supported."
        )

    def test_short_read_structured_fields_and_message(self) -> None:
        err = errors.ShortRead(page_idx=2, expected=4096, actual=10)
        assert (err.page_idx, err.expected, err.actual) == (2, 4096, 10)
        assert str(err) == (
            "I/O error: short read on page 2: expected 4096 bytes, got 10"
        )

    def test_checksum_mismatch_message(self) -> None:
        err = errors.ChecksumMismatch(page_id=5, expected=111, actual=222)
        assert str(err) == "Checksum mismatch on page 5: expected 111, got 222"

    def test_io_completion_error_renders_op_and_kind(self) -> None:
        err = errors.IoCompletionError("NotFound", "open")
        assert err.error_kind == "NotFound"
        assert err.op == "open"
        assert str(err) == "I/O error (open): NotFound"


# --- corrupt-input idiom: engine code must raise, never return garbage -----
class TestCorruptInputRaises:
    def test_corrupt_is_catchable_as_turso_error(self) -> None:
        with pytest.raises(TursoError):
            raise errors.Corrupt("truncated header")

    def test_corrupt_class_identity_preserved(self) -> None:
        with pytest.raises(errors.Corrupt):
            raise errors.Corrupt("truncated header")


# --- comparison-class mapping table ---------------------------------------
class TestComparisonClassMap:
    @pytest.mark.parametrize("cls", _PUBLIC_ERROR_CLASSES)
    def test_every_error_class_is_mapped(self, cls: type) -> None:
        assert cls in ERROR_CLASS, f"{cls.__name__} missing from ERROR_CLASS"

    @pytest.mark.parametrize("cls", _PUBLIC_ERROR_CLASSES)
    def test_mapped_value_is_a_known_comparison_class(self, cls: type) -> None:
        assert ERROR_CLASS[cls] in COMPARISON_CLASSES, cls.__name__

    def test_parse_errors_are_operational(self) -> None:
        # sqlite3 reports syntax errors as OperationalError, not ProgrammingError.
        assert comparison_class(errors.ParseError("x")) == errors.OPERATIONAL_ERROR
        assert comparison_class(errors.LexerError("x")) == errors.OPERATIONAL_ERROR

    def test_constraints_are_integrity(self) -> None:
        assert comparison_class(errors.Constraint("x")) == errors.INTEGRITY_ERROR
        assert (
            comparison_class(errors.ForeignKeyConstraint("x"))
            == errors.INTEGRITY_ERROR
        )
        assert comparison_class(errors.Raise("ABORT", "x")) == errors.INTEGRITY_ERROR

    def test_corrupt_is_database_error(self) -> None:
        assert comparison_class(errors.Corrupt("x")) == errors.DATABASE_ERROR

    def test_busy_is_operational(self) -> None:
        assert comparison_class(errors.Busy()) == errors.OPERATIONAL_ERROR

    def test_not_supported_class(self) -> None:
        assert comparison_class(errors.NotSupported("window funcs")) == (
            errors.NOT_SUPPORTED_ERROR
        )

    def test_internal_error_class(self) -> None:
        assert comparison_class(errors.InternalError("x")) == errors.INTERNAL_ERROR

    def test_helper_falls_back_for_unknown_exception(self) -> None:
        # An unmapped exception must not crash the harness.
        assert comparison_class(RuntimeError("boom")) == errors.OPERATIONAL_ERROR

    def test_helper_walks_mro_for_unregistered_subclass(self) -> None:
        class MyConstraint(errors.Constraint):
            pass

        assert comparison_class(MyConstraint("x")) == errors.INTEGRITY_ERROR

    def test_completion_errors_resolve_to_operational(self) -> None:
        err = errors.ShortRead(page_idx=1, expected=10, actual=2)
        assert comparison_class(err) == errors.OPERATIONAL_ERROR
