"""scheduler — scripted cooperative interleaving over generator yield points.

Ports: (pyturso-specific — no Rust counterpart; inspired by io.StepDriver).
Phase: 11
Status: IMPLEMENTED (cooperative multi-connection scheduler for MVCC scenarios).

The scheduler drives multiple connections cooperatively in a single thread.
It takes a list of "steps" — each step specifies which connection to advance
and what action to take (begin, read, write, commit, abort). This is the
scripted-interleaving DSL for MVCC scenario tests.

The scheduler is intentionally simple: no threads, no locks — the test
script controls the exact interleaving, making scenarios reproducible and
deterministic.
"""

from __future__ import annotations
# mypy: disable-error-code="assignment"
# mypy: disable-error-code="unused-ignore"

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyturso.mvcc.tx import Transaction, TransactionManager
from pyturso.mvcc.versions import VersionedTable
from pyturso.types.value import Value

__all__ = ["StepAction", "ScheduleStep", "Scheduler", "ScheduleResult"]


class StepAction(str, Enum):
    """Actions a schedule step can take."""
    BEGIN = "begin"
    READ = "read"
    WRITE = "write"
    COMMIT = "commit"
    ABORT = "abort"


@dataclass
class ScheduleStep:
    """One step in a schedule: which connection, what action, what args."""
    conn_id: int
    action: StepAction
    rowid: int = 0
    values: tuple[Value, ...] = ()


@dataclass
class ScheduleResult:
    """The result of running a schedule."""
    committed_txs: list[int] = field(default_factory=list)
    aborted_txs: list[int] = field(default_factory=list)
    read_results: dict[int, list[tuple[Value, ...] | None]] = field(default_factory=dict)


class Scheduler:
    """Cooperative MVCC scenario scheduler.

    Drives multiple connections through a scripted interleaving. Each
    connection has its own transaction; the scheduler advances them step by
    step, recording results.
    """

    def __init__(self, table: VersionedTable) -> None:
        self._table = table
        self._tx_mgr = TransactionManager()
        self._txs: dict[int, Transaction] = {}  # conn_id → current tx
        self._result = ScheduleResult()

    @property
    def tx_manager(self) -> TransactionManager:
        return self._tx_mgr

    def run(self, steps: list[ScheduleStep]) -> ScheduleResult:
        """Run a schedule of steps and return the result."""
        for step in steps:
            if step.action is StepAction.BEGIN:
                tx = self._tx_mgr.begin()
                self._txs[step.conn_id] = tx
            elif step.action is StepAction.READ:
                tx = self._txs.get(step.conn_id)
                if tx is not None:
                    self._tx_mgr.record_read(tx, step.rowid)
                    # Read the visible version.
                    chain = self._table.get_chain(step.rowid)
                    visible_row = None
                    if chain is not None:
                        from pyturso.mvcc.visibility import visible
                        # Include tx_id=0 as committed at seq 0 (initial data).
                        commits = dict(self._tx_mgr.commit_timestamps)
                        commits[0] = 0
                        for version in reversed(chain.versions):
                            if visible(version, tx.snapshot_id, tx.tx_id, commits):
                                visible_row = version.values
                                break
                    self._result.read_results.setdefault(step.conn_id, []).append(visible_row)
            elif step.action is StepAction.WRITE:
                tx = self._txs.get(step.conn_id)
                if tx is not None:
                    self._tx_mgr.record_write(tx, step.rowid)
                    # Write the version (not committed yet).
                    self._table.update(step.rowid, step.values, tx.tx_id, committed=False)
            elif step.action is StepAction.COMMIT:
                tx = self._txs.get(step.conn_id)
                if tx is not None:
                    success = self._tx_mgr.commit(tx)
                    if success:
                        # Mark the tx's versions as committed.
                        for chain in self._table.chains.values():
                            for version in chain.versions:
                                if version.created_by == tx.tx_id:
                                    version.is_committed_created = True
                                if version.deleted_by == tx.tx_id:
                                    version.is_committed_deleted = True
                        self._result.committed_txs.append(tx.tx_id)
                    else:
                        self._result.aborted_txs.append(tx.tx_id)
            elif step.action is StepAction.ABORT:
                tx = self._txs.get(step.conn_id)
                if tx is not None:
                    self._tx_mgr.abort(tx)
                    self._result.aborted_txs.append(tx.tx_id)
                    # Remove the tx's uncommitted versions.
                    for chain in self._table.chains.values():
                        chain.versions = [
                            v for v in chain.versions
                            if v.created_by != tx.tx_id
                        ]
                        # Restore deleted_by = None for versions this tx deleted.
                        for v in chain.versions:
                            if v.deleted_by == tx.tx_id:
                                v.deleted_by = None
                                v.is_committed_deleted = False

        return self._result