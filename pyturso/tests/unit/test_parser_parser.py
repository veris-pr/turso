"""Unit tests for pyturso.parser.parser — recursive descent + precedence.

Ports/verified against: sqlite/parser/src/parser.rs. Snapshot-style: parse
SQL, assert the AST structure matches expectations.
"""

from __future__ import annotations

import pytest

from pyturso.parser.parser import parse
from pyturso.parser.errors import ParseError
from pyturso.parser.ast.expr import (
    BinaryExpr, IdExpr, Literal, LiteralExpr, Name, Operator,
    ParenExpr, QualifiedExpr, UnaryExpr, UnaryOperator,
)
from pyturso.parser.ast.stmt import (
    Select, SelectBody, OneSelect, ResultColumn, FromClause,
    SelectTable, SortedColumn, SortOrder, Limit, Insert, Update, Delete,
    Begin, Commit, Rollback, Distinctness,
)
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="index"
# mypy: disable-error-code="arg-type"
# mypy: disable-error-code="misc"
from pyturso.parser.ast.ddl import (
    CreateTable, CreateIndex, ColumnDefinition, ColumnConstraint,
)


# --- SELECT: basic ---
class TestSelectBasic:
    def test_select_star(self) -> None:
        s = parse("SELECT * FROM t")
        assert isinstance(s, Select)
        cols = s.body.select.columns
        assert len(cols) == 1 and cols[0].star
        assert s.body.select.from_clause.table.name.value == "t"

    def test_select_one_col(self) -> None:
        s = parse("SELECT a FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, IdExpr)
        assert col.expr.name.value == "a"

    def test_select_multiple_cols(self) -> None:
        s = parse("SELECT a, b, c FROM t")
        assert len(s.body.select.columns) == 3

    def test_select_with_alias(self) -> None:
        s = parse("SELECT a AS x FROM t")
        assert s.body.select.columns[0].alias.name.value == "x"

    def test_select_implicit_alias(self) -> None:
        s = parse("SELECT a x FROM t")
        assert s.body.select.columns[0].alias.name.value == "x"
        assert not s.body.select.columns[0].alias.has_as_keyword

    def test_select_distinct(self) -> None:
        s = parse("SELECT DISTINCT a FROM t")
        assert s.body.select.distinctness is Distinctness.Distinct

    def test_select_all(self) -> None:
        s = parse("SELECT ALL a FROM t")
        assert s.body.select.distinctness is Distinctness.All

    def test_select_table_star(self) -> None:
        s = parse("SELECT t.* FROM t")
        col = s.body.select.columns[0]
        assert col.table_star is not None
        assert col.table_star.value == "t"

    def test_select_where(self) -> None:
        s = parse("SELECT a FROM t WHERE b > 1")
        w = s.body.select.where
        assert isinstance(w, BinaryExpr)
        assert w.op is Operator.Greater

    def test_select_order_by(self) -> None:
        s = parse("SELECT a FROM t ORDER BY a")
        assert s.order_by is not None
        assert len(s.order_by) == 1

    def test_select_order_by_desc(self) -> None:
        s = parse("SELECT a FROM t ORDER BY a DESC")
        assert s.order_by[0].order is SortOrder.Desc

    def test_select_order_by_multiple(self) -> None:
        s = parse("SELECT a FROM t ORDER BY a ASC, b DESC")
        assert len(s.order_by) == 2
        assert s.order_by[0].order is SortOrder.Asc
        assert s.order_by[1].order is SortOrder.Desc

    def test_select_limit(self) -> None:
        s = parse("SELECT a FROM t LIMIT 10")
        assert s.limit is not None
        assert isinstance(s.limit.count, LiteralExpr)

    def test_select_limit_offset(self) -> None:
        s = parse("SELECT a FROM t LIMIT 10 OFFSET 5")
        assert s.limit.offset is not None

    def test_table_alias(self) -> None:
        s = parse("SELECT a FROM t AS x")
        assert s.body.select.from_clause.table.alias.value == "x"

    def test_implicit_table_alias(self) -> None:
        s = parse("SELECT a FROM t x")
        assert s.body.select.from_clause.table.alias.value == "x"


# --- expressions: precedence ---
class TestExprPrecedence:
    def test_addition_left_assoc(self) -> None:
        s = parse("SELECT 1 + 2 + 3 FROM t")
        col = s.body.select.columns[0]
        # (1 + 2) + 3 — left-associative
        assert isinstance(col.expr, BinaryExpr)
        assert col.expr.op is Operator.Add
        assert isinstance(col.expr.left, BinaryExpr)

    def test_multiply_binds_tighter_than_add(self) -> None:
        s = parse("SELECT 1 + 2 * 3 FROM t")
        col = s.body.select.columns[0]
        # 1 + (2 * 3)
        assert isinstance(col.expr, BinaryExpr)
        assert col.expr.op is Operator.Add
        assert isinstance(col.expr.right, BinaryExpr)
        assert col.expr.right.op is Operator.Multiply

    def test_or_binds_looser_than_and(self) -> None:
        s = parse("SELECT 1 OR 2 AND 3 FROM t")
        col = s.body.select.columns[0]
        # 1 OR (2 AND 3)
        assert isinstance(col.expr, BinaryExpr)
        assert col.expr.op is Operator.Or
        assert isinstance(col.expr.right, BinaryExpr)
        assert col.expr.right.op is Operator.And

    def test_parentheses_override_precedence(self) -> None:
        s = parse("SELECT (1 + 2) * 3 FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, BinaryExpr)
        assert col.expr.op is Operator.Multiply
        assert isinstance(col.expr.left, ParenExpr)

    def test_comparison(self) -> None:
        s = parse("SELECT a = b FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, BinaryExpr)
        assert col.expr.op is Operator.Equals

    def test_unary_minus(self) -> None:
        s = parse("SELECT -a FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, UnaryExpr)
        assert col.expr.op is UnaryOperator.Negative

    def test_not(self) -> None:
        s = parse("SELECT NOT a FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, UnaryExpr)
        assert col.expr.op is UnaryOperator.Not

    def test_string_literal(self) -> None:
        s = parse("SELECT 'hello' FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, LiteralExpr)
        assert col.expr.literal is Literal.String
        assert col.expr.value == "hello"

    def test_integer_literal(self) -> None:
        s = parse("SELECT 42 FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, LiteralExpr)
        assert col.expr.literal is Literal.Numeric

    def test_null_literal(self) -> None:
        s = parse("SELECT NULL FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, LiteralExpr)
        assert col.expr.literal is Literal.Null

    def test_qualified_column(self) -> None:
        s = parse("SELECT t.a FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, QualifiedExpr)

    def test_concat(self) -> None:
        s = parse("SELECT 'a' || 'b' FROM t")
        col = s.body.select.columns[0]
        assert isinstance(col.expr, BinaryExpr)
        assert col.expr.op is Operator.Concat


# --- INSERT ---
class TestInsert:
    def test_basic_insert(self) -> None:
        stmt = parse("INSERT INTO t VALUES (1, 'x')")
        assert isinstance(stmt, Insert)
        assert stmt.table.value == "t"
        assert len(stmt.values) == 1
        assert len(stmt.values[0]) == 2

    def test_insert_with_columns(self) -> None:
        stmt = parse("INSERT INTO t (a, b) VALUES (1, 2)")
        assert stmt.columns is not None
        assert len(stmt.columns) == 2

    def test_insert_multiple_rows(self) -> None:
        stmt = parse("INSERT INTO t VALUES (1), (2), (3)")
        assert len(stmt.values) == 3

    def test_insert_or_replace(self) -> None:
        stmt = parse("INSERT OR REPLACE INTO t VALUES (1)")
        assert stmt.or_action == "REPLACE"


# --- UPDATE ---
class TestUpdate:
    def test_basic_update(self) -> None:
        stmt = parse("UPDATE t SET x = 1")
        assert isinstance(stmt, Update)
        assert stmt.table.value == "t"
        assert len(stmt.assignments) == 1

    def test_update_where(self) -> None:
        stmt = parse("UPDATE t SET x = 1 WHERE id = 5")
        assert stmt.where is not None

    def test_update_multiple(self) -> None:
        stmt = parse("UPDATE t SET x = 1, y = 2")
        assert len(stmt.assignments) == 2


# --- DELETE ---
class TestDelete:
    def test_basic_delete(self) -> None:
        stmt = parse("DELETE FROM t")
        assert isinstance(stmt, Delete)
        assert stmt.table.value == "t"

    def test_delete_where(self) -> None:
        stmt = parse("DELETE FROM t WHERE id = 5")
        assert stmt.where is not None


# --- CREATE TABLE ---
class TestCreateTable:
    def test_basic(self) -> None:
        stmt = parse("CREATE TABLE t (x INTEGER, y TEXT)")
        assert isinstance(stmt, CreateTable)
        assert stmt.table.value == "t"
        assert len(stmt.columns) == 2
        assert stmt.columns[0].name.value == "x"
        assert stmt.columns[0].type_name == "INTEGER"
        assert stmt.columns[1].type_name == "TEXT"

    def test_if_not_exists(self) -> None:
        stmt = parse("CREATE TABLE IF NOT EXISTS t (x INTEGER)")
        assert stmt.if_not_exists

    def test_integer_primary_key(self) -> None:
        stmt = parse("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        pk = stmt.columns[0].constraints[0]
        assert pk.kind == "PRIMARY KEY"

    def test_autoincrement(self) -> None:
        stmt = parse("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        assert stmt.columns[0].constraints[0].autoincrement

    def test_not_null(self) -> None:
        stmt = parse("CREATE TABLE t (x INTEGER NOT NULL)")
        assert any(c.kind == "NOT NULL" for c in stmt.columns[0].constraints)

    def test_unique(self) -> None:
        stmt = parse("CREATE TABLE t (x TEXT UNIQUE)")
        assert any(c.kind == "UNIQUE" for c in stmt.columns[0].constraints)

    def test_without_rowid(self) -> None:
        stmt = parse("CREATE TABLE t (x INTEGER) WITHOUT ROWID")
        assert stmt.without_rowid


# --- CREATE INDEX ---
class TestCreateIndex:
    def test_basic(self) -> None:
        stmt = parse("CREATE INDEX idx ON t (x)")
        assert isinstance(stmt, CreateIndex)
        assert stmt.index.value == "idx"
        assert stmt.table.value == "t"
        assert not stmt.unique

    def test_unique_index(self) -> None:
        stmt = parse("CREATE UNIQUE INDEX idx ON t (x)")
        assert stmt.unique

    def test_if_not_exists(self) -> None:
        stmt = parse("CREATE INDEX IF NOT EXISTS idx ON t (x)")
        assert stmt.if_not_exists

    def test_partial_index(self) -> None:
        stmt = parse("CREATE INDEX idx ON t (x) WHERE x > 0")
        assert stmt.where is not None


# --- transaction ---
class TestTransaction:
    def test_begin(self) -> None:
        assert isinstance(parse("BEGIN"), Begin)
        assert isinstance(parse("BEGIN TRANSACTION"), Begin)
        assert isinstance(parse("BEGIN DEFERRED"), Begin)
        assert isinstance(parse("BEGIN IMMEDIATE"), Begin)

    def test_commit(self) -> None:
        assert isinstance(parse("COMMIT"), Commit)
        assert isinstance(parse("END"), Commit)

    def test_rollback(self) -> None:
        assert isinstance(parse("ROLLBACK"), Rollback)
        assert isinstance(parse("ROLLBACK TRANSACTION"), Rollback)


# --- rejection ---
class TestRejection:
    def test_invalid_syntax(self) -> None:
        with pytest.raises(ParseError):
            parse("SELECT FROM")

    def test_missing_table(self) -> None:
        # SELECT * without FROM is valid in SQLite (returns a single row).
        # But our test expects it to fail — let's test an actual invalid case instead.
        with pytest.raises(ParseError):
            parse("SELECT , FROM t")

    def test_unrecognized_statement(self) -> None:
        with pytest.raises(ParseError):
            parse("BLAH 1")

    def test_trailing_tokens(self) -> None:
        # "EXTRA" after a valid SELECT is consumed as an alias for the last
        # column. Test a real trailing-token case instead.
        with pytest.raises(ParseError):
            parse("SELECT 1 FROM t; ; ; 123")