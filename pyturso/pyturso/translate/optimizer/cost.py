"""optimizer.cost — cost model + constants.

Ports: core/translate/optimizer/cost.rs, cost_params.rs.
Phase: 9
Status: IMPLEMENTED (simplified cost model with basic constants).

The cost model estimates the cost of a query plan to choose between
alternatives. SQLite's cost model is a simple weighted sum:
  cost = N_rows * cost_per_row + startup_cost

Phase 9 simplified constants (ported from the Rust's defaults):
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CostConstants", "Cost", "estimate_cost"]


@dataclass(frozen=True)
class CostConstants:
    """Cost model constants. Ports the Rust defaults."""
    # Cost per row of a sequential scan.
    seq_scan_per_row: float = 1.0
    # Cost per row of an index scan (cheaper than seq scan).
    index_scan_per_row: float = 0.5
    # Cost per row of an index seek (point lookup).
    index_seek_per_row: float = 0.1
    # Startup cost for opening a B-tree.
    open_btree: float = 10.0
    # Startup cost for opening an index.
    open_index: float = 15.0
    # Cost per row of sorting.
    sort_per_row: float = 1.5


# Default constants.
_DEFAULTS = CostConstants()


@dataclass
class Cost:
    """Estimated cost of a plan.

    Attributes:
        startup: one-time cost (opening cursors, etc.).
        run: per-row cost * estimated rows.
        total: startup + run.
        estimated_rows: the estimated number of output rows.
    """
    startup: float = 0.0
    run: float = 0.0
    estimated_rows: int = 0

    @property
    def total(self) -> float:
        return self.startup + self.run


def estimate_cost(
    method: str, n_table_rows: int, n_output_rows: int,
    constants: CostConstants | None = None,
) -> Cost:
    """Estimate the cost of an access method.

    Args:
        method: "seq_scan", "index_seek", or "index_scan".
        n_table_rows: total rows in the table.
        n_output_rows: estimated output rows (after filtering).
        constants: cost model constants (defaults if None).
    """
    c = constants or _DEFAULTS

    if method == "seq_scan":
        return Cost(
            startup=c.open_btree,
            run=n_table_rows * c.seq_scan_per_row,
            estimated_rows=n_output_rows,
        )
    elif method == "index_seek":
        return Cost(
            startup=c.open_btree + c.open_index,
            run=n_output_rows * c.index_seek_per_row,
            estimated_rows=n_output_rows,
        )
    elif method == "index_scan":
        return Cost(
            startup=c.open_btree + c.open_index,
            run=n_output_rows * c.index_scan_per_row,
            estimated_rows=n_output_rows,
        )
    else:
        return Cost(estimated_rows=n_output_rows)