# PREREQUISITES — tests/differential

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] Differential testing as a method: same input to N implementations,
      disagreement = signal; why it finds bugs specifications miss.
      → W. M. McKeeman, *Differential Testing for Software* (P, 1998) —
      short, foundational, worth the hour.
- [ ] Oracle discipline: expected outputs are *recorded* from oracles,
      never hand-written; why hand-written expectations rot into a third
      implementation. → SQLite *How SQLite Is Tested* (D).
- [ ] Normalization pitfalls: float rendering, NULL representation,
      ordering guarantees (multiset vs sequence), error message vs error
      class — each is a false-positive factory if unhandled. Be able to
      name all five before designing the comparator.
- [ ] Python stdlib `sqlite3` behaviors the adapter leans on:
      `executescript` semantics, exception classes, type mapping. → Python
      docs.
- [ ] subprocess with timeouts and crash detection (the tursodb adapter).
- [ ] Determinism as a requirement: fixed seeds, injected time, stable
      fixture generation — flaky differential runs are worse than none.
      → the FoundationDB deterministic-simulation talk (B) for the creed.
