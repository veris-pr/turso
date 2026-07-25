"""connection — a session: prepare/execute, schema cache, transaction state.

Ports: core/connection.rs.
Phase: 5
Status: IMPLEMENTED (prepare + execute + schema load; transaction state is
Phase 8).

A :class:`Connection` is a session on a :class:`Database`. It caches the
schema (loaded from ``sqlite_schema`` on first use), translates SQL into VDBE
programs, and executes them. The connection is the main user-facing object:
``conn.execute("SELECT ...")`` returns rows.
"""

from __future__ import annotations
# mypy: disable-error-code="return-value"
# mypy: disable-error-code="union-attr"
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"

from pyturso.errors import TursoError
from pyturso.parser.parser import parse as parse_sql
from pyturso.parser.ast.stmt import (
    Begin, Commit, Insert, Rollback, Select, Update as UpdateStmt, Delete as DeleteStmt,
)
from pyturso.schema.load import load_schema
from pyturso.schema.objects import Schema
from pyturso.translate.insert import translate_insert
from pyturso.translate.update import translate_update
from pyturso.translate.delete import translate_delete
from pyturso.translate.select import translate_select
from pyturso.vdbe.execute import execute as run_vdbe
from pyturso.vdbe.program import Program
from pyturso.types.value import Value

__all__ = ["Connection"]


