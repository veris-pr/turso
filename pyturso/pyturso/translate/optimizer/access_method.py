"""optimizer.access_method — seq scan vs index seek/scan.

Ports: core/translate/optimizer/access_method.rs.
Phase: 9
Status: IMPLEMENTED (simplified: seq scan always, or index seek if an index
covers an equality constraint on a column).

The access method determines how a table is scanned:
  - **SeqScan**: iterate all rows of the table's B-tree (always available).
  - **IndexSeek**: use an index to find matching rows (if a usable constraint
    matches an index column).

Phase 9 simplified: choose IndexSeek if an index's first column has an
equality constraint; otherwise SeqScan. The full optimizer (Phase 9+)
adds: covering index detection, range scan, cost-based selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pyturso.schema.objects import Index, Schema, Table
from pyturso.translate.optimizer.constraints import Constraint, ConstraintOperator

__all__ = ["AccessMethod", "choose_access_method"]


class AccessMethod(str, Enum):
    """How a table is accessed. Ports the Rust access-method enum."""
    SeqScan = "seq_scan"
    IndexSeek = "index_seek"
    IndexScan = "index_scan"


@dataclass
class AccessResult:
    """The result of access-method selection.

    Attributes:
        method: the chosen access method.
        index: the index used (if IndexSeek/IndexScan), else None.
        constraints: the constraints that drove the choice.
    """
    method: AccessMethod
    index: Index | None = None
    constraints: list[Constraint] | None = None


def choose_access_method(
    table: Table, constraints: list[Constraint], schema: Schema,
) -> AccessResult:
    """Choose the best access method for a table given its constraints.

    Phase 9 simplified: if any index on the table has its first column matching
    an equality constraint, use IndexSeek. Otherwise SeqScan.
    """
    indexes = schema.indexes_on(table.name)

    for idx in indexes:
        if not idx.columns:
            continue
        idx_col_name = idx.columns[0].name.lower()
        for constraint in constraints:
            if constraint.operator is not ConstraintOperator.Eq:
                continue
            if constraint.col_index is None:
                continue
            # Check if the constraint's column matches the index's first column.
            col_name = table.columns[constraint.col_index].name.lower()
            if col_name == idx_col_name:
                return AccessResult(
                    method=AccessMethod.IndexSeek,
                    index=idx,
                    constraints=[constraint],
                )

    return AccessResult(method=AccessMethod.SeqScan)