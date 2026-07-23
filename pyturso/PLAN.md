# pyturso — Build Plan

A followable, phase-by-phase plan for porting the Turso engine to Python.
Rust code is the source of truth; parity is the target; understanding is the
end goal. Read [README.md](README.md) first for doctrine and the parity tiers.

---

## 1. Working method (applies to every phase)

Each phase repeats the same loop, per module:

1. **Read the Rust first.** Every phase lists its Rust reading list. Read for
   data flow and invariants, not line-by-line comprehension. Write down the
   questions you can't answer — they become the module's explanation docs.
2. **Port the concept.** Implement in Python, mirroring module and type names
   (`Pager`, `BTreeCursor`, `ProgramBuilder`, `Insn`…) so cross-reading stays
   effortless. Follow the conventions in §2.
3. **Verify differentially.** Add corpus entries / unit tests that fail
   without the new code and pass with it. Run the three-way harness.
4. **Document.** Write the Diátaxis deliverables listed for the phase. The
   explanation doc must contain an "In Turso" section linking the Rust files
   and stating what was ported faithfully vs. simplified.
5. **Re-read the Rust.** Close the loop: after your Python version works,
   re-read the Rust counterpart and record (in the explanation doc) everything
   it does that yours doesn't, and why.

A phase is **done** when its exit criteria all pass and its docs exist. Do not
start phase N+1 with phase N's exit criteria red.

## 2. Conventions

- **Module mirroring.** `pyturso/storage/pager.py` ports `core/storage/pager.rs`;
  file names match wherever Python allows. New helper modules are allowed but
  must be listed in the module README.
- **`IOResult` as generators.** Any function that in Rust returns
  `IOResult<T>` becomes a Python generator that `yield`s an I/O request object
  and receives the completion via `send()`. A trivial synchronous driver
  (`run_to_completion`) executes them for normal use. This preserves Turso's
  re-entrant state-machine shape (see `docs/agent-guides/async-io-model.md`)
  without pretending Python has io_uring.
- **Errors mirror `core/error.rs`.** One `TursoError` hierarchy; differential
  comparison matches on error class, not message text.
- **Typing.** Full type annotations, `from __future__ import annotations`,
  dataclasses for AST/plan/insn nodes, `enum.Enum` for opcodes and serial
  types. `mypy --strict` clean is a standing goal from Phase 1.
- **Stdlib only** at runtime. `struct` for binary packing, `os` for file I/O.
- **No premature abstraction.** Port what the Rust does today. If the Rust has
  a trait, port it as a `Protocol` only when a second implementation exists.
- **Single-threaded** until the MVCC phase, which stays a concept port.

## 3. Verification infrastructure (built in Phase 0, used forever)

- **Three-way differential harness** (`tests/differential/`): runs each corpus
  script through (a) Python stdlib `sqlite3`, (b) `tursodb` via subprocess,
  (c) pyturso; normalizes output (float formatting, NULL rendering, error
  classes); reports any divergence. Modeled on `scripts/diff.sh` and the
  `.sqltest` philosophy in `sqlite/conformance/`.
- **Corpus format**: plain `.sql` scripts with expected-output sidecars
  generated from sqlite3, plus per-phase directories (`corpus/phase1_read/`,
  `corpus/phase6_where/`…). Corpus entries are *behavioral* — anything
  Rust-specific stays in turso's own test suites and is not ported.
- **File-level checks**: `PRAGMA integrity_check` through sqlite3 on every
  pyturso-written file; logical content hashing via the repo's `tools/dbhash`.
- **`EXPLAIN` differ** (`tools/explain_diff.py`): pretty side-by-side of
  tursodb vs pyturso bytecode for a statement. Advisory, never a gate.

---

## 4. Phases

