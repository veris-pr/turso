"""Unit tests for Phase 11: MVCC versions, visibility, transactions, scheduler.

Tests the MVCC concept port: row versions, snapshot isolation visibility,
first-committer-wins conflict detection, and scripted interleaving scenarios.
"""

from __future__ import annotations
# mypy: disable-error-code="var-annotated"
# mypy: disable-error-code="unused-ignore"

import pytest

from pyturso.mvcc.versions import VersionedTable, RowVersion
from pyturso.mvcc.visibility import visible
from pyturso.mvcc.tx import TransactionManager
from pyturso.mvcc.scheduler import Scheduler, ScheduleStep, StepAction
from pyturso.types.value import Value


# --- versions ---
class TestVersions:
    def test_insert(self) -> None:
        table = VersionedTable()
        table.insert(1, (Value.text("alice"),), tx_id=1, committed=True)
        chain = table.get_chain(1)
        assert chain is not None
        assert len(chain.versions) == 1
        assert chain.versions[0].created_by == 1
        assert chain.versions[0].deleted_by is None

    def test_update(self) -> None:
        table = VersionedTable()
        table.insert(1, (Value.text("old"),), tx_id=1, committed=True)
        table.update(1, (Value.text("new"),), tx_id=2, committed=True)
        chain = table.get_chain(1)
        assert chain is not None
        assert len(chain.versions) == 2
        # Old version deleted by tx 2.
        assert chain.versions[0].deleted_by == 2
        # New version is live.
        assert chain.versions[1].deleted_by is None

    def test_delete(self) -> None:
        table = VersionedTable()
        table.insert(1, (Value.text("x"),), tx_id=1, committed=True)
        table.delete(1, tx_id=2, committed=True)
        chain = table.get_chain(1)
        assert chain is not None
        assert chain.versions[0].deleted_by == 2


# --- visibility ---
class TestVisibility:
    def _make_version(self, created_by: int, deleted_by: int | None = None,
                      committed_created: bool = True,
                      committed_deleted: bool = False) -> RowVersion:
        return RowVersion(
            created_by=created_by,
            deleted_by=deleted_by,
            is_committed_created=committed_created,
            is_committed_deleted=committed_deleted,
            values=(Value.text("x"),),
        )

    def test_visible_committed_before_snapshot(self) -> None:
        v = self._make_version(created_by=1, committed_created=True)
        commits = {1: 5}  # tx 1 committed at seq 5
        assert visible(v, snapshot_id=10, tx_id=2, commit_timestamps=commits)

    def test_invisible_committed_after_snapshot(self) -> None:
        v = self._make_version(created_by=1, committed_created=True)
        commits = {1: 15}  # committed after snapshot 10
        assert not visible(v, snapshot_id=10, tx_id=2, commit_timestamps=commits)

    def test_invisible_not_committed(self) -> None:
        v = self._make_version(created_by=1, committed_created=False)
        commits = {}
        assert not visible(v, snapshot_id=10, tx_id=2, commit_timestamps=commits)

    def test_read_your_own_writes(self) -> None:
        v = self._make_version(created_by=1, committed_created=False)
        commits = {}
        assert visible(v, snapshot_id=0, tx_id=1, commit_timestamps=commits)

    def test_deleted_by_committed_before_snapshot(self) -> None:
        v = self._make_version(created_by=1, deleted_by=2, committed_deleted=True)
        commits = {1: 5, 2: 8}  # created at 5, deleted at 8, snapshot at 10
        assert not visible(v, snapshot_id=10, tx_id=3, commit_timestamps=commits)

    def test_deleted_after_snapshot_still_visible(self) -> None:
        v = self._make_version(created_by=1, deleted_by=2, committed_deleted=True)
        commits = {1: 5, 2: 15}  # created at 5, deleted at 15, snapshot at 10
        assert visible(v, snapshot_id=10, tx_id=3, commit_timestamps=commits)

    def test_deleted_by_current_tx(self) -> None:
        v = self._make_version(created_by=1, deleted_by=2, committed_deleted=False)
        commits = {1: 5}
        assert not visible(v, snapshot_id=10, tx_id=2, commit_timestamps=commits)


