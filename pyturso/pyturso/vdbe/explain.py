"""explain — EXPLAIN-format listing, diffable against tursodb.

Ports: core/vdbe/explain.rs (``explain`` function).
Phase: 5
Status: IMPLEMENTED.

Formats a :class:`pyturso.vdbe.program.Program` as a human-readable listing
matching the SQLite/tursodb ``EXPLAIN`` output format: one line per
instruction with ``addr  opcode  p1  p2  p3  p4  comment``. This is what
``tools/explain_diff.py`` (#TODO) aligns against tursodb's output.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields

from pyturso.vdbe.insn import Insn
from pyturso.vdbe.program import Program

__all__ = ["explain"]


def explain(program: Program) -> str:
    """Format ``program`` as an EXPLAIN listing (one line per instruction).

    The format mirrors tursodb's ``EXPLAIN`` output:
    ``addr  opcode  p1  p2  p3  p4  comment``
    where p1..p4 are the instruction's fields in declaration order.
    """
    lines: list[str] = []
    for addr, insn in enumerate(program.insns):
        name = type(insn).__name__
        f = dataclass_fields(insn)
        vals = [getattr(insn, field.name) for field in f]
        # Map fields to p1..p4 (first 4 fields; extra fields become comments).
        p = []
        for v in vals[:4]:
            if isinstance(v, str):
                p.append(v)
            elif v is None:
                p.append("")
            else:
                p.append(str(v))
        while len(p) < 4:
            p.append("")
        comment = ""
        if len(vals) > 4:
            comment = " ".join(str(v) for v in vals[4:])
        line = f"{addr:<4} {name:<14} {p[0]:<6} {p[1]:<6} {p[2]:<6} {p[3]:<8} {comment}".rstrip()
        lines.append(line)
    return "\n".join(lines) + "\n"