"""errors — TursoError hierarchy; differential harness matches on these classes.

Ports: core/error.rs
Phase: 0
Status: IMPLEMENTED.

The exception hierarchy mirrors the Rust ``LimboError`` enum (and the nested
``CompletionError`` enum) from ``core/error.rs``. Each Rust variant becomes a
class; ``TursoError`` is the base (pyturso's documented name for ``LimboError``).
One pyturso-only addition, :class:`NotSupported`, carries the clean
"unsupported SQL" rejections the scope ledgers require — in Rust these are
emitted as ``ParseError``; pyturso keeps them as a distinct class so the
differential harness can tell "engine doesn't do X" from "syntax is wrong".

The second half of this module is the **error → comparison-class** mapping
table the differential harness compares on. Errors are matched by *class*
(never message text); each pyturso class maps to one of the sqlite3-style
comparison-class strings (:data:`OPERATIONAL_ERROR`, :data:`INTEGRITY_ERROR`,
…). The mapping follows SQLite result-code → exception semantics and is
refined as the corpus exercises more cases (the harness itself is built in a
later Phase 0 TODO; this table is its input).
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# SQLite primary result codes ported from the tail of core/error.rs.
# Kept here (not in the vdbe module) because they classify the errors below;
# the differential harness keys off the *comparison class*, but these codes
# document *why* a class maps where it does.
# ---------------------------------------------------------------------------
SQLITE_ERROR: Final[int] = 1
SQLITE_BUSY: Final[int] = 5
SQLITE_FULL: Final[int] = 13
SQLITE_CONSTRAINT: Final[int] = 19
# Extended constraint codes (primary | (code << 8)).
SQLITE_CONSTRAINT_CHECK: Final[int] = SQLITE_CONSTRAINT | (1 << 8)
SQLITE_CONSTRAINT_FOREIGNKEY: Final[int] = SQLITE_CONSTRAINT | (3 << 8)
SQLITE_CONSTRAINT_NOTNULL: Final[int] = SQLITE_CONSTRAINT | (5 << 8)
SQLITE_CONSTRAINT_PRIMARYKEY: Final[int] = SQLITE_CONSTRAINT | (6 << 8)
SQLITE_CONSTRAINT_TRIGGER: Final[int] = SQLITE_CONSTRAINT | (7 << 8)
SQLITE_CONSTRAINT_UNIQUE: Final[int] = 2067  # SQLITE_CONSTRAINT | (4 << 8)


# ---------------------------------------------------------------------------
# Comparison-class strings the differential harness compares on.
# These mirror the public names of sqlite3's exception hierarchy so an
# ``-- expect-error: OperationalError`` case can be matched uniformly across
# engines.
# ---------------------------------------------------------------------------
OPERATIONAL_ERROR: Final[str] = "OperationalError"
INTEGRITY_ERROR: Final[str] = "IntegrityError"
DATABASE_ERROR: Final[str] = "DatabaseError"
PROGRAMMING_ERROR: Final[str] = "ProgrammingError"
DATA_ERROR: Final[str] = "DataError"
INTERNAL_ERROR: Final[str] = "InternalError"
NOT_SUPPORTED_ERROR: Final[str] = "NotSupportedError"
INTERFACE_ERROR: Final[str] = "InterfaceError"

#: Every comparison class the harness may see, in one place for validation.
COMPARISON_CLASSES: Final[frozenset[str]] = frozenset(
    {
        OPERATIONAL_ERROR,
        INTEGRITY_ERROR,
        DATABASE_ERROR,
        PROGRAMMING_ERROR,
        DATA_ERROR,
        INTERNAL_ERROR,
        NOT_SUPPORTED_ERROR,
        INTERFACE_ERROR,
    }
)


# ---------------------------------------------------------------------------
# TursoError hierarchy (ports core/error.rs `LimboError` + `CompletionError`).
# ---------------------------------------------------------------------------
class TursoError(Exception):
    """Base of the pyturso exception hierarchy; mirrors Rust ``LimboError``.

    Payload-bearing subclasses accept a ``detail`` string; the rendered
    message comes from the class-level :attr:`_template`. Fixed-message
    subclasses (no Rust payload) override :meth:`_format` to drop ``detail``.
    """

    #: ``str.format`` template using ``{detail}`` for the payload, if any.
    _template: str = "{detail}"

    def __init__(self, detail: str = "") -> None:
        # `detail` is the human payload (Rust ``String``/``usize`` rendered to
        # text). Fixed-message subclasses ignore it.
        self.detail: str = detail
        super().__init__(self._format())

    def _format(self) -> str:
        return self._template.format(detail=self.detail)

    def __str__(self) -> str:  # pragma: no cover - exercised via super().__init__
        return self._format()


class _FixedTursoError(TursoError):
    """A TursoError whose message is a constant (no Rust payload).

    Subclasses set :attr:`_template` to a literal string with no ``{detail}``
    placeholder; :meth:`_format` returns it verbatim so the unused ``detail``
    argument (default ``""``) never leaks into the message.
    """

    def _format(self) -> str:
        return self._template


# --- Corrupt / format errors (SQLITE_CORRUPT, SQLITE_NOTADB) ---------------
class Corrupt(TursoError):
    """Corrupt database file / out-of-bounds page access (SQLITE_CORRUPT)."""

    _template = "Corrupt database: {detail}"


class NotADB(_FixedTursoError):
    """File header is not a valid SQLite database (SQLITE_NOTADB)."""

    _template = "File is not a database"


class Page1NotAlloc(_FixedTursoError):
    """Page 1 missing during recovery — a corrupt/empty-state condition."""

    _template = (
        "Database is empty, header does not exist - page 1 should've been "
        "allocated before this"
    )


class InvalidBlobSize(TursoError):
    """A blob's on-disk size does not match its declared length.

    Mirrors ``LimboError::InvalidBlobSize(usize)``.
    """

    _template = "Invalid blob size, expected {detail}"

    def __init__(self, expected: int) -> None:
        self.expected: int = expected
        super().__init__(str(expected))


class BlobHandleExpired(_FixedTursoError):
    """An incremental-blob handle's row/table changed (SQLITE_ABORT)."""

    _template = "Runtime error: blob handle expired"


