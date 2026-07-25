"""Unit tests for Phase 9: constraint extraction, access method, cost model."""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-call"
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"

import sqlite3
from pathlib import Path

import pytest

from pyturso.parser.ast.expr import (
    BinaryExpr, IdExpr, InExpr, Literal, LiteralExpr, Name, Operator,
)
from pyturso.translate.optimizer.constraints import (
    Constraint, ConstraintOperator, extract_constraints,
)
from pyturso.translate.optimizer.access_method import (
    AccessMethod, choose_access_method,
)
from pyturso.translate.optimizer.cost import (
    Cost, CostConstants, estimate_cost,
)
from pyturso.types.affinity import Affinity
from pyturso.schema.objects import (
    Column, Index, IndexColumn, Schema, Table, make_column,
)


# --- constraint extraction ---
class TestConstraintExtraction:
    def _where_terms(self, *exprs):
        return list(exprs)

    def test_equality_constraint(self) -> None:
        term = BinaryExpr(
            IdExpr(Name("age")), Operator.Equals, LiteralExpr(Literal.Numeric, "30")
        )
        constraints = extract_constraints(
            self._where_terms(term), ["id", "name", "age"], None
        )
        assert len(constraints) == 1
        assert constraints[0].operator is ConstraintOperator.Eq
        assert constraints[0].col_index == 2  # "age" is column 2

    def test_less_than_constraint(self) -> None:
        term = BinaryExpr(
            IdExpr(Name("age")), Operator.Less, LiteralExpr(Literal.Numeric, "50")
        )
        constraints = extract_constraints(
            self._where_terms(term), ["id", "name", "age"], None
        )
        assert constraints[0].operator is ConstraintOperator.Lt

    def test_reversed_comparison(self) -> None:
        """value OP col → flip the operator."""
        term = BinaryExpr(
            LiteralExpr(Literal.Numeric, "50"), Operator.Less, IdExpr(Name("age"))
        )
        constraints = extract_constraints(
            self._where_terms(term), ["id", "name", "age"], None
        )
        assert len(constraints) == 1
        # 50 < age → age > 50
        assert constraints[0].operator is ConstraintOperator.Gt

    def test_in_constraint(self) -> None:
        term = InExpr(
            IdExpr(Name("city")), False,
            [LiteralExpr(Literal.String, "NYC"), LiteralExpr(Literal.String, "LA")]
        )
        constraints = extract_constraints(
            self._where_terms(term), ["id", "name", "city"], None
        )
        assert len(constraints) == 1
        assert constraints[0].operator is ConstraintOperator.In

    def test_non_comparison_not_extracted(self) -> None:
        """AND expression is not a single constraint."""
        from pyturso.parser.ast.expr import Operator
        term = BinaryExpr(
            BinaryExpr(IdExpr(Name("a")), Operator.Equals, LiteralExpr(Literal.Numeric, "1")),
            Operator.And,
            BinaryExpr(IdExpr(Name("b")), Operator.Equals, LiteralExpr(Literal.Numeric, "2")),
        )
        constraints = extract_constraints(
            self._where_terms(term), ["a", "b"], None
        )
        assert len(constraints) == 0  # AND is not a single constraint

    def test_rowid_alias_constraint(self) -> None:
        term = BinaryExpr(
            IdExpr(Name("id")), Operator.Equals, LiteralExpr(Literal.Numeric, "5")
        )
        constraints = extract_constraints(
            self._where_terms(term), ["id", "name"], rowid_alias_col=0
        )
        assert len(constraints) == 1
        assert constraints[0].is_rowid is True

    def test_unknown_column_not_extracted(self) -> None:
        term = BinaryExpr(
            IdExpr(Name("xyz")), Operator.Equals, LiteralExpr(Literal.Numeric, "1")
        )
        constraints = extract_constraints(
            self._where_terms(term), ["id", "name"], None
        )
        assert len(constraints) == 0


# --- access method ---
class TestAccessMethod:
    def _make_table(self) -> Table:
        return Table(
            name="t",
            columns=[
                make_column("id", "INTEGER", primary_key=True, rowid_alias=True),
                make_column("name", "TEXT"),
                make_column("age", "INTEGER"),
            ],
            root_page=2,
            rowid_alias_col=0,
        )

    def _make_schema_with_index(self) -> Schema:
        table = self._make_table()
        schema = Schema()
        schema.add_table(table)
        schema.add_index(Index(
            name="idx_age", table_name="t",
            columns=[IndexColumn("age", False)], root_page=3,
        ))
        return schema

    def test_seq_scan_no_constraints(self) -> None:
        table = self._make_table()
        result = choose_access_method(table, [], Schema())
        assert result.method is AccessMethod.SeqScan

    def test_index_seek_with_matching_constraint(self) -> None:
        table = self._make_table()
        schema = self._make_schema_with_index()
        constraint = Constraint(
            where_term_index=0, side=__import__(
                "pyturso.translate.optimizer.constraints", fromlist=["ConstraintSide"]
            ).ConstraintSide.Rhs,
            operator=ConstraintOperator.Eq,
            col_index=2,  # age
            constraining_expr=LiteralExpr(Literal.Numeric, "30"),
            usable=True,
        )
        result = choose_access_method(table, [constraint], schema)
        assert result.method is AccessMethod.IndexSeek
        assert result.index is not None
        assert result.index.name == "idx_age"

    def test_seq_scan_non_equality_constraint(self) -> None:
        """Range constraints don't drive index seek in Phase 9 simplified."""
        table = self._make_table()
        schema = self._make_schema_with_index()
        constraint = Constraint(
            where_term_index=0, side=__import__(
                "pyturso.translate.optimizer.constraints", fromlist=["ConstraintSide"]
            ).ConstraintSide.Rhs,
            operator=ConstraintOperator.Lt,
            col_index=2,
            constraining_expr=LiteralExpr(Literal.Numeric, "50"),
            usable=True,
        )
        result = choose_access_method(table, [constraint], schema)
        assert result.method is AccessMethod.SeqScan


# --- cost model ---
class TestCostModel:
    def test_seq_scan_cost(self) -> None:
        cost = estimate_cost("seq_scan", n_table_rows=100, n_output_rows=50)
        assert cost.startup == 10.0
        assert cost.run == 100.0  # 100 rows * 1.0 per row
        assert cost.total == 110.0

    def test_index_seek_cost(self) -> None:
        cost = estimate_cost("index_seek", n_table_rows=100, n_output_rows=5)
        assert cost.startup == 25.0  # 10 + 15
        assert cost.run == 0.5  # 5 rows * 0.1 per row
        assert cost.total == 25.5

    def test_index_scan_cost(self) -> None:
        cost = estimate_cost("index_scan", n_table_rows=100, n_output_rows=20)
        assert cost.startup == 25.0
        assert cost.run == 10.0  # 20 rows * 0.5 per row

    def test_custom_constants(self) -> None:
        constants = CostConstants(seq_scan_per_row=2.0, open_btree=5.0)
        cost = estimate_cost("seq_scan", n_table_rows=10, n_output_rows=5, constants=constants)
        assert cost.startup == 5.0
        assert cost.run == 20.0  # 10 * 2.0