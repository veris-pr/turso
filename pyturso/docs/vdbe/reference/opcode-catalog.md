# VDBE Opcode Catalog

**Status:** current · **Phase:** 5+

Every VDBE opcode pyturso implements, with its Rust counterpart and status.

## Implemented opcodes (30+)

| Opcode | Rust counterpart | Phase | Description |
|---|---|---|---|
| `Init` | `Op::Init` | 5 | Jump to program start |
| `Transaction` | `Op::Transaction` | 5 | Begin a transaction |
| `OpenRead` | `Op::OpenRead` | 5 | Open a cursor for reading |
| `OpenWrite` | `Op::OpenWrite` | 7 | Open a cursor for writing |
| `Rewind` | `Op::Rewind` | 5 | Move cursor to first row |
| `Column` | `Op::Column` | 5 | Read a column from the cursor |
| `Rowid` | `Op::Rowid` | 5 | Read the rowid from the cursor |
| `ResultRow` | `Op::ResultRow` | 5 | Emit result row from registers |
| `Next` | `Op::Next` | 5 | Advance cursor, loop if row available |
| `Halt` | `Op::Halt` | 5 | Stop the program |
| `Integer` | `Op::Integer` | 5 | Load an integer into a register |
| `Real` | `Op::Real` | 5 | Load a float into a register |
| `String8` | `Op::String8` | 5 | Load a string into a register |
| `Null` | `Op::Null` | 5 | Load NULL into a register |
| `Goto` | `Op::Goto` | 5 | Unconditional jump |
| `Eq` | `Op::Eq` | 5 | Jump if r[lhs] == r[rhs] |
| `Ne` | `Op::Ne` | 5 | Jump if r[lhs] != r[rhs] |
| `Lt` | `Op::Lt` | 5 | Jump if r[lhs] < r[rhs] |
| `Le` | `Op::Le` | 5 | Jump if r[lhs] <= r[rhs] |
| `Gt` | `Op::Gt` | 5 | Jump if r[lhs] > r[rhs] |
| `Ge` | `Op::Ge` | 5 | Jump if r[lhs] >= r[rhs] |
| `Add` | `Op::Add` | 6 | r[dest] = r[r1] + r[r2] |
| `Subtract` | `Op::Subtract` | 6 | r[dest] = r[r1] - r[r2] |
| `Multiply` | `Op::Multiply` | 6 | r[dest] = r[r1] * r[r2] |
| `Divide` | `Op::Divide` | 6 | r[dest] = r[r1] / r[r2] (NULL if r2=0) |
| `Remainder` | `Op::Remainder` | 6 | r[dest] = r[r1] % r[r2] (NULL if r2=0) |
| `Concat` | `Op::Concat` | 6 | r[dest] = r[r1] \|\| r[r2] (string concat) |
| `Function` | `Op::Function` | 6 | Call a scalar function |
| `IsNull` | `Op::IsNull` | 6 | Jump if r[reg] is NULL |
| `NotNull` | `Op::NotNull` | 6 | Jump if r[reg] is NOT NULL |
| `Copy` | `Op::Copy` | 6 | Copy r[src] to r[dest] |
| `NewRowid` | `Op::NewRowid` | 7 | Allocate a new rowid |
| `MakeRecord` | `Op::MakeRecord` | 7 | Build a record from registers |
| `Insert` | `Op::Insert` | 7 | Insert a record into a cursor |

## Planned opcodes (future phases)

| Opcode | Phase | Description |
|---|---|---|
| `If` / `IfNot` | 6 | Conditional jump on register truthiness |
| `Delete` | 7 | Delete the current row from a cursor |
| `SeekGE` / `SeekGT` / `SeekLE` / `SeekLT` | 9 | Index seek operations |
| `IdxRowid` | 9 | Get rowid from index cursor |
| `SorterOpen` / `SorterInsert` / `SorterSort` / `SorterNext` | 10 | Sorter cursor operations |
| `AggStep` / `AggFinal` | 10 | Aggregate step/finalize |
| `OpenPseudo` | 10 | Open a pseudo-table cursor |
| `Last` / `Prev` | 10 | Reverse-order cursor traversal |
| `Sequence` / `SequenceSeq` | 10 | Autoincrement sequence |