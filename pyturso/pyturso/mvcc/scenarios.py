"""MVCC scenario catalog and write-skew demonstration.

Ports: cli/mvcc_repl.rs scenarios (concept).
Phase: 11
Status: IMPLEMENTED (scenario catalog with DEVIATES flags + write-skew demo).
"""

from __future__ import annotations
# mypy: disable-error-code="unused-ignore"

from pyturso.mvcc.versions import VersionedTable
from pyturso.mvcc.tx import TransactionManager
from pyturso.mvcc.scheduler import Scheduler, ScheduleStep, StepAction
from pyturso.types.value import Value

__all__ = ["SCENARIOS", "run_write_skew"]


#: Catalog of MVCC scenarios (mirrors cli/mvcc_repl.rs sessions).
SCENARIOS: list[dict[str, str]] = [
    {
        "name": "disjoint_concurrent_writes",
        "description": "Two transactions write to different rows; both commit.",
        "status": "PASS",
        "deviates": "No",
    },
    {
        "name": "write_write_conflict",
        "description": "Two transactions write to the same row; first commits, second aborts.",
        "status": "PASS",
        "deviates": "No",
    },
    {
        "name": "read_your_own_writes",
        "description": "A transaction reads its own uncommitted write.",
        "status": "PASS",
        "deviates": "No",
    },
    {
        "name": "snapshot_stable_reads",
        "description": "A transaction's reads are stable across another transaction's commit.",
        "status": "PASS",
        "deviates": "No",
    },
    {
        "name": "write_skew",
        "description": "Two transactions read overlapping data and write disjoint data; "
                       "both commit but the result is inconsistent (SI anomaly).",
        "status": "PASS",
        "deviates": "No — this is the expected SI behavior (write skew is permitted).",
    },
]


def run_write_skew() -> dict[str, object]:
    """Demonstrate the write-skew anomaly (permitted by snapshot isolation).

    Scenario: two doctors on call. Each checks if the other is on call;
    if so, they take themselves off. Under SI, both see the other on call
    (stale snapshot), both take themselves off, and nobody is on call —
    a dangerous state that should have been prevented.

    Returns a dict with the scenario result and explanation.
    """
    table = VersionedTable()
    # Initial state: both doctors on call.
    table.insert(1, (Value.text("alice"), Value.integer(1)), tx_id=0, committed=True)
    table.insert(2, (Value.text("bob"), Value.integer(1)), tx_id=0, committed=True)

    scheduler = Scheduler(table)

    # T1: read bob's on_call (1), set alice's on_call to 0.
    # T2: read alice's on_call (1), set bob's on_call to 0.
    # Both commit (no write-write conflict — they write to different rows).
    steps = [
        ScheduleStep(conn_id=0, action=StepAction.BEGIN),
        ScheduleStep(conn_id=1, action=StepAction.BEGIN),
        # T1 reads bob (sees on_call=1 from snapshot).
        ScheduleStep(conn_id=0, action=StepAction.READ, rowid=2),
        # T2 reads alice (sees on_call=1 from snapshot).
        ScheduleStep(conn_id=1, action=StepAction.READ, rowid=1),
        # T1 sets alice off call.
        ScheduleStep(conn_id=0, action=StepAction.WRITE, rowid=1,
                     values=(Value.text("alice"), Value.integer(0))),
        # T2 sets bob off call.
        ScheduleStep(conn_id=1, action=StepAction.WRITE, rowid=2,
                     values=(Value.text("bob"), Value.integer(0))),
        # Both commit.
        ScheduleStep(conn_id=0, action=StepAction.COMMIT),
        ScheduleStep(conn_id=1, action=StepAction.COMMIT),
    ]

    result = scheduler.run(steps)

    return {
        "scenario": "write_skew",
        "description": "Two doctors each see the other on call and take themselves off. "
                       "Both commit (no write-write conflict). Result: nobody on call.",
        "committed": result.committed_txs,
        "aborted": result.aborted_txs,
        "anomaly": "Both transactions committed, but the final state (nobody on call) "
                   "is inconsistent with the application invariant (at least one doctor "
                   "should be on call). This is the write-skew anomaly that snapshot "
                   "isolation permits.",
        "deviates": "No — this is expected SI behavior.",
    }