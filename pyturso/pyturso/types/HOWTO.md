# HOWTO — types

What the module is: [README.md](README.md). Phase 2, after the Phase 1 reader
exists (records come from real pages, so you can check against reality
immediately).

## Work order

1. **`value.py`** — the `Value` type. Read `core/vdbe/value.rs` first. Keep
   it a tagged, immutable value; arithmetic/coercion as functions or methods
   that mirror the Rust op names.
2. **`serial.py`** — the serial-type table. Encode/decode against bytes.
   Watch: types 8/9 (literal 0/1, zero payload bytes) and the 1..6 integer
   widths (1,2,3,4,6,8 bytes, big-endian, two's complement).
3. **`record.py`** — header (varint count + serial types) + body. Depends on
   the varint code in `storage/sqlite3_ondisk.py` — import it, don't
   duplicate it. Refactor Phase 1's raw record decoding to sit on top of this
   module once it lands (one record implementation, not two).
4. **`affinity.py`** — the type-name → affinity resolution rules and *when*
   affinity applies (storage, comparison operands). Port the rule order
   exactly from `core/vdbe/affinity.rs`.
5. **`compare.py`** — cross-class total order (NULL < numeric < TEXT < BLOB),
   INTEGER↔REAL cross-compare, collations (BINARY, NOCASE, RTRIM).
6. **`numeric.py`** — text→number parsing (prefix parsing rules!), i64
   emulation, overflow-to-REAL. Python ints don't wrap: mask/check at i64
   bounds explicitly wherever the Rust does i64 arithmetic.

## Verify

- Property tests: `decode(encode(v)) == v` for every serial type, width
  boundaries ±1.
- Corpus: a mixed-type column ORDER BY case (the single best full-ordering
  check); coercion matrix cases in `phase6_where` once Phase 6 runs them —
  until then pin behavior with unit tests against stdlib sqlite3 directly.

## Gotchas (each becomes a corpus case when executable)

`'10' = 10` in different contexts · `1 = 1.0` and hashing/uniqueness ·
`CAST` truncation rules · negative zero · REAL that is integral choosing
serial type 7 vs integer types on write · NOCASE is ASCII-only.
