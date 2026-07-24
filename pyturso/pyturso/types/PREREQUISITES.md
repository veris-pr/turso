# PREREQUISITES — types

Gate before [TODO.md](TODO.md). Cites resolve in
[READING.md](../../READING.md#citation-index).

- [ ] Two's-complement at widths 8/16/24/32/48/64 — encode −1 and the
      min/max values at each width by hand. → CS:APP ch. 2 (T).
- [ ] IEEE-754 doubles: sign/exponent/mantissa, why integers above 2^53
      lose exactness (this exact fact drives INTEGER↔REAL comparison
      code). → CS:APP ch. 2.
- [ ] Manifest typing: types on *values* not columns, and how that differs
      from every other SQL engine you've used. → SQLite Datatypes doc (D)
      — read in full; it is this module's spec.
- [ ] Affinity as a *coercion preference*, not a constraint — and that
      *when* it applies matters as much as *what* it does. → Datatypes doc
      §type affinity.
- [ ] Collation vs comparison: ordering text is a policy decision (BINARY
      vs NOCASE vs RTRIM). → Datatypes doc §collating sequences.
- [ ] Python-specific trap: `int` is unbounded — every i64 overflow
      behavior must be *emulated*, and Python's `round()` is banker's
      rounding while C's isn't. Be able to state both traps before
      writing `numeric.py`.
- [ ] From Phase 1's output: the record format (header of serial types +
      body). → your own `docs/storage/reference/varints-and-serial-types.md`.
