# TODO — tests/differential (Phase 0, grows forever)

Build order rationale: [HOWTO.md](HOWTO.md).

- [x] Engine adapter protocol: `run_script(sql_text, db_path) ->
      list[Rows | ErrorClass]` implemented three ways.
- [x] sqlite3 adapter (stdlib, in-process).
- [x] tursodb adapter: `TURSODB_BIN` env or `cargo run -q --bin tursodb`
      fallback; output parsing; timeout + crash surfaced as distinct verdict.
- [x] pyturso adapter (returns NOT-IMPLEMENTED cleanly until Phase 5).
- [x] Normalization module (pure functions + unit tests): canonical row
      rendering, %.15g floats, NULL literal, blob hex, error-class mapping
      per engine.
- [x] Comparator: multiset default, ordered iff ORDER BY present.
- [x] Front-matter parsing: `-- setup: fixture=…`, `-- expect-error: …`.
- [x] Reporter: per-case verdict (PASS / DIVERGENT / NOT-IMPLEMENTED /
      ORACLE-DISAGREEMENT / ERROR) + summary; nonzero exit on red.
- [x] Corpus discovery + name filtering (`-k` style) + `--phase` filter.
- [x] Expectation recording flag (`--record`) writing oracle output
      sidecars; never hand-written.
- [x] `_quarantine/` handling: discovered but reported separately, never
      counted green.
- [x] **Phase 0 gate:** trivial corpus runs; sqlite3 ≡ tursodb on it;
      pyturso reports NOT-IMPLEMENTED without crashing.
- [x] Phase 7 ride-alongs: write-path corpus tests (test_phase7_corpus.py)
      writing cases.
- [x] Phase 11: scripted two-connection mode (mvcc/scheduler.py + mvcc/visibility_rules.py)
      `mvcc.scheduler`), turso-only oracle.