# --- Internal / resource errors -------------------------------------------
class InternalError(TursoError):
    """Engine invariant violation (SQLITE_INTERNAL)."""

    _template = "Internal error: {detail}"


class OutOfMemory(_FixedTursoError):
    """Allocation failure (SQLITE_NOMEM)."""

    _template = "Out of memory"


# --- Parse / lexer errors (SQLITE_ERROR → OperationalError in sqlite3) -----
class ParseError(TursoError):
    """SQL parse error. The parser module's positional error maps into this.

    sqlite3 reports syntax errors as ``OperationalError`` ("near ...: syntax
    error"), so the comparison class is :data:`OPERATIONAL_ERROR`.
    """

    _template = "Parse error: {detail}"


class LexerError(TursoError):
    """Lexer-level error ported from ``turso_parser::error::Error``.

    The parser module owns the rich positional lexer type; when it surfaces at
    the engine boundary it is normalised into this class.
    """

    _template = "Parse error: {detail}"


class InvalidDate(TursoError):
    """Unparseable date literal/argument."""

    _template = "Parse error: {detail}"


class InvalidTime(TursoError):
    """Unparseable time literal/argument."""

    _template = "Parse error: {detail}"


class InvalidModifier(TursoError):
    """Unparseable date/time modifier."""

    _template = "Modifier parsing error: {detail}"


# --- Conversion / data errors ---------------------------------------------
class ConversionError(TursoError):
    """A value could not be converted to the requested type."""

    _template = "Conversion error: {detail}"


class NullValue(_FixedTursoError):
    """A NULL was used where a value is required."""

    _template = "Null value"


class InvalidColumnType(_FixedTursoError):
    """A stored column type did not match what the engine expected."""

    _template = "invalid column type"


# --- Runtime / constraint errors (SQLITE_CONSTRAINT → IntegrityError) -----
class Constraint(TursoError):
    """Generic runtime constraint violation (SQLITE_CONSTRAINT)."""

    _template = "Runtime error: {detail}"


class ForeignKeyConstraint(TursoError):
    """A foreign-key constraint failed; carries ROLLBACK|FAIL resolution."""

    _template = "Runtime error: {detail}"


