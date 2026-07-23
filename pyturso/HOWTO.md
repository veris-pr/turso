# HOWTO — working this project

How to actually execute [PLAN.md](PLAN.md), day to day. Every folder below
this one has its own HOWTO.md with folder-specific work; this one is the outer
loop.

## Running a phase

1. **Open PLAN.md at the phase.** Note its build list, Rust reading list,
   docs deliverables, and exit criteria. The exit criteria are the phase's
   to-do list — red gates are work, not failure.
2. **Read first.** Work through the module's `TOREAD.md` (its slice of
   [READING.md](READING.md), the repo guides, and the Rust files) for data
   flow and invariants. Log every question you can't answer as a stub note in
   the target module's `docs/<module>/explanation/` — that backlog becomes
   the explanation docs.
3. **Work the module folders.** Each `pyturso/<module>/HOWTO.md` gives the
   internal work order; its `TODO.md` is the checkbox-level task list —
   check items off in commits. Stub files already name their Rust
   counterparts.
4. **Test as you go.** Unit tests next to each internal invariant
   ([tests/unit/HOWTO.md](tests/unit/HOWTO.md)); behavioral cases into the
   phase's corpus directory
   ([tests/differential/corpus/HOWTO.md](tests/differential/corpus/HOWTO.md)).
   Every change lands with a test that fails without it.
5. **Write the phase's docs** ([docs/HOWTO.md](docs/HOWTO.md)). A phase is
   not done without them.
6. **Run the gates:**

   ```bash
   python -m pytest tests/unit
   python -m tests.differential.run tests/differential/corpus
   mypy pyturso
   ```

7. **Close the loop.** Re-read the phase's Rust; update the "In Turso"
   sections with what the Rust does that your port doesn't. Check every exit
   criterion. Only then move on — never two phases in flight (except the
   2/3/4 window).

## Resuming cold

Read PLAN.md's phase table, `git log --oneline -20`, then the HOWTO of the
folder you were in. The corpus report tells you exactly what works
(PASS / NOT-IMPLEMENTED / DIVERGENT per case) — it is the project's honest
status page.

## Standing conventions (enforced every commit)

- Stdlib only at runtime; Python ≥ 3.11; full type annotations,
  `mypy --strict` clean.
- Names mirror the Rust (`Pager`, `BTreeCursor`, `ProgramBuilder`, `Insn`) so
  cross-reading stays mechanical.
- Anything that does I/O in Rust via `IOResult` is a generator here —
  no hidden blocking calls inside engine code
  ([pyturso/io/HOWTO.md](pyturso/io/HOWTO.md)).
- Corrupt input raises, never returns garbage. Crash > corrupt.
- Unsupported SQL is *rejected* with a clean not-supported error — the scope
  ledgers stay honest.

## When pyturso disagrees with the oracles

1. Reproduce minimal (one statement, tiny fixture).
2. `sqlite3` vs `tursodb` disagree? Quarantine the case; if turso's behavior
   looks unintended, that's an upstream bug report — file it (this is the
   contribution pipeline this project feeds).
3. pyturso alone diverges: read the Rust counterpart *before* debugging your
   Python blind — the answer is usually a rule you didn't know existed
   (affinity, NULL logic, overflow). Then add the corpus case that pins it.
