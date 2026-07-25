# docs/translate — Doc index

Module: [pyturso/translate/](../../pyturso/translate/README.md) ·
Rust: `core/translate/` (see also `core/translate/optimizer/OPTIMIZER.md`)

## Planned documents

### tutorials/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `compile-your-first-select.md` | 5 | planned | AST → plan → bytecode for one query, inspecting each IR |
| `how-group-by-really-executes.md` | 10 | planned | sorter-based aggregation, step by step |

### how-to/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `diff-bytecode-against-tursodb.md` | 5 | planned | explain_diff workflow; what differences are expected vs alarming |
| `read-a-query-plan.md` | 9 | planned | from plan repr, predict the bytecode and the I/O pattern |

### reference/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `plan-ir.md` | 5 | planned | the logical plan type, field by field |
| `emission-skeletons.md` | 5 | planned | open/loop/close shapes per statement kind |
| `constraint-extraction.md` | 9 | planned | which WHERE shapes become index constraints |
| `cost-model.md` | 9 | planned | constants and formulas, with the Rust values cited |

### explanation/
| Doc | Phase | Status | Abstract |
|---|---|---|---|
| `three-stage-compilation.md` | 5 | planned | why plan before emit; what each stage may and may not know |
| `how-a-query-picks-its-indexes.md` | 9 | planned | worked examples: flip seq-scan→index by changing a predicate |
| `optimizer-is-an-optimization.md` | 9 | planned | correctness never depends on it — the always-seq-scan baseline |
