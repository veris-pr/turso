# PREREQUISITES — functions

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] Three-valued logic as it applies to functions: most propagate NULL,
      and the named exceptions (`coalesce`, `count`, `ifnull`, `nullif`) —
      state the rule and the exceptions from memory. → SQLite core
      functions doc (D).
- [ ] Case folding is locale-trouble: why `upper()`/NOCASE are ASCII-only
      in SQLite and what Python's `str.upper()` would wrongly do to 'ß'
      or dotted-i. Know the trap before porting string functions.
- [ ] Float formatting: what `%.15g` means and why output formatting is
      part of *parity*, not cosmetics.
- [ ] C-style rounding vs Python's banker's rounding (`round(2.5)`).
- [ ] Time systems: Julian day numbers, Unix epoch, UTC vs localtime —
      enough to read the date-function spec without guessing. → SQLite
      date/time functions doc (D).
- [ ] Scalar vs aggregate calling conventions: per-row call vs
      step/finalize state machine. → SQLite aggregate functions doc (D).
- [ ] Working prereqs green: types module (affinity/coercion — function
      args coerce by its rules), `io.clock` for injectable time.
