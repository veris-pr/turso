# pyturso.types — Values, serial types, records, affinity

**Ports:** `core/types.rs`, `core/vdbe/value.rs`, `core/vdbe/affinity.rs`,
`core/numeric/`, collation basics from `core/translate/collate.rs`
**Phase:** 2 (foundations used by every later phase)

## What this module is

The value model of the engine. SQLite (and Turso) use *manifest typing*: types
live on **values**, not columns. Everything that flows through the VM, gets
compared in a WHERE clause, sorted by ORDER BY, or serialized into a B-tree
cell is one of five storage classes:

```
NULL · INTEGER (i64) · REAL (f64) · TEXT · BLOB
```

This module owns:

- **`Value`** — the tagged value type (`core/vdbe/value.rs` / `core/types.rs`).
- **Serial types** — the on-disk encoding tag per value (0=NULL, 1..6 ints of
  varying width, 7=float, 8/9=constant 0/1, ≥12 even=BLOB, ≥13 odd=TEXT) and
  encode/decode between `Value` and record bytes.
- **Records** — the row format: header of serial types + body of payloads;
  built on the varint code from `storage/sqlite3_ondisk.py`.
- **Affinity** — column-type-name → affinity (TEXT/NUMERIC/INTEGER/REAL/BLOB)
  and the coercion rules applied before storage and comparison
  (`core/vdbe/affinity.rs`).
- **Comparison & ordering** — the total order across storage classes
  (NULL < numbers < text < blob), numeric cross-comparison of INTEGER/REAL,
  and collation sequences (BINARY, NOCASE, RTRIM).
- **Numeric edge behavior** — text→number parsing, overflow to REAL,
  integer/real equality subtleties (`core/numeric/`).

## Planned files

| File | Ports |
|------|-------|
| `value.py` | `Value` enum + arithmetic/coercion ops |
| `serial.py` | serial-type table, sizes, encode/decode |
| `record.py` | record (row) build/parse |
| `affinity.py` | affinity resolution + application rules |
| `compare.py` | cross-class ordering, collations |
| `numeric.py` | text↔number conversion, overflow rules |

## Parity notes

- Highest-density source of subtle divergence in the whole port: `'10' = 10`,
  `1 = 1.0`, `CAST` behavior, 8-vs-9 serial types for 0/1, NaN handling.
  Every rule gets a differential corpus case, not just a unit test.
- Python `int` is unbounded — i64 wraparound/overflow-to-REAL must be
  emulated explicitly; this is a deliberate parity exercise, not an accident
  to paper over.

## Docs

Diátaxis tree: [../../docs/types/README.md](../../docs/types/README.md)
