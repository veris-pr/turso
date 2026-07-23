# TOREAD — types

Levels refer to [../../READING.md](../../READING.md).

## Before starting

- [ ] SQLite [Datatypes doc](https://sqlite.org/datatype3.html) — the
      manifest-typing spec: storage classes, affinity, comparison rules.
      This page *is* the module; read it twice, keep it open while coding.
- [ ] SQLite File Format doc, record-format section (serial-type table).
- [ ] READING L1: CS:APP ch. 2 (integer & float representation) — two's
      complement widths and IEEE-754 are daily tools here.
- [ ] Prereq from earlier modules: your own
      `docs/storage/reference/varints-and-serial-types.md` (Phase 1 output).

## Rust source

- [ ] `core/types.rs` — `Value`, records, serial types.
- [ ] `core/vdbe/value.rs` — runtime value ops.
- [ ] `core/vdbe/affinity.rs` — the affinity rule order (port verbatim).
- [ ] `core/numeric/` — text→number parsing and overflow behavior.
- [ ] `core/translate/collate.rs` — collation resolution (skim now; matters
      again in translate Phase 6).

## While building

- [ ] READING L3: 15-445 lecture segment on data layouts/tuple storage —
      places SQLite's record format among the alternatives.
- [ ] Python `struct` module docs (big-endian formats) — your `encode`
      toolbox.

## Docs you will write

Three reference docs (see TODO) + `manifest-typing.md` and
`integers-floats-and-text-numbers.md` explanations, both closing with
"In Turso" sections. Status table: `docs/types/README.md`.
