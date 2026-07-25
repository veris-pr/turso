"""MVCC visibility rules reference doc + two-connection differential mode stub."""

from __future__ import annotations

# This module provides the visibility rules reference and a stub for
# the two-connection differential mode.

__all__ = ["VISIBILITY_RULES", "TwoConnectionMode"]


#: The visibility rules as a truth table (ports core/mvcc/ visibility logic).
VISIBILITY_RULES: list[dict[str, str]] = [
    {
        "rule": "1. Created by committed tx before snapshot",
        "condition": "version.created_by has committed AND commit_seq <= snapshot_id",
        "visible": "Yes",
    },
    {
        "rule": "2. Created by current tx (read-your-own-writes)",
        "condition": "version.created_by == tx_id AND version.deleted_by != tx_id",
        "visible": "Yes",
    },
    {
        "rule": "3. Deleted by committed tx before snapshot",
        "condition": "version.deleted_by has committed AND commit_seq <= snapshot_id",
        "visible": "No (version is invisible)",
    },
    {
        "rule": "4. Deleted by current tx",
        "condition": "version.deleted_by == tx_id",
        "visible": "No (we see our own deletes)",
    },
    {
        "rule": "5. Created by uncommitted tx (not current)",
        "condition": "version.created_by has NOT committed",
        "visible": "No (dirty reads not allowed)",
    },
    {
        "rule": "6. Deleted by tx after snapshot",
        "condition": "version.deleted_by committed but commit_seq > snapshot_id",
        "visible": "Yes (delete not visible to us)",
    },
]


class TwoConnectionMode:
    """Stub for the two-connection differential mode (Phase 11).

    The two-connection mode runs two connections cooperatively through
    scripted interleavings, comparing outcomes against turso's MVCC behavior.
    This is the Phase 11 differential harness extension.
    """

    def __init__(self) -> None:
        self.scenarios: list[dict[str, str]] = []

    def add_scenario(self, name: str, description: str, expected: str) -> None:
        """Add a scenario to the two-connection mode."""
        self.scenarios.append({
            "name": name,
            "description": description,
            "expected": expected,
            "status": "PLANNED",
        })

    def run_all(self) -> list[dict[str, str]]:
        """Run all scenarios (stub — returns the catalog)."""
        return self.scenarios