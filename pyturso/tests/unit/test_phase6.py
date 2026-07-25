"""Unit tests for Phase 6: functions, arithmetic, expression evaluation.

Tests the scalar function registry and the expanded expression compiler
(arithmetic, concat, function calls) through the VDBE executor.
"""

from __future__ import annotations
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="attr-defined"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="arg-type"

import sqlite3
from pathlib import Path

import pytest

from pyturso.functions.registry import call_function, registry
from pyturso.io.driver import run_to_completion
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.schema.load import load_schema_from_file
from pyturso.storage.pager import Pager
from pyturso.translate.select import translate_select
from pyturso.types.value import Value
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.execute import execute
from pyturso.vdbe.insn import (Null,
    Add, Column, Concat, Function, Halt, Init, Integer, Multiply, OpenRead,
    ResultRow, Rewind, Next, Rowid, String8, Transaction,
)


@pytest.fixture
def db_pager(tmp_path: Path) -> tuple[Pager, object]:
    db = tmp_path / "p6.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT, age INTEGER, score REAL)")
    conn.executemany("INSERT INTO t VALUES (?,?,?,?)",
                     [(1, "alice", 30, 95.5), (2, "bob", 25, 80.0), (3, "carol", 35, 88.3)])
    conn.commit()
    conn.close()
    schema = load_schema_from_file(str(db))
    raw = db.read_bytes()
    io = MemoryIO()
    f = io.open_file("db")
    f.pwrite(WriteRequest(f, 0, raw))
    pager = Pager(io, "db")
    pager.open()
    return pager, schema


# --- function registry ---
class TestFunctionRegistry:
    def test_length(self) -> None:
        assert call_function("length", [Value.text("hello")]) == Value.integer(5)
        assert call_function("LENGTH", [Value.text("")]) == Value.integer(0)

    def test_length_null(self) -> None:
        assert call_function("length", [Value.null()]) == Value.null()

    def test_length_blob(self) -> None:
        assert call_function("length", [Value.blob(b"\x00\xff")]) == Value.integer(2)

    def test_upper(self) -> None:
        assert call_function("upper", [Value.text("hello")]) == Value.text("HELLO")

    def test_lower(self) -> None:
        assert call_function("lower", [Value.text("HELLO")]) == Value.text("hello")

    def test_upper_null(self) -> None:
        assert call_function("upper", [Value.null()]) == Value.null()

    def test_abs(self) -> None:
        assert call_function("abs", [Value.integer(-5)]) == Value.integer(5)
        assert call_function("abs", [Value.integer(5)]) == Value.integer(5)
        assert call_function("abs", [Value.real(-3.14)]) == Value.real(3.14)

    def test_abs_null(self) -> None:
        assert call_function("abs", [Value.null()]) == Value.null()

    def test_abs_i64_min(self) -> None:
        # abs of i64 min → overflow to REAL.
        result = call_function("abs", [Value.integer(-(2**63))])
        assert result.is_real
        assert result.payload == float(2**63)

    def test_typeof(self) -> None:
        assert call_function("typeof", [Value.null()]) == Value.text("null")
        assert call_function("typeof", [Value.integer(1)]) == Value.text("integer")
        assert call_function("typeof", [Value.real(1.0)]) == Value.text("real")
        assert call_function("typeof", [Value.text("x")]) == Value.text("text")
        assert call_function("typeof", [Value.blob(b"x")]) == Value.text("blob")

    def test_coalesce(self) -> None:
        assert call_function("coalesce", [Value.null(), Value.integer(1)]) == Value.integer(1)
        assert call_function("coalesce", [Value.null(), Value.null(), Value.text("x")]) == Value.text("x")
        assert call_function("coalesce", [Value.null(), Value.null()]) == Value.null()

    def test_ifnull(self) -> None:
        assert call_function("ifnull", [Value.null(), Value.integer(42)]) == Value.integer(42)
        assert call_function("ifnull", [Value.integer(1), Value.integer(2)]) == Value.integer(1)

    def test_nullif(self) -> None:
        assert call_function("nullif", [Value.integer(1), Value.integer(1)]) == Value.null()
        assert call_function("nullif", [Value.integer(1), Value.integer(2)]) == Value.integer(1)

    def test_min_scalar(self) -> None:
        assert call_function("min", [Value.integer(3), Value.integer(1), Value.integer(2)]) == Value.integer(1)

    def test_max_scalar(self) -> None:
        assert call_function("max", [Value.integer(3), Value.integer(1), Value.integer(2)]) == Value.integer(3)

    def test_min_null(self) -> None:
        assert call_function("min", [Value.null(), Value.integer(1)]) == Value.null()

    def test_round(self) -> None:
        assert call_function("round", [Value.real(3.14159), Value.integer(2)]) == Value.real(3.14)
        assert call_function("round", [Value.real(2.5)]) == Value.integer(3)  # round half away from zero

    def test_hex(self) -> None:
        assert call_function("hex", [Value.blob(b"\x00\xff")]) == Value.text("00FF")
        assert call_function("hex", [Value.integer(255)]) == Value.text("FF")

    def test_no_such_function(self) -> None:
        with pytest.raises(ValueError):
            call_function("nonexistent", [Value.integer(1)])

    def test_case_insensitive(self) -> None:
        assert call_function("ABS", [Value.integer(-5)]) == Value.integer(5)
        assert call_function("Abs", [Value.integer(-5)]) == Value.integer(5)


