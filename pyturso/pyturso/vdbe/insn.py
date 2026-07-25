"""insn — VDBE opcodes as per-opcode dataclasses; names mirror Rust verbatim.

Ports: core/vdbe/insn.rs (``Op`` enum).
Phase: 5
Status: IMPLEMENTED (starter ~15 opcodes).

Each opcode is a frozen dataclass with named fields that document its
semantics (the HOWTO says one dataclass per opcode beats a generic 5-operand
struct). Names mirror the Rust ``Op`` variants verbatim so cross-reading
``execute.rs`` stays mechanical.

A branch target (``target_pc`` / ``pc_if_empty`` / ``pc_if_next``) is an
``int``: a resolved address, or ``-1`` for an unresolved label (the builder
backpatches it). A negative value other than -1 is not valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

__all__ = [
    "Insn",
    "Init", "Transaction", "OpenRead", "Rewind", "Column", "Rowid",
    "ResultRow", "Next", "Halt", "Integer", "Real", "String8", "Null",
    "Eq", "Ne", "Lt", "Le", "Gt", "Ge", "Goto",
]

#: Unresolved label sentinel — the builder backpatches this to a real address.
UNRESOLVED: int = -1


@dataclass(frozen=True)
class Init:
    """Jump to ``target_pc`` to start the program (skip the prologue)."""
    target_pc: int = UNRESOLVED


@dataclass(frozen=True)
class Transaction:
    """Begin a transaction on database 0 (the main database)."""
    db: int = 0
    write: int = 0  # 1 for write transaction


@dataclass(frozen=True)
class OpenRead:
    """Open cursor ``cursor_id`` on the B-tree rooted at ``root_page``."""
    cursor_id: int
    root_page: int
    db: int = 0


@dataclass(frozen=True)
class Rewind:
    """Move cursor ``cursor_id`` to the first row; jump to ``pc_if_empty`` if empty."""
    cursor_id: int
    pc_if_empty: int = UNRESOLVED


@dataclass(frozen=True)
class Column:
    """Read column ``column`` from cursor ``cursor_id`` into register ``dest``."""
    cursor_id: int
    column: int
    dest: int


@dataclass(frozen=True)
class Rowid:
    """Read the rowid of cursor ``cursor_id`` into register ``dest``."""
    cursor_id: int
    dest: int


@dataclass(frozen=True)
class ResultRow:
    """Emit registers ``start_reg`` .. ``start_reg + count - 1`` as a result row."""
    start_reg: int
    count: int


@dataclass(frozen=True)
class Next:
    """Advance cursor ``cursor_id``; jump to ``pc_if_next`` if a row is available."""
    cursor_id: int
    pc_if_next: int = UNRESOLVED


@dataclass(frozen=True)
class Halt:
    """Stop the program with ``err_code`` (0 = success)."""
    err_code: int = 0
    description: str = ""


@dataclass(frozen=True)
class Integer:
    """Load integer ``value`` into register ``dest``."""
    value: int
    dest: int


@dataclass(frozen=True)
class Real:
    """Load float ``value`` into register ``dest``."""
    value: float
    dest: int


@dataclass(frozen=True)
class String8:
    """Load string ``value`` into register ``dest``."""
    value: str
    dest: int


@dataclass(frozen=True)
class Null:
    """Load NULL into register ``dest`` (and ``dest_end``..``dest`` if set)."""
    dest: int
    dest_end: int = -1  # -1 = single register


@dataclass(frozen=True)
class Goto:
    """Unconditional jump to ``target_pc``."""
    target_pc: int = UNRESOLVED


# --- comparison opcodes ---
# All comparisons: compare r[lhs] with r[rhs], jump to target_pc if the
# condition is true. flags: jump_if_null (jump if either operand is NULL).
# For Phase 5, flags is a simple bool; Phase 6 adds nulleq.

@dataclass(frozen=True)
class Eq:
    """Jump to ``target_pc`` if r[lhs] == r[rhs]."""
    lhs: int
    rhs: int
    target_pc: int = UNRESOLVED
    jump_if_null: bool = False


@dataclass(frozen=True)
class Ne:
    """Jump to ``target_pc`` if r[lhs] != r[rhs]."""
    lhs: int
    rhs: int
    target_pc: int = UNRESOLVED
    jump_if_null: bool = False


@dataclass(frozen=True)
class Lt:
    """Jump to ``target_pc`` if r[lhs] < r[rhs]."""
    lhs: int
    rhs: int
    target_pc: int = UNRESOLVED
    jump_if_null: bool = False


@dataclass(frozen=True)
class Le:
    """Jump to ``target_pc`` if r[lhs] <= r[rhs]."""
    lhs: int
    rhs: int
    target_pc: int = UNRESOLVED
    jump_if_null: bool = False


@dataclass(frozen=True)
class Gt:
    """Jump to ``target_pc`` if r[lhs] > r[rhs]."""
    lhs: int
    rhs: int
    target_pc: int = UNRESOLVED
    jump_if_null: bool = False


@dataclass(frozen=True)
class Ge:
    """Jump to ``target_pc`` if r[lhs] >= r[rhs]."""
    lhs: int
    rhs: int
    target_pc: int = UNRESOLVED
    jump_if_null: bool = False


# --- logical / null-test opcodes ---

@dataclass(frozen=True)
class IsNull:
    """Jump to target_pc if r[reg] is NULL."""
    reg: int
    target_pc: int = UNRESOLVED

@dataclass(frozen=True)
class NotNull:
    """Jump to target_pc if r[reg] is NOT NULL."""
    reg: int
    target_pc: int = UNRESOLVED


# --- arithmetic opcodes ---

@dataclass(frozen=True)
class Add:
    """r[dest] = r[r1] + r[r2]."""
    r1: int
    r2: int
    dest: int

@dataclass(frozen=True)
class Subtract:
    """r[dest] = r[r1] - r[r2]."""
    r1: int
    r2: int
    dest: int

@dataclass(frozen=True)
class Multiply:
    """r[dest] = r[r1] * r[r2]."""
    r1: int
    r2: int
    dest: int

@dataclass(frozen=True)
class Divide:
    """r[dest] = r[r1] / r[r2] (NULL if r2 == 0)."""
    r1: int
    r2: int
    dest: int

@dataclass(frozen=True)
class Remainder:
    """r[dest] = r[r1] % r[r2] (NULL if r2 == 0)."""
    r1: int
    r2: int
    dest: int

@dataclass(frozen=True)
class Concat:
    """r[dest] = r[r1] || r[r2] (string concatenation)."""
    r1: int
    r2: int
    dest: int


@dataclass(frozen=True)
class Copy:
    """Copy r[src] to r[dest] (and dest_end..dest if range)."""
    src: int
    dest: int
    dest_end: int = -1  # -1 = single register


# --- write opcodes (Phase 7) ---

@dataclass(frozen=True)
class OpenWrite:
    """Open cursor cursor_id for writing on the B-tree at root_page."""
    cursor_id: int
    root_page: int
    db: int = 0

@dataclass(frozen=True)
class NewRowid:
    """Allocate a new rowid for cursor cursor_id into r[dest]."""
    cursor_id: int
    dest: int

@dataclass(frozen=True)
class MakeRecord:
    """Build a record from r[start_reg..start_reg+count-1] into r[dest]."""
    start_reg: int
    count: int
    dest: int

@dataclass(frozen=True)
class Insert:
    """Insert the record in r[record_reg] with rowid r[rowid_reg] into cursor."""
    cursor_id: int
    rowid_reg: int
    record_reg: int


# --- function call opcode ---

@dataclass(frozen=True)
class Function:
    """Call scalar function name with n_args args from r[start_reg..];
    result into r[dest]."""
    name: str
    start_reg: int
    n_args: int
    dest: int


#: The union of all instruction types.
Insn = Union[
    Init, Transaction, OpenRead, Rewind, Column, Rowid,
    ResultRow, Next, Halt, Integer, Real, String8, Null,
    Eq, Ne, Lt, Le, Gt, Ge, Goto,
    Add, Subtract, Multiply, Divide, Remainder, Concat,
    IsNull, NotNull, Copy, OpenWrite, NewRowid, MakeRecord, Insert,
    Function,
    Add, Subtract, Multiply, Divide, Remainder, Concat,
    IsNull, NotNull, Copy, OpenWrite, NewRowid, MakeRecord, Insert,
    Function,
]