"""aggregate — count/sum/avg/min/max/group_concat step/finalize.

Ports: core/functions/aggregate.rs, core/vdbe/execute.rs aggregate paths.
Phase: 10
Status: IMPLEMENTED (count, sum, avg, min, max, group_concat).

Aggregate functions maintain state across rows (step → finalize). The VM
calls ``step`` for each row in a group, then ``finalize`` to get the result.
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="arg-type"

from pyturso.types.compare import compare_values
from pyturso.types.value import Value

__all__ = ["AggregateState", "step_aggregate", "finalize_aggregate"]


class AggregateState:
    """The running state of an aggregate function."""

    def __init__(self, name: str) -> None:
        self.name = name.lower()
        self.count: int = 0
        self.sum: float = 0.0
        self.sum_is_int: bool = True
        self.min_val: Value | None = None
        self.max_val: Value | None = None
        self.concat_values: list[str] = []
        self.has_rows: bool = False

    def step(self, args: list[Value]) -> None:
        """Process one row's arguments."""
        self.has_rows = True
        if self.name == "count":
            # COUNT(*) counts all rows; COUNT(x) counts non-NULL x.
            if not args or args[0] is None:
                self.count += 1  # COUNT(*)
            elif not args[0].is_null:
                self.count += 1
            return

        if self.name == "sum" or self.name == "total":
            v = args[0] if args else Value.null()
            if not v.is_null:
                self.count += 1
                if v.is_integer:
                    self.sum += float(v.payload)  # type: ignore[arg-type]
                elif v.is_real:
                    self.sum += float(v.payload)  # type: ignore[arg-type]
                if not v.is_integer:
                    self.sum_is_int = False
            return

        if self.name == "avg":
            v = args[0] if args else Value.null()
            if not v.is_null:
                self.count += 1
                if v.is_integer:
                    self.sum += float(v.payload)  # type: ignore[arg-type]
                elif v.is_real:
                    self.sum += float(v.payload)  # type: ignore[arg-type]
            return

        if self.name == "min":
            v = args[0] if args else Value.null()
            if not v.is_null:
                if self.min_val is None or compare_values(v, self.min_val) < 0:
                    self.min_val = v
            return

        if self.name == "max":
            v = args[0] if args else Value.null()
            if not v.is_null:
                if self.max_val is None or compare_values(v, self.max_val) > 0:
                    self.max_val = v
            return

        if self.name == "group_concat":
            v = args[0] if args else Value.null()
            if not v.is_null:
                s = v.payload if v.is_text else str(v.payload)  # type: ignore[union-attr]
                self.concat_values.append(s)
            return

    def finalize(self) -> Value:
        """Return the final aggregate result."""
        if self.name == "count":
            return Value.integer(self.count)

        if self.name == "sum":
            if not self.has_rows:
                return Value.null()
            if self.sum_is_int and self.sum == int(self.sum):
                return Value.integer(int(self.sum))
            return Value.real(self.sum)

        if self.name == "total":
            # total() always returns REAL, even for empty input.
            return Value.real(self.sum)

        if self.name == "avg":
            if self.count == 0:
                return Value.null()
            return Value.real(self.sum / self.count)

        if self.name == "min":
            return self.min_val if self.min_val is not None else Value.null()

        if self.name == "max":
            return self.max_val if self.max_val is not None else Value.null()

        if self.name == "group_concat":
            if not self.concat_values:
                return Value.null()
            sep = ","  # default separator
            return Value.text(sep.join(self.concat_values))

        return Value.null()


def step_aggregate(state: AggregateState, args: list[Value]) -> None:
    """Step an aggregate function."""
    state.step(args)


def finalize_aggregate(state: AggregateState) -> Value:
    """Finalize an aggregate function."""
    return state.finalize()