"""program — the compiled artifact translate/ produces.

Ports: core/vdbe/ (program repr — ``Program`` struct).
Phase: 5
Status: IMPLEMENTED.

A ``Program`` is a list of :class:`pyturso.vdbe.insn.Insn` objects plus
metadata: the number of registers and cursors it uses, and the origin SQL
(for EXPLAIN and debugging). The translator builds it; the executor runs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyturso.vdbe.insn import Insn

__all__ = ["Program"]


@dataclass
class Program:
    """A compiled VDBE program.

    Attributes:
        insns: the instruction list (indexed by address).
        n_registers: number of registers the program uses (r[0]..r[n-1]).
        n_cursors: number of cursors the program opens (c[0]..c[n-1]).
        sql: the origin SQL text (for EXPLAIN and debugging).
    """

    insns: list[Insn] = field(default_factory=list)
    n_registers: int = 0
    n_cursors: int = 0
    sql: str = ""

    @property
    def n_insns(self) -> int:
        return len(self.insns)

    def __len__(self) -> int:
        return len(self.insns)