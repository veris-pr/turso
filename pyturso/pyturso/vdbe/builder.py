"""builder — ProgramBuilder: append, labels + backpatching, register allocation.

Ports: core/vdbe/builder.rs (``ProgramBuilder``).
Phase: 5
Status: IMPLEMENTED.

The builder assembles a :class:`pyturso.vdbe.program.Program` incrementally:
append instructions, allocate labels (forward references), backpatch them
when the target address is known, and allocate registers (bump allocator).

Label lifecycle:
  1. ``label = builder.alloc_label()`` — returns an int label ID.
  2. Instructions reference it via ``target_pc=Builder.UNRESOLVED`` with
     ``label=label``. Actually, pyturso simplifies: labels are just ints
     that will be resolved to addresses. The builder stores pending patches.
  3. ``builder.resolve(label)`` — records the current address as the label's
     target and backpatches all instructions that reference it.
  4. ``finalize()`` — asserts no unresolved labels remain, returns the
     ``Program``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, cast

from pyturso.vdbe.insn import (
    UNRESOLVED, Eq, Ge, Goto, Gt, Halt, Init, Insn, Integer, Le, Lt, Ne,
    Next, Null, OpenRead, Real, ResultRow, Rewind, Rowid, String8,
    Transaction, Column,
)
from pyturso.vdbe.program import Program

__all__ = ["ProgramBuilder"]


# Fields that hold branch targets (for backpatching).
_BRANCH_FIELDS: dict[type, str] = {
    Init: "target_pc",
    Rewind: "pc_if_empty",
    Next: "pc_if_next",
    Goto: "target_pc",
    Eq: "target_pc",
    Ne: "target_pc",
    Lt: "target_pc",
    Le: "target_pc",
    Gt: "target_pc",
    Ge: "target_pc",
}


class ProgramBuilder:
    """Assembles a VDBE program with labels and register allocation.

    Usage::

        b = ProgramBuilder()
        start = b.alloc_label()
        b.emit(Init(target_pc=UNRESOLVED))  # will be patched to `start`
        b.emit(OpenRead(cursor_id=0, root_page=2))
        b.resolve(start)  # now `start` = current address
        ...
        program = b.finalize()
    """

    def __init__(self) -> None:
        self._insns: list[Insn] = []
        self._n_registers: int = 1  # r[0] is reserved (unused, like SQLite)
        self._n_cursors: int = 0
        # Label → list of (insn_index, field_name) for backpatching.
        self._pending: dict[int, list[tuple[int, str]]] = {}
        # Label → resolved address.
        self._resolved: dict[int, int] = {}
        self._next_label: int = 0

    # --- register allocation ---
    def alloc_register(self) -> int:
        """Allocate a single register; return its index."""
        r = self._n_registers
        self._n_registers += 1
        return r

    def alloc_registers(self, n: int) -> int:
        """Allocate ``n`` contiguous registers; return the first index."""
        r = self._n_registers
        self._n_registers += n
        return r

    @property
    def n_registers(self) -> int:
        return self._n_registers

    # --- cursor allocation ---
    def alloc_cursor(self) -> int:
        """Allocate a cursor ID; return it."""
        c = self._n_cursors
        self._n_cursors += 1
        return c

    @property
    def n_cursors(self) -> int:
        return self._n_cursors

    # --- labels ---
    def alloc_label(self) -> int:
        """Allocate a label ID (a forward reference to an address)."""
        lbl = self._next_label
        self._next_label += 1
        return lbl

    def resolve(self, label: int) -> int:
        """Mark the current address as the target of ``label``.

        Backpatches all pending instructions that reference this label.
        Returns the resolved address.
        """
        addr = len(self._insns)
        self._resolved[label] = addr
        for insn_idx, field_name in self._pending.pop(label, []):
            insn = self._insns[insn_idx]
            new_insn = replace(insn, **{field_name: addr})  # type: ignore[arg-type]  # type: ignore[arg-type]
            self._insns[insn_idx] = new_insn
        return addr

    @property
    def current_address(self) -> int:
        """The address the next emitted instruction will get."""
        return len(self._insns)

    # --- emit ---
    def emit(self, insn: Insn, *, label: int | None = None) -> int:
        """Append insn to the program; return its address.

        If label is given, backpatch the branch field if the label is already
        resolved; otherwise track it for later backpatching.
        """
        addr = len(self._insns)
        self._insns.append(insn)
        if label is not None:
            field_name = _BRANCH_FIELDS.get(type(insn))
            if field_name is not None:
                if label in self._resolved:
                    self._insns[addr] = replace(
                        insn, **{field_name: self._resolved[label]}  # type: ignore[arg-type]
                    )
                else:
                    self._pending.setdefault(label, []).append((addr, field_name))
        return addr

    # --- finalize ---
    def finalize(self, sql: str = "") -> Program:
        """Build the final ``Program``, asserting no unresolved labels."""
        for lbl, patches in self._pending.items():
            if patches:
                raise AssertionError(
                    f"label {lbl} has {len(patches)} unresolved patch(es) "
                    f"at finalize"
                )
        return Program(
            insns=list(self._insns),
            n_registers=self._n_registers,
            n_cursors=self._n_cursors,
            sql=sql,
        )