# --- VDBE arithmetic opcodes ---
class TestArithmeticOpcodes:
    def _exec_simple(self, prog_fn) -> list[tuple[Value, ...]]:
        """Build and run a simple program (no DB needed)."""
        b = ProgramBuilder()
        prog_fn(b)
        prog = b.finalize()
        # Create a pager without opening (no header needed for non-cursor programs).
        from pyturso.io.memory import MemoryIO
        io = MemoryIO()
        io.open_file("dummy")  # create empty file
        pager = Pager(io, "dummy", page_size=4096)  # bypass header parse
        state = execute(prog, pager)
        return state.result_rows

    def test_add(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2, r3 = b.alloc_register(), b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(Integer(10, r1))
            b.emit(Integer(20, r2))
            b.emit(Add(r1=r1, r2=r2, dest=r3))
            b.emit(ResultRow(start_reg=r3, count=1))
            b.emit(Halt())
        rows = self._exec_simple(build)
        assert rows[0][0] == Value.integer(30)

    def test_multiply(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2, r3 = b.alloc_register(), b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(Integer(3, r1))
            b.emit(Integer(7, r2))
            b.emit(Multiply(r1=r1, r2=r2, dest=r3))
            b.emit(ResultRow(start_reg=r3, count=1))
            b.emit(Halt())
        rows = self._exec_simple(build)
        assert rows[0][0] == Value.integer(21)

    def test_concat(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2, r3 = b.alloc_register(), b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(String8("hello", r1))
            b.emit(String8(" world", r2))
            b.emit(Concat(r1=r1, r2=r2, dest=r3))
            b.emit(ResultRow(start_reg=r3, count=1))
            b.emit(Halt())
        rows = self._exec_simple(build)
        assert rows[0][0] == Value.text("hello world")

    def test_function_opcode(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2 = b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(String8("hello", r1))
            b.emit(Function(name="length", start_reg=r1, n_args=1, dest=r2))
            b.emit(ResultRow(start_reg=r2, count=1))
            b.emit(Halt())
        rows = self._exec_simple(build)
        assert rows[0][0] == Value.integer(5)

    def test_arithmetic_null_propagation(self) -> None:
        def build(b: ProgramBuilder) -> None:
            r1, r2, r3 = b.alloc_register(), b.alloc_register(), b.alloc_register()
            b.emit(Init())
            b.emit(Integer(10, r1))
            b.emit(Null(dest=r2))
            b.emit(Add(r1=r1, r2=r2, dest=r3))
            b.emit(ResultRow(start_reg=r3, count=1))
            b.emit(Halt())
        rows = self._exec_simple(build)
        assert rows[0][0] == Value.null()