# --- transaction manager ---
class TestTransactionManager:
    def test_begin_captures_snapshot(self) -> None:
        mgr = TransactionManager()
        tx1 = mgr.begin()
        assert tx1.snapshot_id == 0
        # Commit tx1 → snapshot advances.
        mgr.record_write(tx1, rowid=1)
        assert mgr.commit(tx1) is True
        tx2 = mgr.begin()
        assert tx2.snapshot_id == 1  # sees tx1's commit

    def test_first_committer_wins(self) -> None:
        """Two transactions write to the same row; first commits, second fails."""
        mgr = TransactionManager()
        tx1 = mgr.begin()
        tx2 = mgr.begin()  # same snapshot
        mgr.record_write(tx1, rowid=1)
        mgr.record_write(tx2, rowid=1)
        assert mgr.commit(tx1) is True  # first wins
        assert mgr.commit(tx2) is False  # second fails (conflict)
        assert tx2.aborted

    def test_disjoint_writes_both_commit(self) -> None:
        """Two transactions write to different rows; both commit."""
        mgr = TransactionManager()
        tx1 = mgr.begin()
        tx2 = mgr.begin()
        mgr.record_write(tx1, rowid=1)
        mgr.record_write(tx2, rowid=2)
        assert mgr.commit(tx1) is True
        assert mgr.commit(tx2) is True  # no conflict (different rows)

    def test_abort(self) -> None:
        mgr = TransactionManager()
        tx = mgr.begin()
        mgr.abort(tx)
        assert tx.aborted
        assert mgr.commit(tx) is False  # already aborted


# --- scheduler scenarios ---
class TestSchedulerScenarios:
    def test_read_your_own_writes(self) -> None:
        """T1 writes, then reads — should see its own write."""
        table = VersionedTable()
        table.insert(1, (Value.text("old"),), tx_id=0, committed=True)
        scheduler = Scheduler(table)
        steps = [
            ScheduleStep(conn_id=0, action=StepAction.BEGIN),
            ScheduleStep(conn_id=0, action=StepAction.WRITE, rowid=1, values=(Value.text("new"),)),
            ScheduleStep(conn_id=0, action=StepAction.READ, rowid=1),
            ScheduleStep(conn_id=0, action=StepAction.COMMIT),
        ]
        result = scheduler.run(steps)
        assert 1 in result.committed_txs
        assert result.read_results[0] == [(Value.text("new"),)]

    def test_snapshot_stable_across_foreign_commit(self) -> None:
        """T1 reads, T2 commits a new version, T1 reads again — sees the old version."""
        table = VersionedTable()
        table.insert(1, (Value.text("v1"),), tx_id=0, committed=True)
        scheduler = Scheduler(table)
        steps = [
            ScheduleStep(conn_id=0, action=StepAction.BEGIN),
            ScheduleStep(conn_id=0, action=StepAction.READ, rowid=1),  # sees v1
            ScheduleStep(conn_id=1, action=StepAction.BEGIN),
            ScheduleStep(conn_id=1, action=StepAction.WRITE, rowid=1, values=(Value.text("v2"),)),
            ScheduleStep(conn_id=1, action=StepAction.COMMIT),
            ScheduleStep(conn_id=0, action=StepAction.READ, rowid=1),  # still sees v1
            ScheduleStep(conn_id=0, action=StepAction.COMMIT),
        ]
        result = scheduler.run(steps)
        assert result.read_results[0] == [(Value.text("v1"),), (Value.text("v1"),)]

    def test_write_write_conflict(self) -> None:
        """Two transactions write to the same row; first commits, second fails."""
        table = VersionedTable()
        table.insert(1, (Value.text("v1"),), tx_id=0, committed=True)
        scheduler = Scheduler(table)
        steps = [
            ScheduleStep(conn_id=0, action=StepAction.BEGIN),
            ScheduleStep(conn_id=1, action=StepAction.BEGIN),
            ScheduleStep(conn_id=0, action=StepAction.WRITE, rowid=1, values=(Value.text("a"),)),
            ScheduleStep(conn_id=1, action=StepAction.WRITE, rowid=1, values=(Value.text("b"),)),
            ScheduleStep(conn_id=0, action=StepAction.COMMIT),
            ScheduleStep(conn_id=1, action=StepAction.COMMIT),
        ]
        result = scheduler.run(steps)
        assert len(result.committed_txs) == 1  # only one commits
        assert len(result.aborted_txs) == 1  # the other aborts

    def test_disjoint_concurrent_writes(self) -> None:
        """Two transactions write to different rows; both commit."""
        table = VersionedTable()
        table.insert(1, (Value.text("v1"),), tx_id=0, committed=True)
        table.insert(2, (Value.text("v2"),), tx_id=0, committed=True)
        scheduler = Scheduler(table)
        steps = [
            ScheduleStep(conn_id=0, action=StepAction.BEGIN),
            ScheduleStep(conn_id=1, action=StepAction.BEGIN),
            ScheduleStep(conn_id=0, action=StepAction.WRITE, rowid=1, values=(Value.text("a"),)),
            ScheduleStep(conn_id=1, action=StepAction.WRITE, rowid=2, values=(Value.text("b"),)),
            ScheduleStep(conn_id=0, action=StepAction.COMMIT),
            ScheduleStep(conn_id=1, action=StepAction.COMMIT),
        ]
        result = scheduler.run(steps)
        assert len(result.committed_txs) == 2  # both commit
        assert len(result.aborted_txs) == 0