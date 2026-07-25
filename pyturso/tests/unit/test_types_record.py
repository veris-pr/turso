"""Unit tests for pyturso.types.record — record build/parse round-trip.

Ports/verified against: core/types.rs Record build/parse. Tests round-trip
build(parse(build(values))) == values for every storage class and mixed records.
"""

from __future__ import annotations

import pytest

from pyturso.types.record import Record, build_record, parse_record
from pyturso.types.value import StorageClass, Value


class TestBuildParseRoundTrip:
    def test_single_integer(self) -> None:
        values = [Value.integer(42)]
        rec = build_record(values)
        parsed = parse_record(rec)
        assert len(parsed) == 1
        assert parsed[0] == Value.integer(42)

    def test_all_storage_classes(self) -> None:
        values = [
            Value.null(),
            Value.integer(0),      # const 0
            Value.integer(1),      # const 1
            Value.integer(127),    # i8
            Value.integer(2**63 - 1),  # i64
            Value.real(3.14),
            Value.text("hello"),
            Value.blob(b"\x00\xff"),
        ]
        rec = build_record(values)
        parsed = parse_record(rec)
        assert len(parsed) == len(values)
        for orig, got in zip(values, parsed.values):
            assert got == orig, f"{orig} != {got}"

    def test_empty_record(self) -> None:
        rec = build_record([])
        parsed = parse_record(rec)
        assert len(parsed) == 0

    def test_single_null(self) -> None:
        rec = build_record([Value.null()])
        parsed = parse_record(rec)
        assert parsed[0] == Value.null()

    def test_multiple_integers(self) -> None:
        values = [Value.integer(i) for i in range(-5, 6)]
        rec = build_record(values)
        parsed = parse_record(rec)
        for orig, got in zip(values, parsed.values):
            assert got == orig

    def test_text_and_blob_mix(self) -> None:
        values = [Value.text("a"), Value.blob(b"b"), Value.text("c")]
        rec = build_record(values)
        parsed = parse_record(rec)
        assert parsed[0] == Value.text("a")
        assert parsed[1] == Value.blob(b"b")
        assert parsed[2] == Value.text("c")

    def test_record_equality(self) -> None:
        r1 = Record([Value.integer(1), Value.text("x")])
        r2 = Record([Value.integer(1), Value.text("x")])
        r3 = Record([Value.integer(2), Value.text("x")])
        assert r1 == r2
        assert r1 != r3

    def test_record_indexing(self) -> None:
        r = Record([Value.integer(1), Value.text("hi")])
        assert r[0] == Value.integer(1)
        assert r[1] == Value.text("hi")
        assert len(r) == 2

    def test_build_then_parse_then_build_idempotent(self) -> None:
        values = [Value.integer(42), Value.text("hello"), Value.real(3.14)]
        rec1 = build_record(values)
        parsed = parse_record(rec1)
        rec2 = build_record(parsed.values)
        assert rec1 == rec2

    def test_large_text(self) -> None:
        values = [Value.text("x" * 1000)]
        rec = build_record(values)
        parsed = parse_record(rec)
        assert parsed[0] == Value.text("x" * 1000)

    def test_i64_boundaries(self) -> None:
        for i in (2**63 - 1, -(2**63), 0, 1, -1):
            rec = build_record([Value.integer(i)])
            parsed = parse_record(rec)
            assert parsed[0] == Value.integer(i)