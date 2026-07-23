# TODO — functions

Work order rationale: [HOWTO.md](HOWTO.md). Iron rule: one function (or one
tight family) per commit, each with catalog row + NULL + coercion corpus cases.

## Phase 6 — scalars

- [ ] `registry.py`: case-insensitive name + arity lookup, variadic
      conventions from `core/function.rs`, deterministic flag; VM
      function-call opcode wired once.
- [ ] `string.py` batch 1: `length`, `upper`, `lower`, `substr` (2- and
      3-arg, negative indexes), `trim`/`ltrim`/`rtrim` (1/2-arg).
- [ ] `string.py` batch 2: `replace`, `instr`, `hex`, `unhex`, `quote`,
      `char`, `unicode`, `zeroblob`.
- [ ] LIKE/GLOB pattern compiler (+ ESCAPE) — shared by the operator;
      case-insensitivity rules exactly per SQLite docs.
- [ ] `math.py`: `abs` (i64 overflow!), `round` (C-format semantics, not
      bankers'), `ceil`/`floor`, `sign`, `pow`, `sqrt`, ln/log/exp, trig —
      domain errors → NULL where SQLite says so.
- [ ] `coalesce`/`ifnull`/`nullif`/`iif`, `typeof`, `min`/`max` scalar
      forms, `random`/`randomblob` (seeded via clock/injectable),
      `last_insert_rowid` (wired to connection).
- [ ] `datetime.py`: `date`, `time`, `datetime`, `julianday`, `strftime`,
      `unixepoch`; modifier chain; `'now'` via `io.clock` only.
- [ ] `printf.py`: `%d %s %f %x %%` + width/precision subset, `format` alias.
- [ ] **Gate:** `corpus/phase6_functions` green; catalog rows complete.

## Phase 10 — aggregates

- [ ] `aggregate.py`: `count(*)`/`count(x)`, `sum`/`total` (overflow rules),
      `avg`, `min`/`max`, `group_concat` (separator arg) — step/finalize
      objects.
- [ ] Land together with vdbe aggregate opcodes + GROUP BY emitter; corpus
      cases incl. empty-input results for each.
