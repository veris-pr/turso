"""optimizer.constraints — WHERE terms → index-usable constraints.

Ports: core/translate/optimizer/constraints.rs (Constraint, ConstraintOperator,
constraints_from_where_clause).
Phase: 9
Status: IMPLEMENTED (simplified: extracts column-op-value constraints from
WHERE terms; identifies index-usable shapes =, <, <=, >, >=, IN).

Constraint extraction is the first optimizer step: it analyzes the WHERE
clause to find comparisons that can drive an index seek instead of a full
table scan. A "constraint" is a WHERE term of the form ``col OP value`` where
``col`` is a column reference and ``value`` is a constant (or an expression
involving already-joined tables).

Phase 9 simplified subset:
  - ``col = value`` → equality constraint (drives index seek)
  - ``col < value``, ``col <= value``, ``col > value``, ``col >= value`` → range constraints
  - ``col IN (v1, v2, ...)`` → IN constraint (multi-value seek)
  - Only top-level WHERE terms (no AND sub-expression extraction yet)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from pyturso.parser.ast.expr import (
    BinaryExpr, Expr, IdExpr, InExpr, LiteralExpr, Operator,
    QualifiedExpr,
)

__all__ = [
    "ConstraintOperator", "Constraint", "ConstraintSide",
    "extract_constraints",
]


class ConstraintSide(str, Enum):
    """Which side of the comparison contains the constraining expression."""
    Lhs = "lhs"
    Rhs = "rhs"


class ConstraintOperator(Enum):
    """The operator of a constraint. Ports ``ConstraintOperator``."""
    Eq = Operator.Equals
    Ne = Operator.NotEquals
    Lt = Operator.Less
    Le = Operator.LessEquals
    Gt = Operator.Greater
    Ge = Operator.GreaterEquals
    In = "IN"
    Like = "LIKE"


@dataclass
class Constraint:
    """An index-usable constraint extracted from a WHERE term.

    Ports ``core::Constraint`` (simplified — no selectivity/lhs_mask/affinity yet).

    Attributes:
        where_term_index: the index of the WHERE term this constraint came from.
        side: which side of the comparison is the column (Lhs or Rhs).
        operator: the comparison operator.
        col_index: the 0-based column index in the table (or None if not a simple column ref).
        constraining_expr: the expression on the other side (the value to seek for).
        is_rowid: whether this constrains the implicit rowid.
        usable: whether this constraint can drive an index seek.
    """
    where_term_index: int
    side: ConstraintSide
    operator: ConstraintOperator
    col_index: int | None
    constraining_expr: Expr
    is_rowid: bool = False
    usable: bool = True


def extract_constraints(
    where_terms: list[Expr], table_col_names: list[str],
    rowid_alias_col: int | None,
) -> list[Constraint]:
    """Extract constraints from a WHERE term list.

    Args:
        where_terms: the WHERE clause expressions (one per top-level term).
        table_col_names: the column names of the source table (for name resolution).
        rowid_alias_col: the index of the rowid-alias column (or None).

    Returns:
        A list of :class:`Constraint` objects. Non-usable terms are not included.
    """
    constraints: list[Constraint] = []
    col_names_lower = [c.lower() for c in table_col_names]

    for i, term in enumerate(where_terms):
        constraint = _try_extract_constraint(
            term, i, col_names_lower, rowid_alias_col
        )
        if constraint is not None:
            constraints.append(constraint)

    return constraints


def _try_extract_constraint(
    expr: Expr, term_index: int,
    col_names_lower: list[str], rowid_alias_col: int | None,
) -> Constraint | None:
    """Try to extract a single constraint from one WHERE term.

    Returns None if the term is not a simple column-op-value comparison.
    """
    # IN constraint: col IN (v1, v2, ...)
    if isinstance(expr, InExpr) and not expr.not_:
        col_idx, side = _resolve_column_side(expr.expr, col_names_lower)
        if col_idx is not None:
            return Constraint(
                where_term_index=term_index,
                side=ConstraintSide.Rhs,
                operator=ConstraintOperator.In,
                col_index=col_idx,
                constraining_expr=expr,  # the whole IN expr
                is_rowid=(col_idx == rowid_alias_col),
                usable=True,
            )

    # Binary comparison: col OP value or value OP col
    if not isinstance(expr, BinaryExpr):
        return None

    op = expr.op
    if op not in (Operator.Equals, Operator.NotEquals, Operator.Less,
                  Operator.LessEquals, Operator.Greater,
                  Operator.GreaterEquals):
        return None

    # Try col OP value
    col_idx, side = _resolve_column_side(expr.left, col_names_lower)
    if col_idx is not None:
        other = expr.right
        # Check that the other side is a literal (constant).
        if not _is_constant(other):
            return None
        return Constraint(
            where_term_index=term_index,
            side=ConstraintSide.Rhs,
            operator=_op_to_constraint(op),
            col_index=col_idx,
            constraining_expr=other,
            is_rowid=(col_idx == rowid_alias_col),
            usable=True,
        )

    # Try value OP col (reversed)
    col_idx, side = _resolve_column_side(expr.right, col_names_lower)
    if col_idx is not None:
        other = expr.left
        if not _is_constant(other):
            return None
        return Constraint(
            where_term_index=term_index,
            side=ConstraintSide.Lhs,
            operator=_flip_op(_op_to_constraint(op)),
            col_index=col_idx,
            constraining_expr=other,
            is_rowid=(col_idx == rowid_alias_col),
            usable=True,
        )

    return None


def _resolve_column_side(
    expr: Expr, col_names_lower: list[str],
) -> tuple[int | None, ConstraintSide]:
    """Check if ``expr`` is a column reference. Returns (col_index, side) or (None, _)."""
    if isinstance(expr, IdExpr):
        name = expr.name.value.lower()
        if name in col_names_lower:
            return col_names_lower.index(name), ConstraintSide.Lhs
    if isinstance(expr, QualifiedExpr):
        name = expr.column.value.lower()
        if name in col_names_lower:
            return col_names_lower.index(name), ConstraintSide.Lhs
    return None, ConstraintSide.Rhs


def _is_constant(expr: Expr) -> bool:
    """Check if an expression is a compile-time constant (literal)."""
    return isinstance(expr, LiteralExpr)


def _op_to_constraint(op: Operator) -> ConstraintOperator:
    """Map an AST Operator to a ConstraintOperator."""
    mapping = {
        Operator.Equals: ConstraintOperator.Eq,
        Operator.NotEquals: ConstraintOperator.Ne,
        Operator.Less: ConstraintOperator.Lt,
        Operator.LessEquals: ConstraintOperator.Le,
        Operator.Greater: ConstraintOperator.Gt,
        Operator.GreaterEquals: ConstraintOperator.Ge,
    }
    return mapping.get(op, ConstraintOperator.Eq)


def _flip_op(op: ConstraintOperator) -> ConstraintOperator:
    """Flip a comparison operator (for value OP col → col OP' value)."""
    flips = {
        ConstraintOperator.Eq: ConstraintOperator.Eq,
        ConstraintOperator.Ne: ConstraintOperator.Ne,
        ConstraintOperator.Lt: ConstraintOperator.Gt,
        ConstraintOperator.Le: ConstraintOperator.Ge,
        ConstraintOperator.Gt: ConstraintOperator.Lt,
        ConstraintOperator.Ge: ConstraintOperator.Le,
    }
    return flips.get(op, op)