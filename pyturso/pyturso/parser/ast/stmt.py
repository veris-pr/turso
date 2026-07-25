"""ast.stmt — statement nodes: SELECT, INSERT, UPDATE, DELETE, transaction.

Ports: sqlite/parser/src/ast.rs (Stmt, Select, SelectBody, OneSelect,
ResultColumn, FromClause, SortedColumn, Limit, Distinctness, SortOrder,
JoinedSelectTable, Insert, Update, Delete).
Phase: 3
Status: IMPLEMENTED (Phase 3 subset: SELECT core, INSERT/UPDATE/DELETE,
BEGIN/COMMIT/ROLLBACK).

Frozen dataclasses mirroring the Rust names. No behavior — emission is
translate's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from .expr import Expr, Name, LiteralExpr

__all__ = [
    "SortOrder", "Distinctness", "As", "ResultColumn",
    "SelectTable", "FromClause", "SortedColumn", "Limit",
    "OneSelect", "SelectBody", "Select",
    "Insert", "Update", "Delete",
    "Begin", "Commit", "Rollback",
    "Stmt",
]


class SortOrder(Enum):
    """ASC / DESC. Ports ``ast::SortOrder``."""
    Asc = "ASC"
    Desc = "DESC"


class Distinctness(Enum):
    """DISTINCT / ALL. Ports ``ast::Distinctness``."""
    Distinct = "DISTINCT"
    All = "ALL"


@dataclass(frozen=True)
class As:
    """Column alias. Ports ``ast::As``."""
    name: Name
    has_as_keyword: bool = True


@dataclass(frozen=True)
class ResultColumn:
    """A SELECT result column: expression+alias, *, or table.*."""
    # expr + optional alias, or star (table=None for bare *, Name for table.*)
    expr: Expr | None = None
    alias: As | None = None
    star: bool = False
    table_star: Name | None = None


@dataclass(frozen=True)
class SelectTable:
    """A table source in FROM: table name or subquery, with optional alias."""
    name: Name | None = None  # table name (None for subquery)
    schema: Name | None = None
    alias: Name | None = None
    # subquery: Select | None = None  # Phase 3: single table only


@dataclass(frozen=True)
class FromClause:
    """FROM clause: base table + optional joins (Phase 3: single table, no joins)."""
    table: SelectTable | None = None


@dataclass(frozen=True)
class SortedColumn:
    """An ORDER BY term: expression + ASC/DESC."""
    expr: Expr
    order: SortOrder | None = None


@dataclass(frozen=True)
class Limit:
    """LIMIT + optional OFFSET."""
    count: Expr
    offset: Expr | None = None


@dataclass(frozen=True)
class OneSelect:
    """A single SELECT (not compound). Ports ``ast::OneSelect::Select``."""
    columns: list[ResultColumn]
    distinctness: Distinctness | None = None
    from_clause: FromClause | None = None
    where: Expr | None = None
    group_by: list[Expr] | None = None
    having: Expr | None = None


@dataclass(frozen=True)
class SelectBody:
    """SELECT body (handles compound queries; Phase 3: single SELECT only)."""
    select: OneSelect


@dataclass(frozen=True)
class Select:
    """A complete SELECT statement. Ports ``ast::Select``."""
    body: SelectBody
    order_by: list[SortedColumn] | None = None
    limit: Limit | None = None


# --- DML ---
@dataclass(frozen=True)
class Insert:
    """INSERT INTO table (cols) VALUES (lists). Ports ``ast::Insert``."""
    table: Name
    values: list[list[Expr]]  # list of value tuples
    schema: Name | None = None
    columns: list[Name] | None = None  # None = all columns
    or_action: str | None = None  # OR REPLACE / OR IGNORE etc.


@dataclass(frozen=True)
class Update:
    """UPDATE table SET col=expr WHERE ... Ports ``ast::Update``."""
    table: Name
    assignments: list[tuple[Name, Expr]]
    schema: Name | None = None
    where: Expr | None = None


@dataclass(frozen=True)
class Delete:
    """DELETE FROM table WHERE ... Ports ``ast::Delete``."""
    table: Name
    schema: Name | None = None
    where: Expr | None = None


# --- Transaction ---
@dataclass(frozen=True)
class Begin:
    """BEGIN [DEFERRED|IMMEDIATE|EXCLUSIVE] [TRANSACTION]."""
    tx_type: str = "DEFERRED"


@dataclass(frozen=True)
class Commit:
    """COMMIT [TRANSACTION]."""
    pass


@dataclass(frozen=True)
class Rollback:
    """ROLLBACK [TRANSACTION]."""
    pass


#: Statement union.
Stmt = Union[Select, Insert, Update, Delete, Begin, Commit, Rollback]