class IntegerOverflow(_FixedTursoError):
    """Integer arithmetic overflow (runtime)."""

    _template = "Runtime error: integer overflow"


class TooBig(_FixedTursoError):
    """String or blob exceeds the size limit (SQLITE_TOOBIG)."""

    _template = "Runtime error: string or blob too big"


class Raise(TursoError):
    """A trigger ``RAISE(ABORT|ROLLBACK|FAIL)`` fired.

    Mirrors ``LimboError::Raise(ResolveType, String)``: the first argument is
    the resolve-type name (e.g. ``"ROLLBACK"``) and the second is the user
    message; only the message reaches the rendered text.
    """

    _template = "Runtime error: {detail}"

    def __init__(self, resolve_type: str, message: str) -> None:
        self.resolve_type: str = resolve_type
        super().__init__(message)


class RaiseIgnore(_FixedTursoError):
    """A trigger ``RAISE(IGNORE)`` — suppresses the current row, not a client
    error, but represented in the enum for control-flow uniformity."""

    _template = "RaiseIgnore"


# --- Concurrency / locking / busy errors (SQLITE_BUSY, SQLITE_LOCKED) -----
class Busy(_FixedTursoError):
    """The database is busy (SQLITE_BUSY) — retryable via the busy handler."""

    _template = "Database is busy"


class TableLocked(_FixedTursoError):
    """A database table is locked (SQLITE_LOCKED)."""

    _template = "Runtime error: database table is locked"


class LockingError(TursoError):
    """A lower-level locking protocol failure."""

    _template = "Locking error: {detail}"


class StatementsInProgress(TursoError):
    """A transaction/savepoint op or 2nd write was rejected because another
    statement on the same connection is still in progress.

    Carries SQLITE_BUSY *semantics* but is not retryable in place (the Rust
    doc-comment spells this out); the payload names the rejected operation.
    """

    _template = "{detail} - SQL statements in progress"


class BusySnapshot(_FixedTursoError):
    """A read transaction's snapshot went stale mid-statement."""

    _template = (
        "Database snapshot is stale. You must rollback and retry the whole "
        "transaction."
    )


class Interrupt(_FixedTursoError):
    """Operation interrupted (SQLITE_INTERRUPT)."""

    _template = "interrupt"


class ReadOnly(_FixedTursoError):
    """An attempt to write a read-only resource (SQLITE_READONLY)."""

    _template = "Error: Resource is read-only"


class DatabaseFull(TursoError):
    """The database is full (SQLITE_FULL)."""

    _template = "Database is full: {detail}"


# --- Transaction / MVCC errors --------------------------------------------
class TransactionError(TursoError):
    """A transaction-control error (Rust ``TxError``)."""

    _template = "Transaction error: {detail}"


class TransactionTerminated(_FixedTursoError):
    """The current transaction was terminated out from under the statement."""

    _template = "Transaction terminated"


class Conflict(TursoError):
    """A generic MVCC conflict."""

    _template = "Conflict: {detail}"


class WriteWriteConflict(_FixedTursoError):
    """Two writers touched the same row (MVCC)."""

    _template = "Write-write conflict"


class CommitDependencyAborted(_FixedTursoError):
    """A commit dependency could not be satisfied (MVCC)."""

    _template = "Commit dependency aborted"


class NoSuchTransactionID(TursoError):
    """A referenced transaction id is unknown to the MVCC layer."""

    _template = "No such transaction ID: {detail}"


# --- Schema errors --------------------------------------------------------
class SchemaUpdated(_FixedTursoError):
    """The schema cookie changed under a prepared statement (SQLITE_SCHEMA)."""

    _template = "Database schema changed"


class SchemaConflict(_FixedTursoError):
    """An incompatible schema change was detected."""

    _template = "Database schema conflict"


# --- Planning / extension / encoding errors -------------------------------
class PlanningError(TursoError):
    """A query-planning failure."""

    _template = "Planning error: {detail}"


class ExtensionError(TursoError):
    """An extension returned an error."""

    _template = "Extension error: {detail}"


class UnsupportedEncoding(TursoError):
    """A non-UTF-8 text encoding was requested; only UTF-8 is supported."""

    _template = "Unsupported text encoding: {detail}. Only UTF-8 is supported."


