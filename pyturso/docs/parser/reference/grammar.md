# Grammar scope ledger — reference

**Status:** current · **Phase:** 3 · **Cites:** `pyturso/parser/parser.py`;
Rust: `sqlite/parser/src/parser.rs`.

Every SQL construct pyturso's parser handles, tracked as supported / planned /
out-of-scope. No silent gaps — a construct not listed here is **rejected** with
a clean `ParseError`.

## Supported (Phase 3)

| Construct | Status | Notes |
|---|---|---|
| `SELECT *` | ✅ | bare star |
| `SELECT t.*` | ✅ | table-qualified star |
| `SELECT expr` | ✅ | expression result columns |
| `SELECT expr AS alias` | ✅ | explicit alias |
| `SELECT expr alias` | ✅ | implicit alias (no AS) |
| `SELECT DISTINCT` | ✅ | |
| `SELECT ALL` | ✅ | |
| `FROM table` | ✅ | single table, no joins |
| `FROM table alias` | ✅ | table alias (AS or implicit) |
| `WHERE expr` | ✅ | |
| `ORDER BY expr [ASC\|DESC]` | ✅ | multiple sort keys |
| `LIMIT expr [OFFSET expr]` | ✅ | |
| `GROUP BY expr, ...` | ✅ | parsed (no aggregation execution until Phase 10) |
| `HAVING expr` | ✅ | parsed |
| `INSERT INTO t VALUES (...)` | ✅ | multiple value tuples |
| `INSERT INTO t (cols) VALUES (...)` | ✅ | column list |
| `INSERT OR REPLACE/IGNORE/FAIL/ABORT/ROLLBACK` | ✅ | conflict resolution |
| `UPDATE t SET col=expr WHERE ...` | ✅ | multiple assignments |
| `DELETE FROM t WHERE ...` | ✅ | |
| `CREATE TABLE` | ✅ | column defs, type names, constraints |
| `CREATE TABLE IF NOT EXISTS` | ✅ | |
| `CREATE TABLE ... WITHOUT ROWID` | ✅ | |
| `INTEGER PRIMARY KEY` | ✅ | with AUTOINCREMENT |
| `NOT NULL` | ✅ | column constraint |
| `UNIQUE` | ✅ | column + table constraint |
| `DEFAULT` | ✅ | literal or expression |
| `CHECK` | ✅ | column + table constraint |
| `CREATE INDEX` | ✅ | |
| `CREATE UNIQUE INDEX` | ✅ | |
| `CREATE INDEX IF NOT EXISTS` | ✅ | |
| `CREATE INDEX ... WHERE` | ✅ | partial index |
| `DROP TABLE [IF EXISTS]` | ✅ | |
| `DROP INDEX [IF EXISTS]` | ✅ | |
| `BEGIN [DEFERRED\|IMMEDIATE\|EXCLUSIVE]` | ✅ | optional TRANSACTION |
| `COMMIT` / `END` | ✅ | optional TRANSACTION |
| `ROLLBACK` | ✅ | optional TRANSACTION |

## Expression operators (by precedence, highest binds tightest)

| Precedence | Operators | Status |
|---|---|---|
| 0 | `OR` | ✅ |
| 1 | `AND` | ✅ |
| 3 | `NOT`, `=`, `!=`, `<>`, `IS`, `IS NOT`, `BETWEEN`, `IN`, `LIKE`, `GLOB`, `REGEXP`, `MATCH`, `ISNULL`, `NOTNULL` | ✅ |
| 4 | `<`, `>`, `<=`, `>=` | ✅ |
| 6 | `&`, `\|`, `<<`, `>>` | ✅ |
| 7 | `+`, `-` | ✅ |
| 8 | `*`, `/`, `%` | ✅ |
| 9 | `\|\|`, `->` | ✅ |
| 10 | `COLLATE` | ✅ |
| 11 (unary) | `-`, `+`, `~`, `NOT` | ✅ |

## Expression operands

| Operand | Status | Notes |
|---|---|---|
| `NULL` | ✅ | |
| `TRUE` / `FALSE` | ✅ | SQLite 3.23+ |
| Integer literal | ✅ | decimal + hex (`0x...`) |
| Float literal | ✅ | `.5`, `1.5`, `1e5` |
| String literal | ✅ | `'...'` with `''` escape |
| Blob literal | ✅ | `x'...'` |
| Parameter | ✅ | `?`, `?N`, `:name`, `$name` (parsed as keyword literal) |
| Identifier | ✅ | bare, `"quoted"`, `` `backtick` ``, `[bracket]` |
| Qualified name | ✅ | `table.col`, `schema.table.col` |
| Function call | ✅ | `func(args)`, `func(DISTINCT args)`, `COUNT(*)` |
| Parenthesized | ✅ | `(expr)` |
| `CAST(expr AS type)` | ✅ | |
| `CASE ... WHEN ... THEN ... ELSE ... END` | ✅ | |
| Unary `- + ~ NOT` | ✅ | |

## Planned (later phases)

| Construct | Phase | Notes |
|---|---|---|
| `JOIN` (INNER, LEFT, RIGHT, CROSS, NATURAL) | 9 | |
| `UNION / INTERSECT / EXCEPT` | 10 | compound queries |
| `WITH` (CTEs) | 10 | |
| Subqueries in expressions | 9 | |
| `RETURNING` clause | 10 | |
| `ALTER TABLE` | 10 | |
| Window functions (`OVER`, `PARTITION BY`) | 10 | |
| `EXPLAIN` / `EXPLAIN QUERY PLAN` | 9 | |
| Named parameters full binding | 5 | currently parsed as keyword literal |

## Out of scope

| Construct | Reason |
|---|---|
| `ATTACH` / `DETACH` | multi-database attach — not in scope |
| `PRAGMA` | Phase 10 ride-along |
| `CREATE TRIGGER` | trigger support — Phase 10+ |
| `CREATE VIEW` | Phase 10 |
| `VACUUM` | not in scope |
| `ANALYZE` | not in scope |
| Vector/struct/union types | Turso extensions — later |