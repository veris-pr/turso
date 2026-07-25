"""ast.expr — expression nodes.

Ports: sqlite/parser/src/ast.rs (Expr, Operator, UnaryOperator, Literal, Name).
Phase: 3
Status: IMPLEMENTED (Phase 3 subset: literals, identifiers, unary, binary,
case, between, cast, collate, in, is-null, not-null, function calls).

Frozen dataclasses mirroring the Rust enum/struct names. No behavior on nodes
— eval/emission belong to translate/. ``__repr__`` (dataclass default) stays
stable for snapshot tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

__all__ = [
    "Operator", "UnaryOperator", "Literal", "Name",
    "Expr",
    "LiteralExpr", "IdExpr", "QualifiedExpr", "DoublyQualifiedExpr",
    "UnaryExpr", "BinaryExpr", "BetweenExpr", "CastExpr", "CollateExpr",
    "CaseExpr", "IsNullExpr", "NotNullExpr", "InExpr", "FunctionCallExpr",
    "ParenExpr",
]


class Operator(Enum):
    """Binary operators. Ports ``ast::Operator``."""
    Add = "+"
    Subtract = "-"
    Multiply = "*"
    Divide = "/"
    Modulus = "%"
    Concat = "||"
    BitwiseAnd = "&"
    BitwiseOr = "|"
    LeftShift = "<<"
    RightShift = ">>"
    Equals = "="
    NotEquals = "!="
    Less = "<"
    LessEquals = "<="
    Greater = ">"
    GreaterEquals = ">="
    And = "AND"
    Or = "OR"
    Is = "IS"
    IsNot = "IS NOT"
    Like = "LIKE"
    Glob = "GLOB"


class UnaryOperator(Enum):
    """Unary operators. Ports ``ast::UnaryOperator``."""
    BitwiseNot = "~"
    Negative = "-"
    Not = "NOT"
    Positive = "+"


class Literal(Enum):
    """Literal kinds. Ports ``ast::Literal``.

    Python keywords ``True``/``False`` can't be enum members, so they're
    suffixed with ``_``.
    """
    Null = "NULL"
    True_ = "TRUE"
    False_ = "FALSE"

    # Numeric, String, Blob carry their value externally (in LiteralExpr).
    Numeric = "NUMERIC"
    String = "STRING"
    Blob = "BLOB"
    Keyword = "KEYWORD"


@dataclass(frozen=True)
class Name:
    """An identifier name. Ports ``ast::Name`` (value + quoting info simplified)."""
    value: str

    def __str__(self) -> str:
        return self.value


# --- Expression node types (frozen dataclasses) --------------------------
@dataclass(frozen=True)
class LiteralExpr:
    """A literal value: NULL, TRUE, numeric string, string, blob, keyword."""
    literal: Literal
    value: str = ""


@dataclass(frozen=True)
class IdExpr:
    """A bare identifier: ``col``."""
    name: Name


@dataclass(frozen=True)
class QualifiedExpr:
    """A qualified identifier: ``table.col``."""
    table: Name
    column: Name


@dataclass(frozen=True)
class DoublyQualifiedExpr:
    """A doubly-qualified identifier: ``schema.table.col``."""
    schema: Name
    table: Name
    column: Name


@dataclass(frozen=True)
class UnaryExpr:
    """A unary expression: ``-x``, ``~x``, ``NOT x``, ``+x``."""
    op: UnaryOperator
    operand: "Expr"


@dataclass(frozen=True)
class BinaryExpr:
    """A binary expression: ``a + b``, ``a = b``, ``a AND b``, etc."""
    left: "Expr"
    op: Operator
    right: "Expr"


@dataclass(frozen=True)
class BetweenExpr:
    """A BETWEEN expression: ``x BETWEEN a AND b`` (with optional NOT)."""
    expr: "Expr"
    not_: bool
    start: "Expr"
    end: "Expr"


@dataclass(frozen=True)
class CastExpr:
    """A CAST expression: ``CAST(x AS type)``."""
    expr: "Expr"
    type_name: str


@dataclass(frozen=True)
class CollateExpr:
    """A COLLATE expression: ``x COLLATE NOCASE``."""
    expr: "Expr"
    collation: Name


@dataclass(frozen=True)
class CaseExpr:
    """A CASE expression: ``CASE base WHEN w THEN t ... ELSE e``."""
    base: "Expr | None"
    when_then: list[tuple["Expr", "Expr"]]
    else_expr: "Expr | None"


@dataclass(frozen=True)
class IsNullExpr:
    """``x IS NULL``."""
    expr: "Expr"


@dataclass(frozen=True)
class NotNullExpr:
    """``x IS NOT NULL``."""
    expr: "Expr"


@dataclass(frozen=True)
class InExpr:
    """``x IN (list)`` or ``x IN (subquery)`` (with optional NOT)."""
    expr: "Expr"
    not_: bool
    # Either a list of expressions or a subquery (Select). For Phase 3, list only.
    values: list["Expr"]


@dataclass(frozen=True)
class FunctionCallExpr:
    """A function call: ``func(a, b, ...)`` with optional DISTINCT."""
    name: Name
    args: list["Expr"]
    distinct: bool = False


@dataclass(frozen=True)
class ParenExpr:
    """A parenthesized expression: ``(x)``."""
    inner: "Expr"


#: The union of all expression node types.
Expr = Union[
    LiteralExpr, IdExpr, QualifiedExpr, DoublyQualifiedExpr,
    UnaryExpr, BinaryExpr, BetweenExpr, CastExpr, CollateExpr,
    CaseExpr, IsNullExpr, NotNullExpr, InExpr, FunctionCallExpr,
    ParenExpr,
]