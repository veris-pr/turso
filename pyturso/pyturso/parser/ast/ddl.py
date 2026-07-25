"""ast.ddl — CREATE/DROP table & index nodes, column defs, constraints.

Ports: sqlite/parser/src/ast.rs (CreateTable, CreateIndex, ColumnDefinition,
table constraints, ColumnConstraint).
Phase: 3
Status: IMPLEMENTED (Phase 3 subset: CREATE TABLE with column defs and basic
constraints, CREATE INDEX).

Frozen dataclasses mirroring the Rust names. The parser parses and keeps
constraints; semantic enforcement (UNIQUE check etc.) belongs to later phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from .expr import Expr, Name

__all__ = [
    "ColumnConstraint", "TableConstraint",
    "ColumnDefinition", "CreateTable", "CreateIndex", "DropTable", "DropIndex",
    "DDL",
]


@dataclass(frozen=True)
class ColumnConstraint:
    """A column-level constraint: PRIMARY KEY, NOT NULL, UNIQUE, DEFAULT, CHECK, REFERENCES."""
    kind: str  # "PRIMARY KEY", "NOT NULL", "UNIQUE", "DEFAULT", "CHECK", "REFERENCES"
    expr: Expr | None = None  # for DEFAULT, CHECK
    type_name: str | None = None  # for REFERENCES (foreign table)
    autoincrement: bool = False  # for INTEGER PRIMARY KEY AUTOINCREMENT


@dataclass(frozen=True)
class TableConstraint:
    """A table-level constraint: PRIMARY KEY(...), UNIQUE(...), CHECK(...), FOREIGN KEY."""
    kind: str  # "PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN KEY"
    columns: list[Name] | None = None  # for PK, UNIQUE
    expr: Expr | None = None  # for CHECK


@dataclass(frozen=True)
class ColumnDefinition:
    """A column definition in CREATE TABLE: name, type, constraints."""
    name: Name
    constraints: list[ColumnConstraint]
    type_name: str | None = None


@dataclass(frozen=True)
class CreateTable:
    """CREATE TABLE [IF NOT EXISTS] name (cols) [WITHOUT ROWID]."""
    table: Name
    columns: list[ColumnDefinition]
    table_constraints: list[TableConstraint]
    schema: Name | None = None
    if_not_exists: bool = False
    without_rowid: bool = False


@dataclass(frozen=True)
class CreateIndex:
    """CREATE [UNIQUE] INDEX [IF NOT EXISTS] name ON table (cols) [WHERE]."""
    index: Name
    table: Name
    columns: list[Name]
    unique: bool = False
    if_not_exists: bool = False
    where: Expr | None = None


@dataclass(frozen=True)
class DropTable:
    """DROP TABLE [IF EXISTS] name."""
    table: Name
    if_exists: bool = False


@dataclass(frozen=True)
class DropIndex:
    """DROP INDEX [IF EXISTS] name."""
    index: Name
    if_exists: bool = False


#: DDL statement union.
DDL = Union[CreateTable, CreateIndex, DropTable, DropIndex]