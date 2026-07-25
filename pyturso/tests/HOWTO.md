# HOWTO — tests

Deciding where a test goes (policy details in [README.md](README.md)):

- Expressible as SQL-in/rows-out? -> differential corpus
  ([differential/](differential/HOWTO.md)). It gets three-way verification
  for free.
- Internal invariant, binary edge, state machine, injected crash? ->
  [unit/](unit/HOWTO.md).
- Testing Rust mechanics? -> it is not ported (see README policy).

The iron rule from the repo's own doctrine: **every change lands with a test
that fails without it**. Run before any commit:

    python -m pytest tests/unit
    python -m tests.differential.run tests/differential/corpus
