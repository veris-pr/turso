# docs/types — Doc index

Module: [pyturso/types/](../../pyturso/types/README.md) ·
Rust: `core/types.rs`, `core/vdbe/value.rs`, `core/vdbe/affinity.rs`, `core/numeric/`

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `decode-a-record-by-hand.md` | 2 | planned | take real record bytes from a fixture DB, decode header + payloads manually, check with code |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `add-a-corpus-case-for-a-coercion-rule.md` | 2 | planned | turn a suspected type edge into a three-way-verified case |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `serial-types.md` | 2 | current | the full table incl. 8/9 constants, sizes, examples |
| `affinity-rules.md` | 2 | current | type-name → affinity resolution; when affinity applies |
| `comparison-order.md` | 2 | current | cross-class total order, numeric cross-compare, collations |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `manifest-typing.md` | 2 | planned | types on values not columns; why, and what it costs/buys |
| `integers-floats-and-text-numbers.md` | 2 | planned | i64 emulation in Python, overflow-to-REAL, '10'=10 and friends |