| # | Phase | Delivers | Milestone demo |
|---|-------|----------|----------------|
| 0 | Harness & skeleton | differential runner, tools, corpus format | three-way run of `SELECT 1` (pyturso stubbed as expected-fail) |
| 1 | File-format reader | header, pages, varints, records, B-tree walk | **M1:** dump every row of a real sqlite3-made `.db`, no SQL |
| 2 | Types & records | serial types, affinity, comparison/collation rules | typed round-trip of every serial type against sqlite3 |
| 3 | Parser | tokenizer, lexer, AST, recursive descent (subset) | parse the whole phase corpus; AST snapshot tests |
| 4 | Schema | `sqlite_schema` → Table/Index/Column objects | `.schema`-equivalent output matches sqlite3 |
| 5 | Minimal pipeline | translate + VDBE skeleton for simple SELECT | **M2:** `SELECT c FROM t WHERE …` end-to-end from a real file |
| 6 | Expressions & functions | full WHERE evaluation, scalar functions, affinity in comparisons | expression corpus (hundreds of cases) green |
| 7 | Write path | pager writes, B-tree insert/delete/balance, freelist | **M3:** pyturso INSERTs; sqlite3 reads the file back, integrity_check OK |
| 8 | WAL & transactions | WAL append/read, commit, checkpoint, recovery | **M4:** kill mid-transaction, recover, verify durability matrix |
| 9 | Planner & optimizer | index selection, cost, joins, ORDER BY elimination | **M5:** query flips seq-scan → index; joins match oracle |
| 10 | Full SQL surface | GROUP BY/aggregates, subqueries, compounds, UPSERT, views | large conformance corpus green |
| 11 | MVCC (concept) | versioned rows, snapshot isolation, 2 fake concurrent conns | interleaved-transaction scenarios match `docs/agent-guides/mvcc.md` |
| 12 | CLI | REPL with core dot-commands | **M6:** side-by-side scripted session vs `tursodb` |

Phases 2/3/4 can proceed in parallel with each other after Phase 1. Everything
else is sequential. Revisit-and-deepen is expected: e.g. Phase 9 will reopen
Phase 5's translator.

---

### Phase 0 — Harness & skeleton

**Goal:** the verification loop exists before any engine code.

Build:
- `tests/differential/run.py`: run a `.sql` script through sqlite3 (stdlib),
  tursodb (subprocess, `-q`), and pyturso; normalize; diff; report.
- Output normalization rules (documented in `tests/differential/README.md`).
- `tools/mkdb.py`: create corpus fixture databases *with sqlite3* from DDL+data
  scripts (until Phase 7, pyturso only reads).
- Package skeleton importable; `pyproject.toml`; pytest wired.

Rust reading: `scripts/diff.sh`, `sqlite/conformance/README*` if present,
skim `.sqltest` files for the behavioral-test mindset.

Docs: `docs/testing` section inside `tests/differential/README.md`;
`docs/README.md` doc-map entries.

**Exit criteria:** `python -m tests.differential.run` executes a trivial
corpus, correctly reports sqlite3≡tursodb, and reports pyturso as
NOT-IMPLEMENTED (not a crash).

---

### Phase 1 — File-format reader (`storage/sqlite3_ondisk.py`, `storage/btree.py` read side)

**Goal:** parse a real database file: the 100-byte header, page types, cell
layouts, varints, overflow chains, and interior/leaf B-tree traversal.

Build:
- `storage/sqlite3_ondisk.py`: header struct, page decoding, cell pointer
  arrays, varint, serial-type record decoding (raw bytes level).
- `storage/btree.py` (read half): `BTreeCursor` — `rewind/next/prev/seek` over
  table B-trees; overflow page chains; then index B-trees.
- `pyturso/io/`: `Completion`, `File` protocol, `MemoryIO` + `PosixIO`
  backends; the generator convention (§2) established here, on the simplest
  module.
- `tools/dbdump.py`, `tools/pagehex.py`.

Rust reading: `core/storage/sqlite3_ondisk.rs`, `core/storage/btree.rs`
(traversal paths only), `core/io/memory.rs`, `core/io/unix.rs`,
`docs/agent-guides/storage-format.md`, SQLite fileformat2 doc as secondary.

Docs (Diátaxis): tutorial "Read a database file byte by byte"; reference
"File header fields", "Page & cell layout", "Varint & serial types"; explanation
"Why B-trees, and how Turso walks them"; how-to "Inspect a page with pagehex".

