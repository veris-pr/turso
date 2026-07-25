"""Unit tests for Phase 6 expanded: string batch 2, LIKE/GLOB, math, arithmetic.

Tests the expanded function registry and the VDBE arithmetic/function opcodes.
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="unused-ignore"

import sqlite3
from pathlib import Path

import pytest

from pyturso.functions.registry import call_function, registry
from pyturso.functions.like import like_match, glob_match
from pyturso.types.value import Value
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.execute import execute
from pyturso.vdbe.insn import (
    Add, Concat, Function, Halt, Init, Integer, Multiply, Null,
    ResultRow, String8, Subtract,
)
from pyturso.storage.pager import Pager
from pyturso.io.memory import MemoryIO


def _run_simple(build_fn) -> list[tuple[Value, ...]]:
    """Build and run a simple program without a DB."""
    b = ProgramBuilder()
    build_fn(b)
    prog = b.finalize()
    io = MemoryIO()
    io.open_file("dummy")
    pager = Pager(io, "dummy", page_size=4096)
    return execute(prog, pager).result_rows


# --- string batch 2 ---
class TestStringBatch2:
    def test_substr_2arg(self) -> None:
        assert call_function("substr", [Value.text("hello"), Value.integer(2)]) == Value.text("ello")

    def test_substr_3arg(self) -> None:
        assert call_function("substr", [Value.text("hello"), Value.integer(2), Value.integer(3)]) == Value.text("ell")

    def test_substr_negative(self) -> None:
        assert call_function("substr", [Value.text("hello"), Value.integer(-2)]) == Value.text("lo")

    def test_substr_null(self) -> None:
        assert call_function("substr", [Value.null(), Value.integer(1)]) == Value.null()

    def test_trim(self) -> None:
        assert call_function("trim", [Value.text("  hello  ")]) == Value.text("hello")

    def test_trim_chars(self) -> None:
        assert call_function("trim", [Value.text("xyhelloxy"), Value.text("xy")]) == Value.text("hello")

    def test_ltrim(self) -> None:
        assert call_function("ltrim", [Value.text("  hello  ")]) == Value.text("hello  ")

    def test_rtrim(self) -> None:
        assert call_function("rtrim", [Value.text("  hello  ")]) == Value.text("  hello")

    def test_replace(self) -> None:
        assert call_function("replace", [Value.text("abcabc"), Value.text("b"), Value.text("X")]) == Value.text("aXcaXc")

    def test_replace_empty_pattern(self) -> None:
        assert call_function("replace", [Value.text("abc"), Value.text(""), Value.text("X")]) == Value.text("abc")

    def test_instr_found(self) -> None:
        assert call_function("instr", [Value.text("hello"), Value.text("ll")]) == Value.integer(3)

    def test_instr_not_found(self) -> None:
        assert call_function("instr", [Value.text("hello"), Value.text("x")]) == Value.integer(0)

    def test_instr_empty(self) -> None:
        assert call_function("instr", [Value.text("hello"), Value.text("")]) == Value.integer(1)

    def test_quote_string(self) -> None:
        assert call_function("quote", [Value.text("it's")]) == Value.text("'it''s'")

    def test_quote_integer(self) -> None:
        assert call_function("quote", [Value.integer(42)]) == Value.text("42")

    def test_quote_null(self) -> None:
        assert call_function("quote", [Value.null()]) == Value.text("NULL")

    def test_char(self) -> None:
        assert call_function("char", [Value.integer(65), Value.integer(66)]) == Value.text("AB")

    def test_unicode(self) -> None:
        assert call_function("unicode", [Value.text("A")]) == Value.integer(65)


# --- LIKE/GLOB ---
class TestLikeGlob:
    def test_like_match_exact(self) -> None:
        assert like_match("hello", "hello")

    def test_like_match_percent(self) -> None:
        assert like_match("h%o", "hello")
        assert like_match("%", "anything")
        assert like_match("h%", "hello")

    def test_like_match_underscore(self) -> None:
        assert like_match("h_llo", "hello")
        assert not like_match("h_ll", "hello")

    def test_like_case_insensitive(self) -> None:
        assert like_match("HELLO", "hello")
        assert like_match("hello", "HELLO")

    def test_like_no_match(self) -> None:
        assert not like_match("h%o", "world")

    def test_like_function(self) -> None:
        assert call_function("like", [Value.text("hello"), Value.text("hello")]) == Value.integer(1)
        assert call_function("like", [Value.text("h%o"), Value.text("hello")]) == Value.integer(1)
        assert call_function("like", [Value.text("world"), Value.text("hello")]) == Value.integer(0)

    def test_glob_match(self) -> None:
        assert glob_match("hel*", "hello")
        assert glob_match("h?llo", "hello")
        assert not glob_match("h?llo", "world")

    def test_glob_function(self) -> None:
        assert call_function("glob", [Value.text("hel*"), Value.text("hello")]) == Value.integer(1)


# --- math functions expanded ---
class TestMathExpanded:
    def test_ceil(self) -> None:
        assert call_function("ceil", [Value.real(3.2)]) == Value.integer(4)

    def test_floor(self) -> None:
        assert call_function("floor", [Value.real(3.8)]) == Value.integer(3)

    def test_sign(self) -> None:
        assert call_function("sign", [Value.integer(5)]) == Value.integer(1)
        assert call_function("sign", [Value.integer(-5)]) == Value.integer(-1)
        assert call_function("sign", [Value.integer(0)]) == Value.integer(0)

    def test_sqrt(self) -> None:
        assert call_function("sqrt", [Value.real(16.0)]) == Value.real(4.0)

    def test_sqrt_negative_null(self) -> None:
        assert call_function("sqrt", [Value.real(-1.0)]) == Value.null()

    def test_pow(self) -> None:
        assert call_function("pow", [Value.integer(2), Value.integer(3)]) == Value.real(8.0)


# --- VDBE arithmetic + function tests ---
class TestVdbeArithmetic:
    def test_subtract(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2, r3 = b.alloc_register(), b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(Integer(20, r1))
            b.emit(Integer(5, r2))
            b.emit(Subtract(r1=r1, r2=r2, dest=r3))
            b.emit(ResultRow(start_reg=r3, count=1))
            b.emit(Halt())
        rows = _run_simple(build)
        assert rows[0][0] == Value.integer(15)

    def test_function_in_result(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2 = b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(String8("HELLO", r1))
            b.emit(Function(name="lower", start_reg=r1, n_args=1, dest=r2))
            b.emit(ResultRow(start_reg=r2, count=1))
            b.emit(Halt())
        rows = _run_simple(build)
        assert rows[0][0] == Value.text("hello")

    def test_nested_functions(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2, r3 = b.alloc_register(), b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(String8("hello", r1))
            b.emit(Function(name="upper", start_reg=r1, n_args=1, dest=r2))
            b.emit(Function(name="length", start_reg=r2, n_args=1, dest=r3))
            b.emit(ResultRow(start_reg=r3, count=1))
            b.emit(Halt())
        rows = _run_simple(build)
        assert rows[0][0] == Value.integer(5)  # length(upper("hello")) = length("HELLO") = 5