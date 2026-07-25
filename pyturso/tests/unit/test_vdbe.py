"""Unit tests for pyturso.vdbe — builder, program, explain, execute.
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="attr-defined"
# mypy: disable-error-code="unused-ignore"

Hand-built programs (no SQL) test the VM directly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pyturso.io.driver import run_to_completion
from pyturso.io.memory import MemoryIO
from pyturso.io.protocol import WriteRequest
from pyturso.storage.pager import Pager
from pyturso.storage.sqlite3_ondisk import (
    cell_pointer_offsets, parse_page_header, parse_record,
    parse_table_leaf_cell,
)
from pyturso.storage.btree import BTreeCursor
from pyturso.types.value import Value
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.execute import execute
from pyturso.vdbe.explain import explain
from pyturso.vdbe.insn import (
    Column, Eq, Goto, Gt, Halt, Init, Integer, Le, Ne, Next, Null, OpenRead,
    ResultRow, Rewind, Rowid, String8, Transaction, UNRESOLVED,
)
from pyturso.vdbe.program import Program


def _find_t_root(pager: Pager) -> int:
    """Find the 't' table root page from sqlite_schema."""
    page1 = run_to_completion(pager.read_page(1))
    hdr = parse_page_header(page1, page_no=1)
    ptrs = cell_pointer_offsets(page1, hdr)
    for ptr in ptrs:
        cell = parse_table_leaf_cell(page1, ptr, pager.page_size)
        rec = parse_record(cell.payload)
        if rec.values[0] == "table" and rec.values[1] == "t":
            return rec.values[3]  # type: ignore[return-value]
    raise RuntimeError("table 't' not found")


@pytest.fixture
def db_pager(tmp_path: Path) -> Pager:
    db = tmp_path / "vdbe.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA page_size=4096")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO t VALUES (?,?)",
                     [(1, "alice"), (2, "bob"), (3, "carol")])
    conn.commit()
    conn.close()
    raw = db.read_bytes()
    io = MemoryIO()
    f = io.open_file("db")
    f.pwrite(WriteRequest(f, 0, raw))
    pager = Pager(io, "db")
    pager.open()
    return pager


# --- builder ---
class TestBuilder:
    def test_alloc_register(self) -> None:
        b = ProgramBuilder()
        assert b.alloc_register() == 1
        assert b.alloc_register() == 2
        assert b.n_registers == 3

    def test_alloc_registers(self) -> None:
        b = ProgramBuilder()
        assert b.alloc_registers(3) == 1
        assert b.n_registers == 4

    def test_alloc_cursor(self) -> None:
        b = ProgramBuilder()
        assert b.alloc_cursor() == 0
        assert b.n_cursors == 1

    def test_emit_returns_address(self) -> None:
        b = ProgramBuilder()
        assert b.emit(Halt()) == 0
        assert b.emit(Integer(1, 0)) == 1

    def test_label_backpatching(self) -> None:
        b = ProgramBuilder()
        target = b.alloc_label()
        b.emit(Init(target_pc=UNRESOLVED), label=target)
        b.emit(Halt())
        b.resolve(target)
        prog = b.finalize()
        assert prog.insns[0].target_pc == 2  # type: ignore[attr-defined]

    def test_unresolved_label_raises(self) -> None:
        b = ProgramBuilder()
        lbl = b.alloc_label()
        b.emit(Goto(target_pc=UNRESOLVED), label=lbl)
        with pytest.raises(AssertionError):
            b.finalize()

    def test_finalize(self) -> None:
        b = ProgramBuilder()
        b.emit(Init())
        b.emit(Halt())
        prog = b.finalize(sql="SELECT 1")
        assert isinstance(prog, Program)
        assert prog.sql == "SELECT 1"
        assert len(prog.insns) == 2


# --- explain ---
class TestExplain:
    def test_basic(self) -> None:
        b = ProgramBuilder()
        b.emit(Init())
        b.emit(Halt())
        listing = explain(b.finalize())
        assert "Init" in listing
        assert "Halt" in listing

    def test_all_instructions(self) -> None:
        b = ProgramBuilder()
        b.emit(Init())
        b.emit(Integer(42, 1))
        b.emit(Halt())
        lines = explain(b.finalize()).strip().split("\n")
        assert len(lines) == 3


# --- execute: hand-built programs ---
class TestExecute:
    def test_select_all(self, db_pager: Pager) -> None:
        t_root = _find_t_root(db_pager)
        b = ProgramBuilder()
        start = b.alloc_label()
        r_name = b.alloc_register()
        cur = b.alloc_cursor()

        b.emit(Init(target_pc=UNRESOLVED), label=start)
        b.resolve(start)
        b.emit(Transaction())
        b.emit(OpenRead(cursor_id=cur, root_page=t_root))
        loop = b.alloc_label()
        end = b.alloc_label()
        b.emit(Rewind(cursor_id=cur, pc_if_empty=UNRESOLVED), label=end)
        b.resolve(loop)
        b.emit(Column(cursor_id=cur, column=1, dest=r_name))
        b.emit(ResultRow(start_reg=r_name, count=1))
        b.emit(Next(cursor_id=cur, pc_if_next=UNRESOLVED), label=loop)
        b.resolve(end)
        b.emit(Halt())

        prog = b.finalize("SELECT name FROM t")
        state = execute(prog, db_pager)
        assert len(state.result_rows) == 3
        assert state.result_rows[0][0] == Value.text("alice")
        assert state.result_rows[1][0] == Value.text("bob")
        assert state.result_rows[2][0] == Value.text("carol")

    def test_select_where_gt(self, db_pager: Pager) -> None:
        """SELECT name FROM t WHERE id > 1 — uses Rowid for the alias column."""
        t_root = _find_t_root(db_pager)
        b = ProgramBuilder()
        start = b.alloc_label()
        r_id = b.alloc_register()
        r_name = b.alloc_register()
        r_one = b.alloc_register()
        cur = b.alloc_cursor()

        b.emit(Init(target_pc=UNRESOLVED), label=start)
        b.resolve(start)
        b.emit(Transaction())
        b.emit(Integer(1, r_one))
        b.emit(OpenRead(cursor_id=cur, root_page=t_root))
        loop = b.alloc_label()
        skip = b.alloc_label()
        end = b.alloc_label()
        b.emit(Rewind(cursor_id=cur, pc_if_empty=UNRESOLVED), label=end)
        b.resolve(loop)
        b.emit(Rowid(cursor_id=cur, dest=r_id))
        b.emit(Le(lhs=r_id, rhs=r_one, target_pc=UNRESOLVED), label=skip)
        b.emit(Column(cursor_id=cur, column=1, dest=r_name))
        b.emit(ResultRow(start_reg=r_name, count=1))
        b.emit(Next(cursor_id=cur, pc_if_next=UNRESOLVED), label=loop)
        b.resolve(skip)
        b.emit(Next(cursor_id=cur, pc_if_next=UNRESOLVED), label=loop)
        b.resolve(end)
        b.emit(Halt())

        prog = b.finalize("SELECT name FROM t WHERE id > 1")
        state = execute(prog, db_pager)
        assert len(state.result_rows) == 2
        assert state.result_rows[0][0] == Value.text("bob")
        assert state.result_rows[1][0] == Value.text("carol")

    def test_integer_and_string8(self, db_pager: Pager) -> None:
        b = ProgramBuilder()
        r1 = b.alloc_register()
        r2 = b.alloc_register()
        b.emit(Init())
        b.emit(Integer(42, r1))
        b.emit(String8("hello", r2))
        b.emit(ResultRow(start_reg=r1, count=2))
        b.emit(Halt())
        state = execute(b.finalize(), db_pager)
        assert state.result_rows[0][0] == Value.integer(42)
        assert state.result_rows[0][1] == Value.text("hello")

    def test_null(self, db_pager: Pager) -> None:
        b = ProgramBuilder()
        r1 = b.alloc_register()
        b.emit(Init())
        b.emit(Null(dest=r1))
        b.emit(ResultRow(start_reg=r1, count=1))
        b.emit(Halt())
        state = execute(b.finalize(), db_pager)
        assert state.result_rows[0][0] == Value.null()