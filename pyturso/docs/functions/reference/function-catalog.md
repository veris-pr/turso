# Function Catalog

**Status:** current · **Phase:** 6+

Every scalar and aggregate function pyturso implements, with parity status.

## Scalar functions (40+)

### String functions

| Function | Arity | Status | Notes |
|---|---|---|---|
| `length(x)` | 1 | ✅ | Length of text or blob |
| `upper(x)` | 1 | ✅ | Uppercase text |
| `lower(x)` | 1 | ✅ | Lowercase text |
| `substr(x, start[, len])` | 2-3 | ✅ | 1-based, negative start from end |
| `trim(x[, chars])` | 1-2 | ✅ | Trim chars from both ends |
| `ltrim(x[, chars])` | 1-2 | ✅ | Trim from left |
| `rtrim(x[, chars])` | 1-2 | ✅ | Trim from right |
| `replace(s, pat, repl)` | 3 | ✅ | Replace all occurrences |
| `instr(hay, needle)` | 2 | ✅ | 1-based position, 0 if not found |
| `hex(x)` | 1 | ✅ | Hex encoding of blob/integer |
| `quote(x)` | 1 | ✅ | SQL literal representation |
| `char(n1, n2, ...)` | -1 | ✅ | Unicode code points to string |
| `unicode(x)` | 1 | ✅ | Code point of first character |
| `like(pat, text[, esc])` | 2-3 | ✅ | LIKE pattern matching |
| `glob(pat, text)` | 2 | ✅ | GLOB pattern matching |

### Math functions

| Function | Arity | Status | Notes |
|---|---|---|---|
| `abs(x)` | 1 | ✅ | Absolute value (i64 overflow → REAL) |
| `round(x[, d])` | 1-2 | ✅ | C round-half-away-from-zero |
| `ceil(x)` / `ceiling(x)` | 1 | ✅ | Ceiling |
| `floor(x)` | 1 | ✅ | Floor |
| `sign(x)` | 1 | ✅ | -1, 0, or 1 |
| `sqrt(x)` | 1 | ✅ | Square root (NULL for negative) |
| `pow(x, y)` / `power(x, y)` | 2 | ✅ | Power |

### Type functions

| Function | Arity | Status | Notes |
|---|---|---|---|
| `typeof(x)` | 1 | ✅ | Storage class name |

### NULL-handling functions

| Function | Arity | Status | Notes |
|---|---|---|---|
| `coalesce(x, ...)` | -1 | ✅ | First non-NULL argument |
| `ifnull(x, y)` | 2 | ✅ | x if not NULL, else y |
| `nullif(x, y)` | 2 | ✅ | NULL if x == y, else x |
| `min(x, ...)` | -1 | ✅ | Scalar minimum (NULL propagates) |
| `max(x, ...)` | -1 | ✅ | Scalar maximum (NULL propagates) |

### Date/time functions

| Function | Arity | Status | Notes |
|---|---|---|---|
| `date(t[, mod...])` | -1 | ✅ | Date from time value + modifiers |
| `time(t[, mod...])` | -1 | ✅ | Time from time value + modifiers |
| `datetime(t[, mod...])` | -1 | ✅ | Date+time from time value + modifiers |
| `julianday(t[, mod...])` | -1 | ✅ | Julian day number |
| `unixepoch(t[, mod...])` | -1 | ✅ | Unix epoch seconds |
| `strftime(fmt, t[, mod...])` | -1 | ✅ | Formatted date/time string |

### Printf function

| Function | Arity | Status | Notes |
|---|---|---|---|
| `printf(fmt, ...)` | -1 | ✅ | C-style format (%d, %s, %f, %x, %%, width) |
| `format(fmt, ...)` | -1 | ✅ | Alias for printf |

## Aggregate functions

| Function | Status | Notes |
|---|---|---|
| `count(*)` / `count(x)` | ✅ | Count all rows / non-NULL values |
| `sum(x)` | ✅ | INTEGER until overflow → REAL |
| `total(x)` | ✅ | Always REAL, 0.0 for empty |
| `avg(x)` | ✅ | Average (NULL for empty) |
| `min(x)` | ✅ | Aggregate minimum |
| `max(x)` | ✅ | Aggregate maximum |
| `group_concat(x[, sep])` | ✅ | Concatenate with separator |

## Planned functions

| Function | Phase | Notes |
|---|---|---|
| `random()` | 6 | Seeded via io.clock |
| `randomblob(n)` | 6 | Random blob |
| `zeroblob(n)` | 6 | Zero-filled blob |
| `last_insert_rowid()` | 7 | Connection's last rowid |
| `changes()` / `total_changes()` | 7 | Rows affected |
| `sqlite_version()` | 10 | Version string |
| `iif(cond, a, b)` | 6 | Inline if |
| `min(x, y)` (2-arg) | 6 | Two-arg min (scalar) |