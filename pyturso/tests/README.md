# tests — Verification

Two layers, complementary and both mandatory per phase
(see [../PLAN.md](../PLAN.md) §3):

| Layer | Location | Question it answers |
|-------|----------|---------------------|
| Unit | [unit/](unit/README.md) | "Is this module internally correct?" — fast, pure-Python, pytest |
| Differential | [differential/](differential/README.md) | "Does the whole engine behave like sqlite3 and tursodb?" — the parity gate |

## Policy (mirrors the repo's testing doctrine, adapted)

- **Every change needs a test that fails without it.** Same rule as the Rust
  codebase (`CLAUDE.md` core principles), no exceptions for "obvious" code.
- **Behavioral tests go in the differential corpus**, not unit tests — if it
  can be expressed as SQL-in/rows-out, it belongs in the corpus where all
  three engines check it.
- **Unit tests cover what SQL can't reach**: varint edge encodings, page
  layouts, cursor state machines, builder label patching, crash-injection
  points.
- **Rust-only tests are not ported.** Turso tests that exercise Rust handling
  (ownership, panics, sanitizers, async machinery) have no behavioral content
  to port. Turso tests that exercise *SQL behavior* (`.sqltest` files) are
  ported selectively — tracked in `differential/corpus/from_sqltest/MANIFEST.md`.
- **Determinism**: fixed seeds for randomized tests (recorded in the test),
  injected clock for anything time-dependent.

Run everything:

```bash
python -m pytest tests/unit
python -m tests.differential.run tests/differential/corpus
```
