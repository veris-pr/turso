"""insert — INSERT translation entry point.

Ports: core/translate/insert.rs.
Phase: 7
Status: IMPLEMENTED (simplified: INSERT INTO t VALUES (...) — single table,
no column list, no RETURNING, no conflict resolution).

Translates an INSERT statement into VDBE opcodes:
  Init → Transaction → OpenWrite → [for each row: evaluate values →
  MakeRecord → NewRowid/Rowid → Insert] → Halt
"""

from __future__ import annotations

from pyturso.errors import NotSupported, TursoError
from pyturso.parser.ast.stmt import Insert as InsertStmt
from pyturso.parser.parser import parse as parse_sql
from pyturso.schema.objects import Schema
from pyturso.translate.expr.compile import compile_expr
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.insn import (
    Halt, Init, Insert, Integer, MakeRecord, NewRowid, Null, OpenWrite,
    Transaction,
)
from pyturso.vdbe.program import Program

__all__ = ["translate_insert", "translate_dml"]


def translate_insert(sql: str, schema: Schema) -> Program:
    """Compile an INSERT statement into a VDBE Program."""
    ast = parse_sql(sql)
    if not isinstance(ast, InsertStmt):
        raise NotSupported(f"expected INSERT, got {type(ast).__name__}")

    table = schema.get_table(ast.table.value)
    if table is None:
        raise TursoError(f"no such table: {ast.table.value}")

    builder = ProgramBuilder()
    start = builder.alloc_label()
    builder.emit(Init(target_pc=-1), label=start)
    builder.resolve(start)
    builder.emit(Transaction())

    cursor_id = builder.alloc_cursor()
    builder.emit(OpenWrite(cursor_id=cursor_id, root_page=table.root_page))

    # Determine which columns to insert into.
    if ast.columns is not None:
        # Explicit column list — map to column indices.
        col_indices = []
        for col_name in ast.columns:
            idx = table.column_index(col_name.value)
            if idx is None:
                raise TursoError(f"no such column: {col_name.value}")
            col_indices.append(idx)
    else:
        # All columns in table order.
        col_indices = list(range(len(table.columns)))

    n_cols = len(col_indices)

    for value_row in ast.values:
        if len(value_row) != n_cols:
            raise TursoError(
                f"column count mismatch: table has {n_cols} columns, "
                f"values has {len(value_row)}"
            )

        # Allocate registers in TABLE column order (not insertion order).
        n_table_cols = len(table.columns)
        start_reg = builder.alloc_registers(n_table_cols)
        rowid_reg = builder.alloc_register()

        # Initialize all columns to NULL.
        for i in range(n_table_cols):
            builder.emit(Null(dest=start_reg + i))

        # Fill in the provided columns.
        for i, val_expr in enumerate(value_row):
            col_idx = col_indices[i]
            if col_idx == table.rowid_alias_col:
                _eval_simple(builder, val_expr, rowid_reg)
                # The record stores NULL for the alias column (already NULL).
            else:
                _eval_simple(builder, val_expr, start_reg + col_idx)

        # If no explicit rowid was set (alias column not in the values),
        # allocate a new one.
        if table.rowid_alias_col is not None and col_indices.count(table.rowid_alias_col) == 0:
            builder.emit(NewRowid(cursor_id=cursor_id, dest=rowid_reg))

        # Build the record from the value registers.
        record_reg = builder.alloc_register()
        builder.emit(MakeRecord(
            start_reg=start_reg, count=n_table_cols, dest=record_reg,
        ))

        # Insert the row.
        builder.emit(Insert(
            cursor_id=cursor_id,
            rowid_reg=rowid_reg,
            record_reg=record_reg,
        ))

    builder.emit(Halt())
    return builder.finalize(sql)


def _eval_simple(builder: ProgramBuilder, expr: object, dest: int) -> None:
    """Evaluate a simple literal expression into a register."""
    from pyturso.parser.ast.expr import LiteralExpr, Literal, IdExpr

    if isinstance(expr, LiteralExpr):
        if expr.literal is Literal.Null:
            builder.emit(Null(dest=dest))
        elif expr.literal is Literal.Numeric:
            try:
                builder.emit(Integer(int(expr.value), dest))
            except ValueError:
                from pyturso.vdbe.insn import Real
                builder.emit(Real(float(expr.value), dest))
        elif expr.literal is Literal.String:
            from pyturso.vdbe.insn import String8
            builder.emit(String8(expr.value, dest))
        elif expr.literal is Literal.Blob:
            from pyturso.vdbe.insn import String8
            builder.emit(String8(expr.value, dest))  # simplified
        else:
            builder.emit(Integer(0, dest))
    else:
        raise NotSupported(f"complex value expression not supported: {type(expr).__name__}")


def translate_dml(sql: str, schema: Schema) -> Program:
    """Compile any supported DML statement (Phase 7: INSERT only)."""
    return translate_insert(sql, schema)