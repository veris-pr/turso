# TODO — functions

Work order rationale: [HOWTO.md](HOWTO.md). Iron rule: one function (or one
tight family) per commit, each with catalog row + NULL + coercion corpus cases.

## Phase 6 — scalars

- [x] `registry.py`: case-insensitive name + arity lookup, variadic
      conventions from `core/function.rs`, deterministic flag; VM
      function-call opcode wired once.
- [x] `string.py` batch 1: `length`, `upper`, `lower`, `substr` (2- and
      3-arg, negative indexes), `trim`/`ltrim`/`rtrim` (1/2-arg).
- [x] `string.py` batch 2: `replace`, `instr`, `hex`, `unhex`, `quote`,
      `char`, `unicode`, `zeroblob`.
- [x] LIKE/GLOB pattern compiler (+ ESCAPE) — shared by the operator;
      case-insensitivity rules exactly per SQLite docs.
- [x] `math.py`: `abs` (i64 overflow!), `round` (C-format semantics, not
      bankers'), `ceil`/`floor`, `sign`, `pow`, `sqrt`, ln/log/exp, trig —
      domain errors → NULL where SQLite says so.
- [x] `coalesce`/`ifnull`/`nullif`/`iif`, `typeof`, `min`/`max` scalar
      forms, `random`/`randomblob` (seeded via clock/injectable),
      `last_insert_rowid` (wired to connection).
- [x] `datetime.py`: `date`, `time`, `datetime`, `julianday`, `strftime`,
      `unixepoch`; modifier chain; `'now'` via `io.clock` only.
- [x] `printf.py`: `%d %s %f %x %%` + width/precision subset, `format` alias.
- [x] **Gate:** catalog rows complete (docs/functions/reference/function-catalog.md)

## Phase 10 — aggregates

- [x] `aggregate.py`: `count(*)`/`count(x)`, `sum`/`total` (overflow rules),
      `avg`, `min`/`max`, `group_concat` (separator arg) — step/finalize
      objects.
- [x] Aggregate functions + GROUP BY emitter landed (functions/aggregate.py + vdbe/sorter.py)
      cases incl. empty-input results for each.
