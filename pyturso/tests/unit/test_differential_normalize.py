"""Unit tests for tests.differential.normalize — canonical row rendering.

Verified against: tests/differential/README.md normalization rules (NULL
literal, %.15g floats, blobs hex, errors by class) and the tursodb float
divergence documented in core/numeric/mod.rs format_float.

The defining property under test: normalization is IDEMPOTENT on canonical
input (so the harness applies it uniformly to every engine) and reconciles
tursodb's native text to canonical.
"""

from __future__ import annotations

from tests.differential.engine import Rows, render_cell
from tests.differential.normalize import (
    CANONICAL_NULL,
    FLOAT_FORMAT,
    normalize_cell,
    normalize_result,
    normalize_results,
    normalize_rows,
)

#: For float tests, the canonical format is a single source of truth: both
#: render_cell (type-aware) and normalize_cell (text) must produce it.
CANONICAL = FLOAT_FORMAT


# --- NULL: tursodb empty cell → canonical "NULL" ---------------------------
class TestNull:
    def test_empty_becomes_null(self) -> None:
        assert normalize_cell("") == CANONICAL_NULL

    def test_null_literal_is_stable(self) -> None:
        # Idempotent: canonical "NULL" stays "NULL".
        assert normalize_cell("NULL") == CANONICAL_NULL


# --- float reconciliation: tursodb format → %.15g canonical ----------------
class TestFloat:
    def test_plain_float_idempotent(self) -> None:
        assert normalize_cell("1.5") == "1.5"

    def test_matches_render_cell_for_typed_float(self) -> None:
        # The whole point: a type-aware engine's canonical float and a
        # normalized text float agree.
        for v in (1.5, -0.5, 0.0, 3.14, 1.0 / 3.0, 1e20, 1e-20, 123456.789):
            assert normalize_cell(CANONICAL % v) == render_cell(v)

    def test_tursodb_divergent_format_reconciled(self) -> None:
        # tursodb's format_float(1e20) → "1.00000000000000e+20"; canonical %.15g
        # → "1e+20". normalize must reconcile the former to the latter.
        assert normalize_cell("1.00000000000000e+20") == "1e+20"

    def test_float_with_trailing_zeros_normalized(self) -> None:
        # "1.00000000000000" parses to 1.0 → %.15g → "1".
        assert normalize_cell("1.00000000000000") == "1"

    def test_scientific_lowercase_e(self) -> None:
        assert normalize_cell("1e20") == "1e+20"


# --- integers: never float-normalized (precision preserved) ----------------
class TestInteger:
    def test_small_int_verbatim(self) -> None:
        assert normalize_cell("42") == "42"

    def test_negative_int_verbatim(self) -> None:
        assert normalize_cell("-7") == "-7"

    def test_int64_max_precision_preserved(self) -> None:
        # A float round-trip would destroy int64 precision: must stay verbatim
        # because there is no '.'/e mark to trigger the float path.
        assert normalize_cell("9223372036854775807") == "9223372036854775807"

    def test_leading_zeros_text_preserved(self) -> None:
        # Text "007" must NOT become int 7 (the typed-row trap): no float mark
        # → verbatim.
        assert normalize_cell("007") == "007"


# --- text / blob: verbatim -------------------------------------------------
class TestTextAndBlob:
    def test_text_verbatim(self) -> None:
        assert normalize_cell("hello") == "hello"

    def test_blob_hex_verbatim(self) -> None:
        # Type-aware engines already render x'<hex>'; normalize keeps it.
        assert normalize_cell("x'00ff'") == "x'00ff'"

    def test_blob_with_e_byte_not_misread_as_float(self) -> None:
        # "x'abef'" contains 'e' but is not a float: try/except keeps it.
        assert normalize_cell("x'abef'") == "x'abef'"


# --- row / result / list shapes -------------------------------------------
class TestShapes:
    def test_normalize_rows_preserves_shape(self) -> None:
        rows: Rows = [("1", ""), ("x", "1.5")]
        assert normalize_rows(rows) == [("1", "NULL"), ("x", "1.5")]

    def test_normalize_rows_empty(self) -> None:
        assert normalize_rows([]) == []

    def test_normalize_result_passes_error_class_through(self) -> None:
        # Errors are comparison classes already; normalization must not touch.
        assert normalize_result("OperationalError") == "OperationalError"

    def test_normalize_result_normalizes_rows(self) -> None:
        rows: Rows = [("1", "")]
        assert normalize_result(rows) == [("1", "NULL")]

    def test_normalize_results_mixed_list(self) -> None:
        out = normalize_results(
            [[("1", "")], "IntegrityError", [("1.5",)], []]
        )
        # Annotate to satisfy invariant list typing.
        assert out == [[("1", "NULL")], "IntegrityError", [("1.5",)], []]


# --- idempotency (the defining harness property) --------------------------
class TestIdempotency:
    def test_double_normalize_equals_single(self) -> None:
        cells = ["", "NULL", "1", "1.5", "1e20", "1.00000000000000e+20",
                 "9223372036854775807", "hello", "x'00ff'", "007", "-3.0"]
        for c in cells:
            once = normalize_cell(c)
            twice = normalize_cell(once)
            assert once == twice, f"not idempotent for {c!r}: {once!r} → {twice!r}"

    def test_canonical_engine_output_is_fixed_point(self) -> None:
        # Whatever render_cell (sqlite3/pyturso) produces, normalize leaves it.
        for v in (None, 1, 1.5, "hi", b"\x00\xff", 1.0 / 3.0, 1e20):
            rendered = render_cell(v)
            assert normalize_cell(rendered) == rendered