**Exit criteria:** `tools/dbdump.py` reproduces `SELECT * FROM t` output
(sqlite3 as oracle) for fixture DBs covering: multi-page tables, all serial
types, overflow, interior pages ≥2 levels, WITHOUT ROWID excluded (deferred to
Phase 2 exit or explicitly ticketed).

---

### Phase 2 — Types, records, affinity (`types/`)

**Goal:** the value model: NULL/INTEGER/REAL/TEXT/BLOB, serial-type encode/
decode, type affinity, comparison ordering across types, collations
(BINARY/NOCASE/RTRIM).

Rust reading: `core/types.rs`, `core/vdbe/value.rs`, `core/vdbe/affinity.rs`,
`core/numeric/`, `core/translate/collate.rs`.

Docs: reference "Serial types table", "Affinity rules", "Cross-type comparison
order"; explanation "Manifest typing: why SQLite types are per-value".

**Exit criteria:** property-style unit tests: encode(decode(x)) round-trips;
cross-type ORDER BY of a mixed column matches sqlite3 exactly.

---

### Phase 3 — Parser (`parser/`)

**Goal:** tokenizer → lexer → AST → recursive-descent parser for a defined
subset (grow per phase): SELECT core, INSERT/UPDATE/DELETE, CREATE TABLE/INDEX,
expressions with correct precedence, literals, identifiers/quoting.

Rust reading: `sqlite/parser/src/token.rs`, `lexer.rs`, `ast.rs` + `ast/`,
`parser.rs` (11k LOC — read per-construct as you port it, not linearly).

Docs: tutorial "From SQL text to AST"; reference "Supported grammar (per
phase)", "AST node catalog"; explanation "Why recursive descent; how errors
are reported"; how-to "Add a new statement type".

**Exit criteria:** every corpus statement parses to an AST snapshot; invalid-SQL
cases produce the same error *class* as sqlite3; precedence corpus (arithmetic,
comparison, logical, COLLATE, unary) matches oracle via Phase 5+ evaluation or
AST-shape assertions until then.

---

### Phase 4 — Schema (`schema/`)

**Goal:** read `sqlite_schema` via the Phase 1 cursor, parse the stored SQL via
Phase 3, and materialize Table/Index/Column/rootpage objects; rowid-alias
(INTEGER PRIMARY KEY) detection.

Rust reading: `core/schema.rs`, `core/translate/schema.rs`.

Docs: explanation "The schema is just a table"; reference "Schema object
model"; how-to "Trace how a CREATE TABLE becomes rows in page 1".

**Exit criteria:** for fixture DBs, pyturso's schema objects agree with
`PRAGMA table_info` / `sqlite_schema` queries run in sqlite3.

---

### Phase 5 — Minimal pipeline (`translate/` + `vdbe/` skeletons)

**Goal:** the smallest honest end-to-end path:
`SELECT cols FROM t [WHERE simple-pred] [LIMIT n]` compiled to bytecode and
executed by a register-based VM over Phase 1 cursors.

Build:
- `vdbe/insn.py`: opcode enum + operands, mirroring `core/vdbe/insn.rs` names.
- `vdbe/builder.py`: `ProgramBuilder` (labels, register allocation).
- `vdbe/execute.py`: dispatch loop; ~15 opcodes to start
  (Init/OpenRead/Rewind/Column/ResultRow/Next/Halt/Integer/String8/Eq/Ne/…).
- `vdbe/explain.py`: EXPLAIN-format listing for the differ.
- `translate/select.py`, `translate/expr/`, `translate/emitter/`: minimal
  translation; one-table plans in `translate/plan.py`.

Rust reading: `core/vdbe/insn.rs`, `core/vdbe/builder.rs`,
`core/vdbe/execute.rs` (only the ported opcodes), `core/translate/select.rs`,
`core/translate/main_loop/`, `core/translate/emitter/select.rs`,
`docs/agent-guides/debugging.md` (bytecode comparison workflow).

Docs: tutorial "Compile and single-step your first program"; reference "Opcode
catalog (ported subset)"; explanation "Registers, cursors, and the program
counter — VDBE as a tiny CPU"; how-to "Diff bytecode against tursodb".

**Exit criteria:** M2 demo; differential corpus `phase5_select/` green;
`tools/explain_diff.py` shows structurally comparable programs for 5 sample
queries.