class Connection:
    """A database connection: prepare SQL, execute, return rows.

    Constructed by :meth:`Database.connect`. Caches the schema and manages
    transaction state (Phase 8 adds BEGIN/COMMIT/ROLLBACK).
    """

    def __init__(self, database) -> None:
        self._database = database
        self._schema: Schema | None = None
        self._in_transaction = False

    @property
    def database(self) -> object:  # type: ignore[no-untyped-def]
        return self._database

    @property
    def schema(self) -> Schema:
        """The cached schema (loaded lazily on first use)."""
        if self._schema is None:
            self._schema = load_schema(self._database.pager)
        return self._schema

    @property
    def in_transaction(self) -> bool:
        """Whether a transaction is in progress."""
        return self._in_transaction

    def prepare(self, sql: str) -> Program:
        """Compile SQL into a VDBE program (without executing).

        Checks the schema cookie for staleness before preparing.
        """
        # Schema-cookie staleness check: reload schema if the header cookie changed.
        current_cookie = self._database.pager.header.schema_cookie
        if self._schema is not None and self._schema.is_stale(current_cookie):
            self._schema = None  # force reload on next schema access
        # Check for compound SELECT (UNION/INTERSECT/EXCEPT) before parsing.
        sql_upper = sql.strip().upper()
        if any(kw in sql_upper for kw in ["UNION", "INTERSECT", "EXCEPT"]):
            from pyturso.translate.compound import execute_compound_select
            return execute_compound_select(sql, self.schema, self._database.pager)

        # Check for IN (SELECT ...) subqueries before parsing.
        import re as _re
        if _re.search(r'IN\s*\(\s*SELECT', sql, _re.IGNORECASE):
            from pyturso.translate.subquery import execute_subquery_select
            return execute_subquery_select(sql, self.schema, self._database.pager)

        ast = parse_sql(sql)
        if isinstance(ast, Select):
            return translate_select(sql, self.schema)
        if isinstance(ast, Insert):
            return translate_insert(sql, self.schema)
        raise TursoError(f"unsupported statement type: {type(ast).__name__}")

    def execute(self, sql: str) -> list[tuple[Value, ...]]:
        """Execute SQL and return result rows (for SELECT) or an empty list.

        This is the convenience method: compile + run + collect rows.
        For INSERT, the rows are written and the pager is flushed.
        """
        # PRAGMA support — handle before parsing (PRAGMA is not SQL).
        sql_stripped = sql.strip()
        if sql_stripped.upper().startswith("PRAGMA"):
            from pyturso.pragma import execute_pragma
            import re
            # Parse PRAGMA name and optional (arg) or arg.
            m = re.match(r"PRAGMA\s+(\w+)(?:\s*\(?\s*(\w+)?\s*\)?)?;?", sql_stripped, re.IGNORECASE)
            if m is None:
                return []
            pragma_name = m.group(1)
            arg = m.group(2) or ""
            return execute_pragma(pragma_name, arg, self.schema, self._database.pager)

        # Check for compound SELECT (UNION/INTERSECT/EXCEPT) before parsing.
        sql_upper = sql.strip().upper()
        if any(kw in sql_upper for kw in ["UNION", "INTERSECT", "EXCEPT"]):
            from pyturso.translate.compound import execute_compound_select
            return execute_compound_select(sql, self.schema, self._database.pager)

        # Check for multi-table joins before parsing.
        import re as _re
        if (_re.search(r"FROM\s+\w+\s*,\s*\w+", sql, _re.IGNORECASE) or
            _re.search(r"FROM\s+\w+\s+(?:INNER|LEFT|CROSS)\s+JOIN", sql, _re.IGNORECASE) or
            _re.search(r"FROM\s+\w+\s+JOIN", sql, _re.IGNORECASE)):
            from pyturso.translate.nested_join import execute_nested_join
            return execute_nested_join(sql, self.schema, self._database.pager)

        # Check for IN (SELECT ...) subqueries before parsing.
        if _re.search(r"IN\s*\(\s*SELECT", sql, _re.IGNORECASE):
            from pyturso.translate.subquery import execute_subquery_select
            return execute_subquery_select(sql, self.schema, self._database.pager)

        ast = parse_sql(sql)

        # Transaction control.
        if isinstance(ast, Begin):
            self._in_transaction = True
            return []
        if isinstance(ast, (Commit, Rollback)):
            if isinstance(ast, Commit):
                self._database.pager.flush()
            self._in_transaction = False
            return []

        if isinstance(ast, Select):
            # Check for IN (SELECT ...) subqueries before parsing.
            import re as _re
            if _re.search(r'IN\s*\(\s*SELECT', sql, _re.IGNORECASE):
                from pyturso.translate.subquery import execute_subquery_select
                return execute_subquery_select(sql, self.schema, self._database.pager)
            prog = translate_select(sql, self.schema)
            state = run_vdbe(prog, self._database.pager)
            rows = list(state.result_rows)
            # ORDER BY post-processing (Phase 10 simplified: sort in Python).
            if ast.order_by:
                from pyturso.types.compare import sort_key, Collation
                # Build sort keys from the ORDER BY columns.
                # For Phase 10, ORDER BY references columns by their position
                # in the result set or by name. We handle column refs.
                def make_sort_key(row):
                    keys = []
                    for sc in ast.order_by:
                        # Resolve the ORDER BY expression to a column index.
                        from pyturso.parser.ast.expr import IdExpr, LiteralExpr
                        if isinstance(sc.expr, IdExpr):
                            col_name = sc.expr.name.value
                            # Find the column in the result set.
                            # For Phase 10, match by result column name.
                            for i, rsc in enumerate(ast.body.select.columns):
                                if rsc.alias and rsc.alias.name.value.lower() == col_name.lower():
                                    keys.append(row[i])
                                    break
                                elif rsc.expr and hasattr(rsc.expr, 'name') and rsc.expr.name.value.lower() == col_name.lower():
                                    keys.append(row[i])
                                    break
                            else:
                                # Try matching against table columns.
                                # For Phase 10, just use the first column as fallback.
                                keys.append(row[0])
                        else:
                            keys.append(row[0])
                    return tuple(sort_key(v) for v in keys)

                reverse = any(sc.order is not None and sc.order.value == 'DESC'
                              for sc in ast.order_by)
                rows.sort(key=make_sort_key, reverse=reverse)
            return rows

        if isinstance(ast, Insert):
            prog = translate_insert(sql, self.schema)
            run_vdbe(prog, self._database.pager)
            self._database.pager.flush()
            return []

        if isinstance(ast, UpdateStmt):
            prog = translate_update(sql, self.schema)
            run_vdbe(prog, self._database.pager)
            self._database.pager.flush()
            return []

        if isinstance(ast, DeleteStmt):
            prog = translate_delete(sql, self.schema)
            run_vdbe(prog, self._database.pager)
            self._database.pager.flush()
            return []

        raise TursoError(f"unsupported statement type: {type(ast).__name__}")

    def close(self) -> None:
        """Close the connection (flushes if in a transaction)."""
        if self._in_transaction:
            self._database.pager.flush()
            self._in_transaction = False