class CheckpointFailed(TursoError):
    """A WAL checkpoint failed."""

    _template = "Checkpoint failed: {detail}"


# --- Invalid argument errors ----------------------------------------------
class InvalidArgument(TursoError):
    """An invalid argument was supplied to a function/operation."""

    _template = "Invalid argument supplied: {detail}"


class InvalidFormatter(TursoError):
    """An invalid formatter was supplied (strftime-style)."""

    _template = "Invalid formatter supplied: {detail}"


# --- pyturso-only: clean rejection of unsupported SQL ----------------------
class NotSupported(TursoError):
    """A SQL feature is outside pyturso's parity scope.

    pyturso-only: Rust emits unsupported-SQL rejections as ``ParseError``;
    pyturso keeps them as a distinct class so the differential harness can
    report NOT-IMPLEMENTED cleanly and the scope ledgers stay honest.
    """

    _template = "not supported: {detail}"


# ---------------------------------------------------------------------------
# I/O completion errors (ports core/error.rs `CompletionError`).
# These surface through the io layer as generator requests; they are TursoError
# subclasses so the harness matches on them uniformly. The structured variants
# preserve their named fields verbatim from Rust.
# ---------------------------------------------------------------------------
class CompletionError(TursoError):
    """Base for I/O completion errors (Rust ``CompletionError``)."""

    _template = "I/O error: {detail}"


class IoCompletionError(CompletionError):
    """A stdlib-style I/O error tagged with the failing operation.

    Mirrors ``CompletionError::IOError(ErrorKind, &'static str)``.
    """

    _template = "I/O error ({op}): {detail}"

    def __init__(self, error_kind: str, op: str) -> None:
        self.error_kind: str = error_kind
        self.op: str = op
        # `detail` carries the operation for the generic template; the op-aware
        # template is rendered via _format.
        super().__init__(op)

    def _format(self) -> str:
        return f"I/O error ({self.op}): {self.error_kind}"


class CompletionAborted(_FixedTursoError):
    """An I/O completion was aborted."""

    _template = "Completion was aborted"


class DecryptionError(CompletionError):
    """Page decryption failed.

    Mirrors ``CompletionError::DecryptionError { page_idx }``.
    """

    def __init__(self, page_idx: int) -> None:
        self.page_idx: int = page_idx
        super().__init__(str(page_idx))

    def _format(self) -> str:
        return f"Decryption failed for page={self.page_idx}"


class ShortWrite(_FixedTursoError):
    """An I/O write did not deliver all requested bytes."""

    _template = "I/O error: partial write"


class ShortRead(CompletionError):
    """A page read returned fewer bytes than expected.

    Mirrors ``CompletionError::ShortRead { page_idx, expected, actual }``.
    """

    def __init__(self, page_idx: int, expected: int, actual: int) -> None:
        self.page_idx: int = page_idx
        self.expected: int = expected
        self.actual: int = actual
        super().__init__(str(page_idx))

    def _format(self) -> str:
        return (
            f"I/O error: short read on page {self.page_idx}: "
            f"expected {self.expected} bytes, got {self.actual}"
        )


class ShortReadWalFrame(CompletionError):
    """A WAL-frame read returned fewer bytes than expected.

    Mirrors ``CompletionError::ShortReadWalFrame { offset, expected, actual }``.
    """

    def __init__(self, offset: int, expected: int, actual: int) -> None:
        self.offset: int = offset
        self.expected: int = expected
        self.actual: int = actual
        super().__init__(str(offset))

    def _format(self) -> str:
        return (
            f"I/O error: short read on WAL frame at offset {self.offset}: "
            f"expected {self.expected} bytes, got {self.actual}"
        )


class WalFramePageMismatch(CompletionError):
    """A WAL frame's page number did not match the expected one.

    Mirrors ``CompletionError::WalFramePageMismatch { frame_id, expected,
    actual }``.
    """

    def __init__(self, frame_id: int, expected: int, actual: int) -> None:
        self.frame_id: int = frame_id
        self.expected: int = expected
        self.actual: int = actual
        super().__init__(str(frame_id))

    def _format(self) -> str:
        return (
            f"WAL frame page mismatch at frame {self.frame_id}: "
            f"expected page {self.expected}, got {self.actual}"
        )