---

### Phase 6 — Expressions & functions (`functions/`, expanded `translate/expr`)

**Goal:** full expression evaluation in WHERE and the select list: operators
with affinity-correct comparison, CASE, BETWEEN, IN (value lists), LIKE/GLOB,
NULL semantics, and an initial scalar function set (`length`, `upper`, `abs`,
`coalesce`, `substr`, `typeof`, `hex`, date/time core, `printf` subset).

Rust reading: `core/translate/expr/`, `core/functions/` (all files),
`core/function.rs`, `core/vdbe/execute.rs` function-call paths.

Docs: reference "Function catalog + parity status", "NULL semantics cheatsheet";
explanation "Three-valued logic in the VM"; how-to "Add a scalar function and
prove parity".

**Exit criteria:** expression corpus (target: 300+ statements, auto-verified)
green three-way; every implemented function has at least one NULL-argument and
one type-coercion corpus case.

---

### Phase 7 — Write path (`storage/pager.py`, `storage/btree.py` write side)

**Goal:** mutate files correctly: pager write-through, page allocation and the
freelist, B-tree insert with cell overflow and page split/balance, delete with
underflow handling, rowid allocation; CREATE TABLE writing schema rows.
Journaling minimal (rollback journal *or* straight-to-WAL — decide by reading
how Turso defaults; record decision in the explanation doc).

Rust reading: `core/storage/pager.rs`, `core/storage/btree.rs` (balance —
the hardest code in the project; budget multiple passes),
`core/storage/page_cache.rs`, `core/storage/buffer_pool.rs`,
`docs/agent-guides/storage-format.md` freelist/pointer-map sections.

Docs: tutorial "Insert a row and watch the pages change"; explanation "B-tree
balancing, in pictures" (this doc is a phase deliverable, not optional — if
you can't draw it, you don't understand it); reference "Freelist format";
how-to "Verify a written file with integrity_check and dbhash".

**Exit criteria:** M3 demo; randomized insert/delete sequences (fixed seeds)
produce files where sqlite3 `integrity_check` passes and full-table dumps match
a sqlite3-built twin; `tools/dbhash` matches on logical-twin databases.

---

### Phase 8 — WAL & transactions (`storage/wal.py`)

**Goal:** WAL frame format, append on commit, read-path frame lookup
(most-recent-frame-wins), salt/checksums, checkpointing back to the main file,
crash recovery on open; BEGIN/COMMIT/ROLLBACK statement support.

Rust reading: `core/storage/wal.rs`, `core/storage/checksum.rs`,
`docs/agent-guides/transaction-correctness.md` (read *before* coding),
`core/translate/transaction.rs`.

Docs: explanation "Why WAL: the durability/concurrency trade"; reference "WAL
frame & header format"; how-to "Simulate a crash and recover"; tutorial
"Follow one COMMIT from statement to disk".

**Exit criteria:** M4 demo — a scripted harness that kills pyturso at injected
points (pre-commit-frame, post-commit-frame, mid-checkpoint) and asserts the
recovery matrix; sqlite3 can open and read the pyturso WAL'd database.

---

### Phase 9 — Planner & optimizer (`translate/optimizer/`)

**Goal:** WHERE-clause analysis into index-usable constraints, access-method
selection (seq scan vs index seek/scan, covering index), simple cost model,
nested-loop joins with join-order search, ORDER BY satisfaction via index.

Rust reading: `core/translate/optimizer/` (start with `OPTIMIZER.md` in that
directory), `core/translate/planner.rs`, `core/translate/plan.rs`,
`core/translate/main_loop/`.

Docs: explanation "How a query picks its indexes" with worked examples;
reference "Constraint extraction rules", "Cost model constants"; how-to "Read
a query plan and predict the bytecode".

**Exit criteria:** M5 demo; a plan-assertion corpus (EXPLAIN-based, structural)
plus behavioral corpus with joins/indexes green; results identical with the
optimizer force-disabled (correctness must never depend on the optimizer).

---

### Phase 10 — Full SQL surface (breadth phase)

