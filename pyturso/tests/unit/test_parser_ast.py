"""Unit tests for pyturso.parser.ast — AST node dataclasses.

Verifies nodes are frozen, constructable, and equal by value (snapshot test
stability). No parsing here — the parser tests exercise construction.
"""

from __future__ import annotations

import pytest

from pyturso.parser.ast.expr import (
    BinaryExpr, IdExpr, Literal, LiteralExpr, Name, Operator,
    UnaryExpr, UnaryOperator, ParenExpr,
)
from pyturso.parser.ast.stmt import (
    As, Distinctness, FromClause, Limit, OneSelect, ResultColumn,
    Select, SelectBody, SelectTable, SortedColumn, SortOrder,
    Insert, Update, Delete, Begin, Commit, Rollback,
)
from pyturso.parser.ast.ddl import (
    ColumnConstraint, ColumnDefinition, CreateTable, CreateIndex,
)


# --- expr nodes ---
class TestExprNodes:
    def test_literal_null(self) -> None:
        e = LiteralExpr(Literal.Null)
        assert e.literal is Literal.Null
        assert e.value == ""

    def test_id(self) -> None:
        e = IdExpr(Name("col"))
        assert e.name.value == "col"

    def test_binary(self) -> None:
        e = BinaryExpr(IdExpr(Name("a")), Operator.Equals, IdExpr(Name("b")))
        assert e.op is Operator.Equals

    def test_unary(self) -> None:
        e = UnaryExpr(UnaryOperator.Negative, IdExpr(Name("x")))
        assert e.op is UnaryOperator.Negative

    def test_paren(self) -> None:
        e = ParenExpr(IdExpr(Name("x")))
        inner = e.inner
        assert isinstance(inner, IdExpr)
        assert inner.name.value == "x"

    def test_frozen(self) -> None:
        e = IdExpr(Name("x"))
        with pytest.raises(Exception):
            e.name = Name("y")  # type: ignore[misc]

    def test_equality(self) -> None:
        assert IdExpr(Name("a")) == IdExpr(Name("a"))
        assert IdExpr(Name("a")) != IdExpr(Name("b"))


# --- stmt nodes ---
class TestStmtNodes:
    def test_select_star(self) -> None:
        sel = Select(
            body=SelectBody(
                select=OneSelect(
                    columns=[ResultColumn(star=True)],
                    from_clause=FromClause(table=SelectTable(name=Name("t"))),
                ),
            ),
        )
        assert sel.body.select.columns[0].star
        fc = sel.body.select.from_clause
        assert fc is not None and fc.table is not None
        assert fc.table.name is not None
        assert fc.table.name.value == "t"

    def test_select_with_where(self) -> None:
        sel = Select(
            body=SelectBody(
                select=OneSelect(
                    columns=[ResultColumn(expr=IdExpr(Name("a")))],
                    from_clause=FromClause(table=SelectTable(name=Name("t"))),
                    where=BinaryExpr(IdExpr(Name("b")), Operator.Greater,
                                     LiteralExpr(Literal.Numeric, "1")),
                ),
            ),
        )
        assert sel.body.select.where is not None

    def test_insert(self) -> None:
        ins = Insert(
            table=Name("t"),
            values=[[LiteralExpr(Literal.Numeric, "1"), LiteralExpr(Literal.String, "x")]],
        )
        assert ins.table.value == "t"
        assert len(ins.values) == 1

    def test_update(self) -> None:
        upd = Update(
            table=Name("t"),
            assignments=[(Name("x"), LiteralExpr(Literal.Numeric, "1"))],
        )
        assert len(upd.assignments) == 1

    def test_delete(self) -> None:
        dele = Delete(table=Name("t"))
        assert dele.where is None

    def test_begin_commit_rollback(self) -> None:
        assert Begin().tx_type == "DEFERRED"
        assert Commit()
        assert Rollback()


# --- ddl nodes ---
class TestDDLNodes:
    def test_create_table(self) -> None:
        ct = CreateTable(
            table=Name("t"),
            columns=[
                ColumnDefinition(Name("id"), [
                    ColumnConstraint("PRIMARY KEY", autoincrement=True)
                ], "INTEGER"),
                ColumnDefinition(Name("name"), [
                    ColumnConstraint("NOT NULL")
                ], "TEXT"),
            ],
            table_constraints=[],
        )
        assert ct.table.value == "t"
        assert len(ct.columns) == 2
        assert ct.columns[0].constraints[0].autoincrement

    def test_create_index(self) -> None:
        ci = CreateIndex(
            index=Name("idx_x"),
            table=Name("t"),
            columns=[Name("x")],
        )
        assert not ci.unique
        assert ci.columns[0].value == "x"