class ChecksumMismatch(CompletionError):
    """A page/WAL checksum did not match the expected value.

    Mirrors ``CompletionError::ChecksumMismatch { page_id, expected, actual }``.
    """

    def __init__(self, page_id: int, expected: int, actual: int) -> None:
        self.page_id: int = page_id
        self.expected: int = expected
        self.actual: int = actual
        super().__init__(str(page_id))

    def _format(self) -> str:
        return (
            f"Checksum mismatch on page {self.page_id}: "
            f"expected {self.expected}, got {self.actual}"
        )


class ChecksumNotEnabled(_FixedTursoError):
    """Checksum verification requested but the feature is disabled."""

    _template = "tursodb not compiled with checksum feature"


# ---------------------------------------------------------------------------
# Error → comparison-class mapping (the differential harness matches here).
# Mapping follows SQLite result-code → sqlite3-exception semantics:
#   SQLITE_CORRUPT/NOTADB   → DatabaseError
#   SQLITE_CONSTRAINT family→ IntegrityError
#   SQLITE_BUSY/LOCKED/IOERR/FULL/READONLY/INTERRUPT/SCHEMA → OperationalError
#   SQLITE_INTERNAL/NOMEM    → InternalError
#   parse/lexer errors       → OperationalError (sqlite3 reports syntax
#                              errors as OperationalError, *not* Programming)
#   unsupported-SQL (pyturso) → NotSupportedError
# Refined as the corpus exercises more cases; keyed by exact class.
# ---------------------------------------------------------------------------
ERROR_CLASS: Final[dict[type[TursoError], str]] = {
    # Corrupt / format
    Corrupt: DATABASE_ERROR,
    NotADB: DATABASE_ERROR,
    Page1NotAlloc: DATABASE_ERROR,
    InvalidBlobSize: DATABASE_ERROR,
    BlobHandleExpired: OPERATIONAL_ERROR,
    # Internal / resource
    InternalError: INTERNAL_ERROR,
    OutOfMemory: INTERNAL_ERROR,
    # Parse / lexer — sqlite3 reports syntax errors as OperationalError.
    ParseError: OPERATIONAL_ERROR,
    LexerError: OPERATIONAL_ERROR,
    InvalidDate: OPERATIONAL_ERROR,
    InvalidTime: OPERATIONAL_ERROR,
    InvalidModifier: OPERATIONAL_ERROR,
    # Conversion / data
    ConversionError: DATA_ERROR,
    NullValue: DATA_ERROR,
    InvalidColumnType: DATA_ERROR,
    # Runtime / constraint
    Constraint: INTEGRITY_ERROR,
    ForeignKeyConstraint: INTEGRITY_ERROR,
    IntegerOverflow: OPERATIONAL_ERROR,
    TooBig: OPERATIONAL_ERROR,
    Raise: INTEGRITY_ERROR,
    RaiseIgnore: OPERATIONAL_ERROR,
    # Concurrency / locking / busy
    Busy: OPERATIONAL_ERROR,
    TableLocked: OPERATIONAL_ERROR,
    LockingError: OPERATIONAL_ERROR,
    StatementsInProgress: OPERATIONAL_ERROR,
    BusySnapshot: OPERATIONAL_ERROR,
    Interrupt: OPERATIONAL_ERROR,
    ReadOnly: OPERATIONAL_ERROR,
    DatabaseFull: OPERATIONAL_ERROR,
    # Transaction / MVCC
    TransactionError: OPERATIONAL_ERROR,
    TransactionTerminated: OPERATIONAL_ERROR,
    Conflict: OPERATIONAL_ERROR,
    WriteWriteConflict: OPERATIONAL_ERROR,
    CommitDependencyAborted: OPERATIONAL_ERROR,
    NoSuchTransactionID: OPERATIONAL_ERROR,
    # Schema
    SchemaUpdated: OPERATIONAL_ERROR,
    SchemaConflict: OPERATIONAL_ERROR,
    # Planning / extension / encoding / checkpoint
    PlanningError: OPERATIONAL_ERROR,
    ExtensionError: OPERATIONAL_ERROR,
    UnsupportedEncoding: OPERATIONAL_ERROR,
    CheckpointFailed: OPERATIONAL_ERROR,
    # Invalid argument / formatter
    InvalidArgument: OPERATIONAL_ERROR,
    InvalidFormatter: OPERATIONAL_ERROR,
    # pyturso-only
    NotSupported: NOT_SUPPORTED_ERROR,
    # I/O completion errors
    CompletionError: OPERATIONAL_ERROR,
    IoCompletionError: OPERATIONAL_ERROR,
    CompletionAborted: OPERATIONAL_ERROR,
    DecryptionError: OPERATIONAL_ERROR,
    ShortWrite: OPERATIONAL_ERROR,
    ShortRead: OPERATIONAL_ERROR,
    ShortReadWalFrame: OPERATIONAL_ERROR,
    WalFramePageMismatch: OPERATIONAL_ERROR,
    ChecksumMismatch: OPERATIONAL_ERROR,
    ChecksumNotEnabled: OPERATIONAL_ERROR,
}


