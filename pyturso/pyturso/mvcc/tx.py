"""tx — begin/commit/abort, first-committer-wins conflict detection.

Ports: core/mvcc/ (concept — transaction state, write-write conflict).
Phase: 11
Status: IMPLEMENTED (begin with snapshot capture, read/write sets,
first-committer-wins conflict check at commit, abort).

Transaction lifecycle:
  1. ``begin()`` → captures the current snapshot_id (commit sequence number).
  2. ``read(rowid)`` → records the rowid in the read set.
  3. ``write(rowid, values)`` → records the rowid in the write set.
  4. ``commit()`` → checks write-write conflicts (first-committer-wins):
     if another transaction has already committed a write to any row in the
     write set since this transaction's snapshot, the commit fails.
  5. ``abort()`` → rolls back (discards the transaction's versions).

First-committer-wins: if two transactions T1 and T2 both write to the same
row and T1 commits first, T2's commit fails (its snapshot is stale for that
row). This is the snapshot isolation write-write conflict rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyturso.types.value import Value

__all__ = ["Transaction", "TransactionManager"]


@dataclass
class Transaction:
    """An MVCC transaction.

    Attributes:
        tx_id: unique transaction ID.
        snapshot_id: the commit sequence number at BEGIN time.
        read_set: rowids read by this transaction.
        write_set: rowids written by this transaction.
        committed: whether the transaction has committed.
        aborted: whether the transaction has aborted.
    """
    tx_id: int
    snapshot_id: int
    read_set: set[int] = field(default_factory=set)
    write_set: set[int] = field(default_factory=set)
    committed: bool = False
    aborted: bool = False


class TransactionManager:
    """Manages transaction IDs, commit sequence, and conflict detection.

    The manager tracks the global commit sequence number and the committed
    transactions. It assigns transaction IDs and validates commits.
    """

    def __init__(self) -> None:
        self._next_tx_id: int = 1
        self._next_commit_seq: int = 0  # the last committed sequence number
        self._transactions: dict[int, Transaction] = {}
        self._commit_timestamps: dict[int, int] = {}  # tx_id → commit_seq
        # Track which tx has written to which rowid.
        self._write_history: dict[int, list[int]] = {}  # rowid → [tx_ids that committed writes]

    @property
    def current_snapshot(self) -> int:
        """The current commit sequence number (the snapshot for new transactions)."""
        return self._next_commit_seq

    def begin(self) -> Transaction:
        """Start a new transaction. Captures the current snapshot."""
        tx = Transaction(tx_id=self._next_tx_id, snapshot_id=self._next_commit_seq)
        self._transactions[tx.tx_id] = tx
        self._next_tx_id += 1
        return tx

    def record_read(self, tx: Transaction, rowid: int) -> None:
        """Record a read in the transaction's read set."""
        tx.read_set.add(rowid)

    def record_write(self, tx: Transaction, rowid: int) -> None:
        """Record a write in the transaction's write set."""
        tx.write_set.add(rowid)

    def commit(self, tx: Transaction) -> bool:
        """Attempt to commit a transaction.

        Returns True if committed, False if a write-write conflict was detected
        (first-committer-wins). On conflict, the transaction is aborted.
        """
        if tx.committed or tx.aborted:
            return False

        # Check write-write conflicts: for each rowid in the write set,
        # check if any transaction committed a write to it after our snapshot.
        for rowid in tx.write_set:
            history = self._write_history.get(rowid, [])
            for committing_tx_id in history:
                commit_seq = self._commit_timestamps.get(committing_tx_id, 0)
                if commit_seq > tx.snapshot_id:
                    # Another transaction committed a write to this row after
                    # our snapshot → write-write conflict.
                    self.abort(tx)
                    return False

        # Commit: assign the next commit sequence number.
        self._next_commit_seq += 1
        tx.committed = True
        self._commit_timestamps[tx.tx_id] = self._next_commit_seq

        # Record the write in the write history.
        for rowid in tx.write_set:
            self._write_history.setdefault(rowid, []).append(tx.tx_id)

        return True

    def abort(self, tx: Transaction) -> None:
        """Abort a transaction (rollback)."""
        tx.aborted = True

    @property
    def commit_timestamps(self) -> dict[int, int]:
        """The commit timestamps map (for visibility checks)."""
        return self._commit_timestamps