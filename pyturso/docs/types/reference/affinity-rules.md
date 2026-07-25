# Affinity rules — reference

**Status:** current · **Phase:** 2 · **Cites:** `pyturso/types/affinity.py`;
Rust: `core/vdbe/affinity.rs` (`Affinity`, `Affinity::affinity`,
`Affinity::convert`, `apply_numeric_affinity`).

## The five affinities

| Affinity | Description |
|---|---|
| `TEXT` | Stores data as NULL, TEXT, or BLOB. Numeric values → text. |
| `NUMERIC` | Text → INTEGER or REAL (in that preference); stays TEXT if not well-formed. |
| `INTEGER` | Like NUMERIC but differs in CAST expressions. |
| `REAL` | Like NUMERIC but forces integers to REAL. |
| `BLOB` | No conversion (values stored as-is). |

## Type-name → affinity resolution (rule order IS the spec)

The rules are checked **in order**; the first match wins. This order is the
spec — changing it changes behavior.

| # | Condition (case-insensitive substring) | Affinity |
|---|---|---|
| 1 | Contains `INT` | INTEGER |
| 2 | Contains `CHAR`, `CLOB`, or `TEXT` | TEXT |
| 3 | Contains `BLOB` or empty string | BLOB |
| 4 | Contains `REAL`, `FLOA`, or `DOUB` | REAL |
| 5 | Otherwise | NUMERIC |

Examples: `VARCHAR` → TEXT (rule 2, "CHAR"); `BIGINT` → INTEGER (rule 1,
"INT"); `FLOAT` → REAL (rule 4, "FLOA"); `DATE` → NUMERIC (rule 5, no match).

## Application rules (`apply_affinity`)

| Affinity | INTEGER | REAL | TEXT | BLOB | NULL |
|---|---|---|---|---|---|
| TEXT | → text | → text | unchanged | unchanged | unchanged |
| NUMERIC | unchanged | unchanged | → int/real if well-formed | unchanged | unchanged |
| INTEGER | unchanged | unchanged | → int/real if well-formed | unchanged | unchanged |
| REAL | → real | unchanged | → real | unchanged | unchanged |
| BLOB | unchanged | unchanged | unchanged | unchanged | unchanged |

## Text→number conversion (ports `apply_numeric_affinity`)

Only **complete** numbers are converted — a valid numeric prefix with trailing
non-numeric characters stays TEXT. Hex integers (`0x...`) stay TEXT (historical
compatibility). Integers that overflow i64 → REAL.

| Input | Result |
|---|---|
| `"42"` | `Value.integer(42)` |
| `"3.14"` | `Value.real(3.14)` |
| `"123abc"` | stays TEXT (prefix-only) |
| `"0xFF"` | stays TEXT (hex) |
| `"hello"` | stays TEXT (not numeric) |
| `str(2**63 + 1)` | `Value.real(float(...))` (overflow to REAL) |