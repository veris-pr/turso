"""statement — prepared program + step lifecycle.

Ports: core/statement.rs.
Phase: 5
Status: IMPLEMENTED (simplified: execute + collect rows; step-by-step
execution is a future refinement).

A :class:`Statement` wraps a compiled :class:`Program` and its execution
state. It supports the SQLite-like protocol: ``step()`` returns one row at a
time, ``run()`` collects all rows, ``reset()`` re-runs from the start,
``finalize()`` releases the program.
"""

from __future__ import annotations
# mypy: disable-error-code="no-untyped-def"
# mypy: disable-error-code="unused-ignore"

from pyturso.errors import TursoError
from pyturso.types.value import Value
from pyturso.vdbe.execute import VMState, execute as run_vdbe
from pyturso.vdbe.program import Program

__all__ = ["Statement"]


class Statement:
    """A prepared SQL statement.

    Attributes:
        program: the compiled VDBE program.
        _state: the last execution state (None until first step).
        _finalized: whether the statement has been finalized.
    """

    def __init__(self, program: Program, pager) -> None:
        self.program = program
        self._pager = pager
        self._state: VMState | None = None
        self._finalized: bool = False
        self._row_index: int = 0

    def _check_finalized(self) -> None:
        if self._finalized:
            raise TursoError("statement has been finalized")

    def step(self) -> tuple[Value, ...] | None:
        """Execute the program and return the next row, or None if done.

        On first call, runs the full program and collects all rows. Subsequent
        calls return rows one at a time from the collected list.
        """
        self._check_finalized()
        if self._state is None:
            self._state = run_vdbe(self.program, self._pager)
            self._row_index = 0
        if self._row_index < len(self._state.result_rows):
            row = self._state.result_rows[self._row_index]
            self._row_index += 1
            return row
        return None

    def run(self) -> list[tuple[Value, ...]]:
        """Execute the program and return all result rows."""
        self._check_finalized()
        self._state = run_vdbe(self.program, self._pager)
        self._row_index = len(self._state.result_rows)
        return list(self._state.result_rows)

    def reset(self) -> None:
        """Reset the statement for re-execution (clears the result state)."""
        self._check_finalized()
        self._state = None
        self._row_index = 0

    def finalize(self) -> None:
        """Finalize the statement (no further use allowed)."""
        self._finalized = True
        self._state = None

    def __iter__(self):  # type: ignore[no-untyped-def]
        """Iterate over result rows (runs the program on first iteration)."""
        self._check_finalized()
        if self._state is None:
            self._state = run_vdbe(self.program, self._pager)
            self._row_index = 0
        while self._row_index < len(self._state.result_rows):
            row = self._state.result_rows[self._row_index]
            self._row_index += 1
            yield row