# HOWTO — translate

What the module is: [README.md](README.md). Work spans Phases 5, 6, 9, 10;
subfolders carry their own HOWTOs
([expr/](expr/HOWTO.md) · [emitter/](emitter/HOWTO.md) ·
[optimizer/](optimizer/HOWTO.md) · [main_loop/](main_loop/HOWTO.md)).

## Phase 5 — the minimal honest pipeline

Order matters; each step is testable before the next:

1. **`plan.py`** — the smallest IR that is still a *plan*: one source table,
   a list of WHERE terms, result columns, LIMIT. Read `core/translate/plan.rs`
   and port the field *names* even where pyturso's version is narrower.
2. **`planner.py`** — AST → plan: resolve the table via `schema`, bind
   column references (including the rowid alias!), expand `*`, validate.
   All "no such table/column" errors originate here, never in emission.
3. **`expr/compile.py` minimal** — literals, column refs, one comparison
   (see [expr/HOWTO.md](expr/HOWTO.md) step 1–2).
4. **`emitter/select.py` + `main_loop/loop.py`** — emit the skeleton with an
   `EXPLAIN` from tursodb for the same query on screen
   ([emitter/HOWTO.md](emitter/HOWTO.md)).
5. **`select.py`** — the entry point tying 1–4 together; `pragma`-style
   dispatch grows here later.
6. Insert an **optimizer no-op seam** now: plan passes through a function
   that Phase 9 will replace. The seam (and its force-disable flag) is
   permanent — correctness never depends on the optimizer.

## Phase 6 — expressions

All of [expr/HOWTO.md](expr/HOWTO.md). The translator change per operator is
small; the parity risk is affinity/collation resolution — port the Rust's
decision order literally, cite it in comments.

## Phase 9 — optimizer

[optimizer/HOWTO.md](optimizer/HOWTO.md). Also grows `main_loop` to nested
joins and `plan.py` to multi-table.

## Phase 10 — per-statement translators

One file per statement kind, mirroring the Rust file list (`insert.py` earlier
in Phase 7, `update.py`, `delete.py`, then group_by/compound/subquery work
threaded through plan+emitter). Each new statement kind: planner support →
emitter → corpus, in that order.

## Rules

- Registers and labels only via `vdbe.builder` — never hand-numbered.
- Unsupported constructs raise clean not-supported errors at *translation*
  time (the parser may accept what the translator rejects; both ledgers stay
  honest).
- After any emitter change, run `tools/explain_diff.py` on the affected query
  shapes; structural drift from tursodb is a smell worth a note even when
  rows match.
