"""select — SELECT translation entry point.

Ports: core/translate/select.rs.
Phase: 5
Status: IMPLEMENTED (single-table SELECT with WHERE, result columns, LIMIT).

The entry point: parse → plan → optimize (no-op) → emit. Ties together the
planner, optimizer seam, and emitter into a single ``translate_select``
function that takes SQL + schema and returns a VDBE Program.
"""

from __future__ import annotations

from pyturso.errors import NotSupported, TursoError
from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.ast.stmt import Select
from pyturso.schema.objects import Schema
from pyturso.translate.emitter.select import emit_select
from pyturso.translate.optimizer.noop import optimize
from pyturso.translate.planner import plan_select
from pyturso.translate.plan import Plan
from pyturso.vdbe.builder import ProgramBuilder
from pyturso.vdbe.program import Program

__all__ = ["translate_select", "translate"]


def translate_select(sql: str, schema: Schema) -> Program:
    """Compile a SELECT statement into a VDBE Program.

    The full Phase 5 pipeline: parse → plan → optimize (no-op) → emit.
    """
    ast = parse_sql(sql)
    if not isinstance(ast, Select):
        raise NotSupported(f"only SELECT supported in Phase 5, got {type(ast).__name__}")

    plan = plan_select(ast, schema)
    plan = optimize(plan)  # no-op seam for Phase 9
    builder = ProgramBuilder()
    return emit_select(plan, builder)


def translate(sql: str, schema: Schema) -> Program:
    """Compile any supported statement into a VDBE Program (Phase 5: SELECT only)."""
    return translate_select(sql, schema)