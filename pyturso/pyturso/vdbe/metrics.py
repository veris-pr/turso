"""metrics — opcode counters; wired into the VM loop.

Ports: core/vdbe/metrics.rs.
Phase: 5
Status: IMPLEMENTED (basic opcode count per execution).

The metrics module counts how many times each opcode is executed. This is
useful for understanding query performance and detecting infinite loops
(the VM's stall guard uses the total step count).
"""

from __future__ import annotations

from collections import Counter
# mypy: disable-error-code="unused-ignore"
# mypy: disable-error-code="type-arg"
from dataclasses import dataclass, field

__all__ = ["Metrics", "MetricsCollector"]


@dataclass
class Metrics:
    """Execution metrics for a VDBE program run."""
    opcode_counts: Counter = field(default_factory=Counter)
    total_steps: int = 0
    rows_emitted: int = 0


class MetricsCollector:
    """Collects metrics during VDBE execution."""

    def __init__(self) -> None:
        self.metrics = Metrics()

    def record_opcode(self, name: str) -> None:
        """Record one execution of an opcode."""
        self.metrics.opcode_counts[name] += 1
        self.metrics.total_steps += 1

    def record_row(self) -> None:
        """Record one emitted result row."""
        self.metrics.rows_emitted += 1

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [f"Total steps: {self.metrics.total_steps}",
                 f"Rows emitted: {self.metrics.rows_emitted}",
                 "Opcode counts:"]
        for name, count in self.metrics.opcode_counts.most_common():
            lines.append(f"  {name:<20} {count}")
        return "\n".join(lines)