**Goal:** GROUP BY + aggregate functions + HAVING (sorter-based, port
`vdbe/sorter.rs`), DISTINCT, compound SELECTs, correlated & uncorrelated
subqueries, IN (subquery), UPDATE/DELETE with indexes, UPSERT, views, ALTER
basics, PRAGMA subset. Window functions and triggers: evaluate and either port
or explicitly defer with a note in this file.

Rust reading: `core/vdbe/sorter.rs`, `core/translate/{group_by,aggregation,
compound_select,subquery,update,delete,upsert,view,pragma}.rs`.

Docs: per-feature explanation shorts; reference updates to opcode/function
catalogs; tutorial "How GROUP BY really executes".

**Exit criteria:** a curated port of behavioral cases from
`sqlite/conformance/sqlite-sqltests/` (tracked in
`tests/differential/corpus/from_sqltest/MANIFEST.md` with per-file parity
status) runs green; anything intentionally unsupported is listed there, not
silently skipped.

---

### Phase 11 — MVCC (concept port, `mvcc/`)

**Goal:** understand Turso's experimental MVCC by modeling it: row versions,
transaction ids, snapshot visibility rules, write-write conflict detection —
exercised by a scripted multi-connection driver (cooperative, single-thread).

Rust reading: `core/mvcc/` (`database/`, `cursor.rs`), `docs/agent-guides/mvcc.md`,
`cli/mvcc_repl.rs` scenarios.

Docs: explanation "Snapshot isolation, concretely"; how-to "Reproduce a
write-write conflict"; reference "Visibility rules".

**Exit criteria:** scenario scripts (mirroring mvcc_repl sessions) produce the
isolation outcomes the Rust docs specify; deviations from turso behavior are
documented, not hidden.

---

### Phase 12 — CLI (`cli/`)

**Goal:** an interactive REPL: line editing, statement termination, table/list
output modes, core dot-commands (`.schema`, `.tables`, `.mode`, `.open`,
`.read`, `.explain`), errors formatted like tursodb where sensible.

Rust reading: `cli/` at repo root (entry, REPL loop, output modes).

Docs: tutorial "A guided pyturso session"; reference "Dot-command parity table".

**Exit criteria:** M6 — a scripted session file produces output diffable
against `tursodb -q` for the supported feature set.

---

## 5. Documentation workflow (Diátaxis)

Each module owns a tree under `docs/<module>/` with four quadrants:

- **tutorials/** — learning-oriented, written *after* a module stabilizes;
  each phase names at least one.
- **how-to/** — task recipes, added whenever you catch yourself re-deriving a
  procedure (inspect a page, diff bytecode, regenerate corpus).
- **reference/** — tables and catalogs (formats, opcodes, functions, grammar),
  written *alongside* the code and updated in the same commit that changes
  behavior.
- **explanation/** — the understanding artifacts; drafted from the questions
  collected while reading Rust (§1 step 1). Every explanation doc ends with an
  **"In Turso"** section: links to the Rust files, what was ported faithfully,
  what was simplified, and what the Rust does that pyturso doesn't.

`docs/<module>/README.md` is the module's doc index and lists the planned
documents with status. Quadrant folders exist upfront, each carrying a
`HOWTO.md` with quadrant-specific writing rules.

## 6. Risks & standing decisions

- **B-tree balancing (Phase 7) is the wall.** Expect it to take as long as
  Phases 1–5 combined. Mitigation: exhaustive fixed-seed randomized testing
  against integrity_check from day one of the phase.
- **Scope creep via SQLite's surface area.** The corpus MANIFEST is the
  scope ledger: features are either green, red-with-ticket, or
  declared-out-of-scope. No fourth state.
- **Drift from upstream.** Turso moves fast. pyturso pins understanding, not
  bytes: when upstream refactors, update the "In Turso" doc sections during
  the next phase boundary, not continuously.
- **Rust-only tests are not ported** (borrow-checker, panics, async
  machinery, sanitizers). Behavioral intent is ported via the corpus instead.

## 7. Cadence

With full-time effort, phases 0–5 are on the order of weeks each, 6–10 longer,
7 the longest. The only hard rule: **never two phases in flight** (except the
2/3/4 parallel window), and never advance with a red exit criterion.
