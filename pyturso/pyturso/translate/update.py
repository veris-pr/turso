"""update — UPDATE translation entry point.

Ports: core/translate/update.rs.
Phase: 10
Status: IMPLEMENTED (simplified: UPDATE t SET col=expr WHERE ... — single
table, no subqueries in SET, no RETURNING).

Translates an UPDATE statement into VDBE opcodes:
  Init → Transaction → OpenWrite → Rewind → [WHERE test →
  evaluate SET expressions → Column writes → ... ] → Next → Halt

Phase 10 simplified: reads each column, applies the WHERE filter, evaluates
the SET expressions, and rewrites the row by inserting a new record with the
updated values. This is a simplified approach — it does a full row rewrite
(like SQLite's ephemeral table approach, but without the ephemeral table).
"""

from __future__ import annotations

from pyturso.errors import NotSupported, TursoError
from pyturso.parser.ast.stmt import Update as UpdateStmt
from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.ast.expr import (
    BinaryExpr, Expr, IdExpr, Literal, LiteralExpr, Operator,
    QualifiedExpr,
)
from pyturso.schema.objects import Schema, Table
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.insn import (
    Column, Copy, Halt, Init, Insert, Integer, MakeRecord, Null,
    OpenWrite, Rewind, Rowid, String8, Transaction, Next,
)
from pyturso.vdbe.program import Program

__all__ = ["translate_update"]


def translate_update(sql: str, schema: Schema) -> Program:
    """Compile an UPDATE statement into a VDBE program."""
    ast = parse_sql(sql)
    if not isinstance(ast, UpdateStmt):
        raise NotSupported(f"expected UPDATE, got {type(ast).__name__}")

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

    # Build a map: column_index → new_value_expr.
    set_map: dict[int, Expr] = {}
    for col_name, val_expr in ast.assignments:
        idx = table.column_index(col_name.value)
        if idx is None:
            raise TursoError(f"no such column: {col_name.value}")
        set_map[idx] = val_expr

    n_cols = len(table.columns)
    loop_start = builder.alloc_label()
    end = builder.alloc_label()

    builder.emit(Rewind(cursor_id=cursor_id, pc_if_empty=-1), label=end)
    builder.resolve(loop_start)

    # WHERE test (if present).
    if ast.where is not None:
        from pyturso.translate.emitter.select import _emit_where_term
        skip = builder.alloc_label()
        _emit_where_term(builder, ast.where, table, cursor_id, skip)

    # Read all columns into registers.
    start_reg = builder.alloc_registers(n_cols)
    rowid_reg = builder.alloc_register()

    for i, col in enumerate(table.columns):
        if i == table.rowid_alias_col:
            builder.emit(Rowid(cursor_id=cursor_id, dest=rowid_reg))
            builder.emit(Null(dest=start_reg + i))
        else:
            builder.emit(Column(cursor_id=cursor_id, column=i, dest=start_reg + i))

    # Apply SET expressions: overwrite the SET columns with new values.
    for col_idx, expr in set_map.items():
        _eval_set_expr(builder, expr, table, cursor_id, start_reg + col_idx)

    # Build the record and insert it.
    record_reg = builder.alloc_register()
    builder.emit(MakeRecord(start_reg=start_reg, count=n_cols, dest=record_reg))
    builder.emit(Insert(cursor_id=cursor_id, rowid_reg=rowid_reg, record_reg=record_reg))

    builder.emit(Next(cursor_id=cursor_id, pc_if_next=-1), label=loop_start)

    if ast.where is not None:
        builder.resolve(skip)
        builder.emit(Next(cursor_id=cursor_id, pc_if_next=-1), label=loop_start)

    builder.resolve(end)
    builder.emit(Halt())
    return builder.finalize(sql)


def _eval_set_expr(
    builder: ProgramBuilder, expr: Expr, table: Table,
    cursor_id: int, dest: int,
) -> None:
    """Evaluate a SET expression into a register."""
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
            builder.emit(String8(expr.value, dest))
        else:
            builder.emit(Integer(0, dest))
        return

    if isinstance(expr, IdExpr):
        # Column reference — read it.
        col_idx = table.column_index(expr.name.value)
        if col_idx is None:
            raise TursoError(f"no such column: {expr.name.value}")
        if col_idx == table.rowid_alias_col:
            builder.emit(Rowid(cursor_id=cursor_id, dest=dest))
        else:
            builder.emit(Column(cursor_id=cursor_id, column=col_idx, dest=dest))
        return

    # Complex expression — use the expr compiler.
    from pyturso.translate.expr.compile import compile_expr
    reg = compile_expr(builder, expr, cursor_id, table)
    builder.emit(Copy(src=reg, dest=dest))