def comparison_class(exc: BaseException) -> str:
    """Return the differential comparison-class string for ``exc``.

    Walks the MRO so subclasses not listed verbatim in :data:`ERROR_CLASS`
    still resolve to their nearest registered ancestor. Unknown errors
    (not a :class:`TursoError`) collapse to :data:`OPERATIONAL_ERROR`, the
    SQLite catch-all, so the harness never crashes on an unmapped exception.
    """
    if isinstance(exc, TursoError):
        for cls in type(exc).__mro__:
            mapped = ERROR_CLASS.get(cls)
            if mapped is not None:
                return mapped
    return OPERATIONAL_ERROR


__all__ = [
    # SQLite result-code constants
    "SQLITE_ERROR",
    "SQLITE_BUSY",
    "SQLITE_FULL",
    "SQLITE_CONSTRAINT",
    "SQLITE_CONSTRAINT_CHECK",
    "SQLITE_CONSTRAINT_FOREIGNKEY",
    "SQLITE_CONSTRAINT_NOTNULL",
    "SQLITE_CONSTRAINT_PRIMARYKEY",
    "SQLITE_CONSTRAINT_TRIGGER",
    "SQLITE_CONSTRAINT_UNIQUE",
    # Comparison-class strings
    "OPERATIONAL_ERROR",
    "INTEGRITY_ERROR",
    "DATABASE_ERROR",
    "PROGRAMMING_ERROR",
    "DATA_ERROR",
    "INTERNAL_ERROR",
    "NOT_SUPPORTED_ERROR",
    "INTERFACE_ERROR",
    "COMPARISON_CLASSES",
    # Mapping + helper
    "ERROR_CLASS",
    "comparison_class",
    # Hierarchy
    "TursoError",
    "Corrupt",
    "NotADB",
    "Page1NotAlloc",
    "InvalidBlobSize",
    "BlobHandleExpired",
    "InternalError",
    "OutOfMemory",
    "ParseError",
    "LexerError",
    "InvalidDate",
    "InvalidTime",
    "InvalidModifier",
    "ConversionError",
    "NullValue",
    "InvalidColumnType",
    "Constraint",
    "ForeignKeyConstraint",
    "IntegerOverflow",
    "TooBig",
    "Raise",
    "RaiseIgnore",
    "Busy",
    "TableLocked",
    "LockingError",
    "StatementsInProgress",
    "BusySnapshot",
    "Interrupt",
    "ReadOnly",
    "DatabaseFull",
    "TransactionError",
    "TransactionTerminated",
    "Conflict",
    "WriteWriteConflict",
    "CommitDependencyAborted",
    "NoSuchTransactionID",
    "SchemaUpdated",
    "SchemaConflict",
    "PlanningError",
    "ExtensionError",
    "UnsupportedEncoding",
    "CheckpointFailed",
    "InvalidArgument",
    "InvalidFormatter",
    "NotSupported",
    # I/O completion errors
    "CompletionError",
    "IoCompletionError",
    "CompletionAborted",
    "DecryptionError",
    "ShortWrite",
    "ShortRead",
    "ShortReadWalFrame",
    "WalFramePageMismatch",
    "ChecksumMismatch",
    "ChecksumNotEnabled",
]