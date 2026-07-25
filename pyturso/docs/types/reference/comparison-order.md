# Comparison order — reference

**Status:** current · **Phase:** 2 · **Cites:** `pyturso/types/compare.py`;
Rust: `core/types.rs` (`ValueRef::Ord`), `core/numeric/mod.rs`
(`sqlite_int_float_cmp`), `core/translate/collate.rs` (`CollationSeq`).

## Cross-class total order

SQLite defines a total order across all storage classes:

```
NULL < INTEGER/REAL < TEXT < BLOB
```

| Class rank | Storage classes | Comparison rule |
|---|---|---|
| 0 | NULL | NULL < everything; NULL == NULL |
| 1 | INTEGER, REAL | Numeric cross-comparison (see below) |
| 2 | TEXT | Collation-dependent (see below) |
| 3 | BLOB | Byte-by-byte comparison |

## INTEGER ↔ REAL comparison

| Left | Right | Rule |
|---|---|---|
| INTEGER | INTEGER | Python `int` comparison |
| REAL | REAL | Python `float` comparison (NaN sorts lowest) |
| INTEGER | REAL | `sqlite_int_float_cmp` (see below) |

### `sqlite_int_float_cmp` (precision handling)

When comparing an integer with a float, large magnitudes require care (float
precision degrades past 2⁵³):

1. If the float is NaN → integer is greater (NaN treated as NULL).
2. If the float is outside i64 range (`< -2⁶³` or `≥ 2⁶³`) → the int wins by
   sign (very negative float < any int; very large float > any int).
3. If the float is in i64 range: convert to `int`, compare as integers. If
   equal, fall back to `float` comparison to detect non-integral parts.

## Collations

| Collation | Description | Ports |
|---|---|---|
| `BINARY` | Byte-by-byte comparison (default) | `CollationSeq::Binary` |
| `NOCASE` | ASCII-only case-insensitive (only A-Z lowered) | `CollationSeq::NoCase` |
| `RTRIM` | Strip trailing spaces, then BINARY | `CollationSeq::Rtrim` |

### NOCASE is ASCII-only

SQLite's `NOCASE` collation only lowercases ASCII `A-Z`. Non-ASCII bytes
(e.g. `É`) compare as-is — they are **not** lowered. This is a deliberate
SQLite behavior and a known gotcha:

```sql
SELECT 'É' = 'é' COLLATE NOCASE;  -- 0 (false) — NOCASE only lowercases A-Z
```

### RTRIM

Trailing spaces (`U+0020`) are stripped from both sides before BINARY
comparison:

```sql
SELECT 'abc  ' = 'abc' COLLATE RTRIM;  -- 1 (true)
```

## API

| Function | Signature |
|---|---|
| `compare_values(a, b, collation)` | `Value, Value, Collation → int (-1/0/+1)` |
| `compare_strings(a, b, collation)` | `str, str, Collation → int` |
| `sort_key(v, collation)` | `Value, Collation → tuple[int, object]` |

`sort_key` returns a `(class_rank, within_class_key)` tuple for `sorted()` —
one pass produces the correct cross-class ORDER BY.