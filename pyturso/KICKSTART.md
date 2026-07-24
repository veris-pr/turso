# KICKSTART.md — prompt for delegating build steps to an LLM

A reusable prompt for driving the port with any coding model (including
weaker/cheaper ones). It works because the scaffold is the brain: the prompt
only pins scope and forbids improvisation. Fill the two `<...>` blanks per
run.

---

## The prompt (copy from here)

You are implementing one small, pre-planned step of **pyturso**, a Python
port of the Turso database engine located at `pyturso/` in this repository.
All design decisions are already made and written down in the repo. Your job
is execution, not design. Do not invent structure, do not rename things, do
not reorganize, do not touch any file outside `pyturso/`.

**Current assignment:** the first unchecked `[ ]` item in
`pyturso/<MODULE>/TODO.md`. Implement exactly that one item. `<EXTRA NOTES>`

**Before writing any code, read in this order:**
1. `pyturso/HOWTO.md` — the working rules (conventions section especially).
2. `pyturso/<MODULE>/README.md` — what this module is.
3. `pyturso/<MODULE>/HOWTO.md` — the work order and gotchas for this folder.
4. The TODO item itself, plus the Rust source files named in the stub
   docstring of the file you are about to edit (path is in its `Ports:` line).
   Port the *behavior and names* from the Rust; write idiomatic Python.

**Hard rules:**
- Stdlib only. Python 3.11+. Full type annotations. Names mirror the Rust
  (`BTreeCursor`, `ProgramBuilder`, …) as the stubs and READMEs already show.
- Anything that performs I/O must be a generator yielding request objects
  from `pyturso.io` — never call `os.*` or `open()` inside engine code.
  If `pyturso/io/` is not built yet and your item needs it, stop and report.
- On invalid/corrupt input: raise the appropriate error from
  `pyturso/errors.py`. Never return garbage, never silently continue.
- The TODO item ships **with its test in the same change** — a test that
  fails without your code and passes with it. Follow
  `pyturso/tests/unit/HOWTO.md` for where and how.
- Do not modify: `PLAN.md`, `READING.md`, any `README.md`, `HOWTO.md`,
  `TOREAD.md`, or anything under `docs/` — except when the TODO item itself
  names a doc to write, and then only that doc.
- Do not start the next TODO item. One item, then stop.

**Verify before finishing (all must pass):**
```
cd pyturso
python -m pytest tests/unit -q
python -m compileall -q pyturso
```
Also run any check the TODO item itself names (e.g. comparison against
`sqlite3`).

**When done:** tick the item's checkbox in `TODO.md` (that file is the one
exception to the do-not-modify rule), then report: what you implemented,
which Rust file(s) you ported it from, test results, and anything you were
unsure about.

**If you get stuck or something contradicts these files:** stop and report
the contradiction. Do not guess, do not work around it, do not redesign.
An honest "blocked because X" is a successful outcome; improvised structure
is not.

---

## Usage notes

- `<MODULE>` per the phase order in `PLAN.md`. Kickstart sequence:
  1. `pyturso` (errors.py — the Phase 0 item in `pyturso/pyturso/TODO.md`)
  2. `tools` (mkdb.py)
  3. `tests/differential` (the harness, item by item)
  4. `pyturso/io`, then `pyturso/storage` (Phase 1 begins)
- `<EXTRA NOTES>` — usually empty; use it to pass corrections from the
  previous run's report ("the normalization module you wrote last run is at
  tests/differential/normalize.py — reuse it").
- One prompt run = one TODO item = one commit. Review the diff before the
  next run; anything wrong goes back via `<EXTRA NOTES>`.
- Weaker models are fine for mechanical items (varints, serial types,
  lexer tokens, dataclasses, tools). Keep the judgment-heavy items for a
  stronger model or yourself: B-tree balancing (storage Phase 7), affinity
  in comparisons (types/translate Phase 6), WAL recovery (Phase 8) — and
  all `docs/` explanation writing, which is your understanding work, not
  delegable.
