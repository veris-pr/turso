"""plan — the logical-plan IR: source tables, where terms, result columns, order/limit.

Ports: core/translate/plan.rs (``Plan``, ``ResultSetColumn``, ``WhereTerm``).
Phase: 5
Status: IMPLEMENTED (Phase 5 subset: one source table, where terms, result
columns, LIMIT/OFFSET).

The central IR between the planner and the emitter. The planner builds it
from the AST + schema; the optimizer (Phase 9) transforms it; the emitter
turns it into VDBE opcodes. Understanding this one type is understanding half
the compiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyturso.parser.ast.expr import Expr
from pyturso.parser.ast.stmt import SortedColumn
from pyturso.schema.objects import Table

__all__ = ["SourceTable", "WhereTerm", "ResultSetColumn", "Plan"]


@dataclass
class SourceTable:
    """A table source in the FROM clause (Phase 5: single table only)."""
    table: Table
    alias: str = ""  # table alias (empty = no alias)


@dataclass
class WhereTerm:
    """A WHERE clause term: a boolean expression + metadata.

    Phase 5: a single expression per term. Phase 9 adds constraint extraction
    (which columns, which operators, usable by an index).
    """
    expr: Expr


@dataclass
class ResultSetColumn:
    """A result column in the SELECT output.

    Attributes:
        expr: the expression to evaluate (None for *).
        name: the output column name (alias or derived).
        is_star: True for bare ``*``.
        table_star: table name for ``table.*`` (None otherwise).
        col_index: the physical column index in the source table (for simple
            column refs; -1 for expressions).
    """
    expr: Expr | None
    name: str
    is_star: bool = False
    table_star: str = ""
    col_index: int = -1


@dataclass
class Plan:
    """The logical plan for a SELECT. Ports ``core::translate::plan::Plan``.

    Phase 5 subset: one source table, a WHERE term list, result columns,
    ORDER BY, LIMIT/OFFSET. Phase 9 adds joins, index choices, access methods.
    """
    source: SourceTable | None = None
    where_terms: list[WhereTerm] = field(default_factory=list)
    result_columns: list[ResultSetColumn] = field(default_factory=list)
    order_by: list[SortedColumn] | None = None
    limit: Expr | None = None
    offset: Expr | None = None
    distinct: bool = False
    # The cursor ID assigned by the emitter.
    cursor_id: int = 0
    constraints: list[object] = field(default_factory=list)  # Phase 9: extracted constraints