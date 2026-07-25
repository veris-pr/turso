# Serial types — reference

**Status:** current · **Phase:** 2 · **Cites:** `pyturso/types/serial.py`;
Rust: `core/types.rs` (`SerialType`, `SerialTypeKind`, `From<T> for SerialType`,
`SerialType::size`, `read_value`, `serialize_serial`).

Every value in a SQLite record is preceded by a **serial type** — a varint
that identifies the value's on-disk encoding and width. This table is the
canonical reference.

## Serial type table

| Serial type | Kind | Payload bytes | Decodes to |
|---|---|---|---|
| 0 | NULL | 0 | `Value.null()` |
| 1 | I8 | 1 | `Value.integer(i8, big-endian signed)` |
| 2 | I16 | 2 | `Value.integer(i16, big-endian signed)` |
| 3 | I24 | 3 | `Value.integer(i24, sign-extended to i32)` |
| 4 | I32 | 4 | `Value.integer(i32, big-endian signed)` |
| 5 | I48 | 6 | `Value.integer(i48, sign-extended to i64)` |
| 6 | I64 | 8 | `Value.integer(i64, big-endian signed)` |
| 7 | F64 | 8 | `Value.real(f64, big-endian IEEE 754)` |
| 8 | ConstInt0 | 0 | `Value.integer(0)` (zero payload bytes) |
| 9 | ConstInt1 | 0 | `Value.integer(1)` (zero payload bytes) |
| 10 | — | — | **invalid** (raises `Corrupt`) |
| 11 | — | — | **invalid** (raises `Corrupt`) |
| ≥12 even | BLOB | `(st - 12) / 2` | `Value.blob(bytes)` |
| ≥13 odd | TEXT | `(st - 13) / 2` | `Value.text(UTF-8 decoded)` |

## Minimal-width integer encoding

When encoding an `INTEGER` to a record, pyturso chooses the **narrowest** serial
type that fits the value (ports `From<T> for SerialType`):

| Value range | Serial type |
|---|---|
| `0` | 8 (const 0, 0 bytes) |
| `1` | 9 (const 1, 0 bytes) |
| `[-128, 127]` | 1 (i8) |
| `[-32768, 32767]` | 2 (i16) |
| `[-8388608, 8388607]` | 3 (i24) |
| `[-2³¹, 2³¹-1]` | 4 (i32) |
| `[-2⁴⁷, 2⁴⁷-1]` | 5 (i48) |
| otherwise | 6 (i64) |

## Sign extension

I24 and I48 are not standard C types — they use 3 and 6 bytes respectively.
Sign extension is done by repeating the top bit:

- **I24**: 3 bytes → pad to 4 with a sign byte (`0xFF` if high bit set, else `0x00`).
- **I48**: 6 bytes → pad to 8 with two sign bytes.

## API

| Function | Signature | Description |
|---|---|---|
| `serial_type_size(st)` | `int → int` | payload bytes for a serial type |
| `encode_value(v)` | `Value → (int, bytes)` | serial type + payload bytes |
| `decode_value(st, buf)` | `int, bytes → Value` | decode a serial type from bytes |
| `is_valid_serial_type(n)` | `int → bool` | 10 and 11 are invalid |