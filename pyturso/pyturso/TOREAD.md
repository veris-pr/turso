# TOREAD — package root (API & assembly)

Levels refer to [../READING.md](../READING.md).

## Before Phase 0 (`errors.py`)

- [ ] `core/error.rs` — the variant list you are mirroring.
- [ ] SQLite [result codes doc](https://sqlite.org/rescode.html) — skim; the
      classes sqlite3 (Python) raises map from these, and the harness
      compares on your mapping.

## Before Phase 5

- [ ] SQLite [C API intro](https://sqlite.org/cintro.html) — the
      prepare/step/finalize lifecycle this API mirrors; also explains the
      Python stdlib `sqlite3` behaviors the harness observes.
- [ ] Rust: `core/lib.rs` (Database), `core/connection.rs`,
      `core/statement.rs` — track one `prepare` + `step` call top-down; this
      read *is* the module design.
- [ ] Prereq from your own docs: `docs/vdbe/explanation/resumable-step.md`
      (statement.step is its public face).

## Before Phase 8 additions

- [ ] Repo guide: `docs/agent-guides/transaction-correctness.md` (the
      connection-state rules section).
- [ ] Rust: `core/connection.rs` transaction-state handling;
      `core/translate/transaction.rs`.

## Standing

- [ ] READING L3: *Architecture of a Database System* §1 (process models) —
      why embedded/in-process is its own architecture; frames what
      Database/Connection own here vs in a server DB.

## Docs you will write

`public-api.md` · `error-hierarchy.md` · `anatomy-of-a-query.md` (capstone,
grows per phase) · `who-owns-what.md` (Phase 8) · `open-query-close.md`
tutorial · lifecycle how-to. Status: `docs/api/README.md`.
