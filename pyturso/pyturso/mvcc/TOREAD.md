# TOREAD — mvcc

Levels refer to [../../READING.md](../../READING.md).

## Before starting (all of it — this phase is reading-heavy by design)

- [ ] Repo guide: `docs/agent-guides/mvcc.md` — the spec + limitations list
      (the limitations list is the scenario checklist).
- [ ] READING L5: 15-445 MVCC + isolation lectures; then the 15-721 MVCC
      design-decisions lecture (version storage, GC, index management).
- [ ] *An Empirical Evaluation of In-Memory MVCC* (Wu et al., VLDB 2017) —
      the design-space map; place Turso's choices on it as you read the Rust.
- [ ] Jepsen [consistency models map](https://jepsen.io/consistency) — pin
      "snapshot isolation" precisely; know write skew before coding.

## Rust source

- [ ] `cli/mvcc_repl.rs` — read first: the scenarios it can express are your
      behavioral target.
- [ ] `core/mvcc/database/` — version storage + commit logic.
- [ ] `core/mvcc/cursor.rs` — how reads thread visibility.
- [ ] Skim: `core/mvcc/persistent_storage/` — what durability means for
      versions (note for the mechanism-we-dont-port doc).

## Prereqs from your own docs

- [ ] `docs/io/explanation/ioresult-as-generators.md` — the scheduler is its
      biggest payoff.
- [ ] `docs/storage/explanation/why-wal.md` + `docs/api/explanation/who-owns-what.md`
      — the single-version world you are about to generalize.

## Docs you will write

`visibility-rules.md` · `scenario-catalog.md` ·
`snapshot-isolation-concretely.md` · `mechanism-we-dont-port.md` ·
`two-transactions-one-row.md` tutorial · conflict + interleaving how-tos.
Status: `docs/mvcc/README.md`.
