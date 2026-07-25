# HOWTO — package root (public API & assembly)

What the module is: [README.md](README.md). This folder's code is thin on
purpose — it wires subsystems and exposes Database/Connection/Statement.

## Work order

1. **Phase 0 — `errors.py` first.** The differential harness needs the
   exception hierarchy before any engine code exists. Port the variant list
   from `core/error.rs` into a class tree; map each class to the differential
   error classes the harness compares on. Keep messages human, classes exact.
2. **Phase 5 — minimal API.** `database.py` (open file → pager),
   `connection.py` (holds schema + prepare()), `statement.py` (owns a
   `vdbe.Program` + its execution state). Port the *lifecycle*, not the whole
   surface: `prepare → step* → (row | done) → reset/finalize`.
   `step()` is a generator over the io layer; provide `run()`/iteration as
   the convenience driver on top — never the other way around.
3. **Phase 8 — transaction state.** BEGIN/COMMIT/ROLLBACK move connection
   state; read how `core/connection.rs` tracks auto-commit vs explicit before
   adding fields.
4. **Phase 10 — `pragma.py`** subset, ledgered in the docs.
5. **Phase 12** — whatever the CLI needs that is missing (non-interactive
   exec, `.schema` support queries) gets added *here*, not in cli/.

## Rules

- No engine logic in this folder: if a function inspects pages, opcodes, or
  AST nodes, it belongs in a subsystem module.
- Every public method appears in `docs/api/reference/public-api.md` in the
  same commit (scope-ledger discipline).
- The capstone doc `docs/api/explanation/anatomy-of-a-query.md` gets a new
  layer each time this folder wires in a new subsystem — keep it current; it
  is the project's single best artifact.

## Verify

Phase 5 gate: `corpus/phase5_select` green three-way; unit tests drive
statement lifecycle by hand (step-by-step, reset, re-step, finalize-then-use
errors).
