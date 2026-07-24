# TODO — types (Phase 2)

Work order rationale: [HOWTO.md](HOWTO.md).

- [x] `value.py`: `Value` tagged type (NULL/INTEGER/REAL/TEXT/BLOB),
      constructors, `type_of()`, equality that does *not* cross-coerce
      (coercion is explicit, mirroring the Rust).
- [x] `serial.py`: full serial-type table incl. 8/9 constants;
      `serial_size(t)`, `decode(t, bytes)`, `encode(value) -> (t, bytes)`
      choosing the minimal width exactly as the Rust does.
- [x] Property tests: encode/decode round-trip for every type; integer width
      boundaries ±1; REAL bit-exactness (struct '>d').
- [x] `record.py`: parse + build on `storage.sqlite3_ondisk` varints; then
      refactor Phase 1's inline record decoding onto this (one
      implementation — delete the Phase 1 copy).
- [x] `affinity.py`: type-name → affinity rule order ported verbatim from
      `core/vdbe/affinity.rs` (rule order is the spec!); application
      functions for storage and comparison contexts.
- [x] `compare.py`: cross-class total order; INTEGER↔REAL exact comparison
      (beware float precision at |x| > 2^53 — port how the Rust handles it);
      collations BINARY / NOCASE (ASCII-only!) / RTRIM.
- [x] `numeric.py`: text→number prefix parsing, i64 bounds emulation
      (explicit checks — Python ints don't wrap), overflow-to-REAL rules.
- [x] Oracle pin (pre-Phase-6): unit tests comparing mixed-type ORDER BY and
      comparison results against stdlib sqlite3 directly.
- [x] Reference docs: `serial-types.md`, `affinity-rules.md`,
      `comparison-order.md` — written alongside, same commits.

Exit: Phase 2 criteria in PLAN.md (round-trips + mixed ORDER BY parity).
