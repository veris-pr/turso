"""visibility — snapshot visibility predicate.

Ports: core/mvcc/ (concept — snapshot isolation visibility rules).
Phase: 11
Status: IMPLEMENTED (pure function + truth-table tests).

The visibility predicate determines whether a row version is visible to a
transaction reading at a given snapshot. The rules (snapshot isolation):

  1. A version is visible if its ``created_by`` transaction has committed
     AND the commit happened at or before the snapshot point.
  2. A version is NOT visible if its ``deleted_by`` transaction has committed
     AND the delete happened at or before the snapshot point.
  3. A version created by the current transaction is always visible
     (read-your-own-writes), even if not yet committed.
  4. A version deleted by the current transaction is NOT visible
     (the transaction sees its own deletes).

The snapshot point is identified by a ``snapshot_id`` — a monotonically
increasing commit sequence number. Each transaction captures the current
snapshot_id at BEGIN time.
"""

from __future__ import annotations

from pyturso.mvcc.versions import RowVersion

__all__ = ["visible"]


def visible(
    version: RowVersion,
    snapshot_id: int,
    tx_id: int,
    commit_timestamps: dict[int, int],
) -> bool:
    """Determine if ``version`` is visible to ``tx_id`` at ``snapshot_id``.

    Args:
        version: the row version to check.
        snapshot_id: the snapshot point (commit sequence number at BEGIN).
        tx_id: the ID of the reading transaction.
        commit_timestamps: a map of tx_id → commit_timestamp (the snapshot_id
            at which that transaction committed). Transactions not in this
            map have not committed.

    Returns:
        True if the version is visible to the transaction.
    """
    # Rule 3: read-your-own-writes — a version created by the current tx
    # is always visible, even if not committed.
    if version.created_by == tx_id:
        # Rule 4: but if the current tx deleted it, it's not visible.
        if version.deleted_by == tx_id:
            return False
        return True

    # Rule 1: the creating transaction must have committed at or before the snapshot.
    created_commit = commit_timestamps.get(version.created_by)
    if created_commit is None:
        return False  # creator hasn't committed
    if not version.is_committed_created:
        return False  # marked as not committed
    if created_commit > snapshot_id:
        return False  # committed after our snapshot

    # Rule 2: the deleting transaction must NOT have committed at or before
    # the snapshot. If it did, the version is invisible (it was deleted).
    if version.deleted_by is not None:
        if version.deleted_by == tx_id:
            return False  # we deleted it → not visible
        deleted_commit = commit_timestamps.get(version.deleted_by)
        if deleted_commit is not None and version.is_committed_deleted:
            if deleted_commit <= snapshot_id:
                return False  # delete committed before our snapshot → invisible

    return True