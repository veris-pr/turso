# Error Hierarchy

**Status:** current · **Phase:** 0

Ports `core/error.rs` `LimboError` enum. The differential harness matches on
these classes (error → comparison-class mapping in `pyturso/errors.py`).

## Base class

```
TursoError(Exception)
```

All pyturso errors derive from `TursoError`. The differential harness catches
`TursoError` and maps it to a comparison class.

## Major subclasses

| Class | Comparison class | When raised |
|---|---|---|
| `Corrupt` | `DatabaseError` | Corrupt database file, bad magic, invalid page |
| `NotADB` | `DatabaseError` | File header is not SQLite format |
| `ParseError` | `OperationalError` | SQL syntax error (parser/lexer) |
| `Constraint` | `IntegrityError` | Runtime constraint violation |
| `ForeignKeyConstraint` | `IntegrityError` | Foreign key constraint failure |
| `Busy` | `OperationalError` | Database is busy |
| `NotSupported` | `NotSupportedError` | Feature outside pyturso's scope |
| `InternalError` | `InternalError` | Engine invariant violation |
| `OutOfMemory` | `InternalError` | Allocation failure |
| `CompletionError` | `OperationalError` | I/O completion failure |

## I/O errors

| Class | When |
|---|---|
| `CompletionError` | Base for I/O completion errors |
| `IoCompletionError` | stdlib I/O error (pread/pwrite/fsync) |
| `ShortRead` | Page read returned fewer bytes than expected |
| `ShortReadWalFrame` | WAL frame read returned fewer bytes |
| `ChecksumMismatch` | Page/WAL checksum mismatch |

## Comparison class mapping

`pyturso.errors.comparison_class(exc)` returns the string name:

| Input | Output |
|---|---|
| `Corrupt`, `NotADB` | `"DatabaseError"` |
| `ParseError` | `"OperationalError"` |
| `Constraint`, `ForeignKeyConstraint` | `"IntegrityError"` |
| `NotSupported` | `"NotSupportedError"` |
| `InternalError`, `OutOfMemory` | `"InternalError"` |
| `Busy`, `CompletionError` | `"OperationalError"` |
| Unknown `TursoError` | `"OperationalError"` (SQLite catch-all) |
| Non-`TursoError` | `"OperationalError"` (never crashes the harness) |