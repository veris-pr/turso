"""versions — row-version chains stamped with transaction ids.

Ports: core/mvcc/database/ (concept — row version model).
Phase: 11
Status: IMPLEMENTED (row-version chains for MVCC snapshot isolation).

In Turso's MVCC, each row has a chain of versions. Each version is a record
stamped with the transaction that created it (``created_by``) and the
transaction that deleted it (``deleted_by``, or ``None`` if still alive).
A version is visible to a transaction if its ``created_by`` is committed
and visible in the transaction's snapshot, and its ``deleted_by`` is not
committed or not visible in the snapshot.

The version chain is the foundation: everything else (visibility, tx, scheduler)
sits on this data model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyturso.types.value import Value

__all__ = ["RowVersion", "VersionChain", "VersionedTable"]


@dataclass
class RowVersion:
    """One version of a row in the version chain.

    Attributes:
        created_by: the transaction ID that created this version.
        deleted_by: the transaction ID that deleted this version (or None).
        is_committed_created: whether created_by has committed.
        is_committed_deleted: whether deleted_by has committed (if deleted_by is not None).
        values: the row's values for this version.
    """
    created_by: int
    deleted_by: int | None
    is_committed_created: bool
    is_committed_deleted: bool
    values: tuple[Value, ...]


@dataclass
class VersionChain:
    """The chain of versions for one row (keyed by rowid)."""
    rowid: int
    versions: list[RowVersion] = field(default_factory=list)

    def add_version(self, version: RowVersion) -> None:
        """Add a new version to the chain."""
        self.versions.append(version)

    def delete_current(self, tx_id: int, committed: bool = False) -> None:
        """Mark the current live version as deleted by tx_id."""
        for v in reversed(self.versions):
            if v.deleted_by is None and v.is_committed_created:
                v.deleted_by = tx_id
                v.is_committed_deleted = committed
                return


@dataclass
class VersionedTable:
    """A table with MVCC version chains for each row."""
    chains: dict[int, VersionChain] = field(default_factory=dict)

    def get_chain(self, rowid: int) -> VersionChain | None:
        return self.chains.get(rowid)

    def get_or_create_chain(self, rowid: int) -> VersionChain:
        if rowid not in self.chains:
            self.chains[rowid] = VersionChain(rowid=rowid)
        return self.chains[rowid]

    def insert(self, rowid: int, values: tuple[Value, ...], tx_id: int,
               committed: bool = False) -> None:
        """Insert a new row with an initial version."""
        chain = self.get_or_create_chain(rowid)
        chain.add_version(RowVersion(
            created_by=tx_id,
            deleted_by=None,
            is_committed_created=committed,
            is_committed_deleted=False,
            values=values,
        ))

    def update(self, rowid: int, values: tuple[Value, ...], tx_id: int,
               committed: bool = False) -> None:
        """Update a row: delete the old version, insert a new one."""
        chain = self.get_chain(rowid)
        if chain is not None:
            chain.delete_current(tx_id, committed)
        self.insert(rowid, values, tx_id, committed)

    def delete(self, rowid: int, tx_id: int, committed: bool = False) -> None:
        """Delete a row: mark the current version as deleted."""
        chain = self.get_chain(rowid)
        if chain is not None:
            chain.delete_current(tx_id, committed)