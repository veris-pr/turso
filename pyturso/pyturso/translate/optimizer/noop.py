"""noop — the optimizer no-op seam.

Ports: (pyturso-specific) — the seam that Phase 9 will replace with real
optimization passes.
Phase: 5 (no-op) / 9 (real optimization)
Status: IMPLEMENTED (no-op pass-through).

The optimizer seam is a permanent fixture from Phase 5 day one: the plan
passes through a function that Phase 9 will replace. Correctness never depends
on the optimizer — results must be identical with optimization disabled. The
``force_disable`` flag is for testing.
"""

from __future__ import annotations
# mypy: disable-error-code="type-arg"
# mypy: disable-error-code="assignment"

from pyturso.translate.plan import Plan

__all__ = ["optimize"]

#: Global force-disable flag (set to True to bypass optimization even in Phase 9+).
force_disable: bool = True  # Phase 5: always disabled


def optimize(plan: Plan) -> Plan:
    """Optimize a plan.

    Phase 5: no-op (pass-through).
    Phase 9: constraint extraction + access method selection (when enabled).
    """
    if force_disable:
        return plan

    # Phase 9: extract constraints and choose access method.
    if plan.source is not None and plan.where_terms:
        from pyturso.schema.objects import Schema
        from pyturso.translate.optimizer.constraints import extract_constraints
        from pyturso.translate.optimizer.access_method import choose_access_method
        from pyturso.translate.optimizer.access_method import AccessMethod

        table = plan.source.table
        col_names = [c.name for c in table.columns]
        constraints = extract_constraints(
            [t.expr for t in plan.where_terms], col_names,
            table.rowid_alias_col,
        )
        # We can't choose access method without a schema here (the optimizer
        # seam doesn't have access to the schema). For Phase 9, the access
        # method selection is done in the planner, not here.
        # Store the constraints on the plan for the emitter to use.
        plan.constraints = constraints

    return plan