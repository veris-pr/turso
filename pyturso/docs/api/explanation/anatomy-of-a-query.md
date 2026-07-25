# Anatomy of a Query — capstone explanation

**Status:** current · **Phase:** 5+ (grows every phase)

> This document traces a single SQL query through every layer of pyturso,
> from text to result rows. It is the project's single best artifact for
> understanding how the engine works as a whole.

## The query

```sql
SELECT name, age FROM employees WHERE dept = 'eng' AND age > 25 ORDER BY age DESC
```

## Layer 1: Parser (Phase 3)

The SQL text enters the parser:

1. **Lexer** (`pyturso/parser/lexer.py`) tokenizes the text into a stream of
   `Token` objects: `[SELECT, ID("name"), COMMA, ID("age"), FROM, ID("employees"),
   WHERE, ID("dept"), EQ, STRING("eng"), AND, ID("age"), GT, INTEGER("25"),
   ORDER, BY, ID("age"), DESC, EOF]`.

2. **Parser** (`pyturso/parser/parser.py`) consumes the token stream via
   recursive descent with precedence climbing. It produces an AST:
   ```
   Select(
     body=SelectBody(select=OneSelect(
       columns=[ResultColumn(expr=IdExpr("name")),
                ResultColumn(expr=IdExpr("age"))],
       from_clause=FromClause(table=SelectTable(name="employees")),
       where=BinaryExpr(And,
         BinaryExpr(Eq, IdExpr("dept"), LiteralExpr("eng")),
         BinaryExpr(Gt, IdExpr("age"), LiteralExpr("25"))),
     )),
     order_by=[SortedColumn(expr=IdExpr("age"), order=Desc)],
   )
   ```

## Layer 2: Planner (Phase 5)

The planner (`pyturso/translate/planner.py`) resolves names against the schema:

1. Look up `employees` in the `Schema` → find the `Table` object with root
   page, columns, and rowid-alias flag.
2. Bind `name` → column index 1, `age` → column index 2, `dept` → column 3.
3. Build a `Plan` with the source table, WHERE terms, and result columns.

## Layer 3: Optimizer (Phase 9)

The optimizer (`pyturso/translate/optimizer/`) extracts constraints from the
WHERE clause: `dept = 'eng'` is an equality constraint on column 3; `age > 25`
is a range constraint on column 2. If an index matches `dept`, the optimizer
chooses an `IndexSeek` access method; otherwise `SeqScan`.

## Layer 4: Emitter (Phase 5)

The emitter (`pyturso/translate/emitter/select.py`) turns the plan into VDBE
opcodes using the `ProgramBuilder`:

```
0  Init          → start
1  Transaction
2  OpenRead      cursor=0, root=2
3  Rewind        cursor=0, if_empty=end
4  Column        cursor=0, col=3, dest=r1    (dept)
5  String8       "eng", dest=r2
6  Ne            r1, r2, skip                (jump if dept != 'eng')
7  Column        cursor=0, col=2, dest=r3    (age)
8  Integer       25, dest=r4
9  Le            r3, r4, skip                (jump if age <= 25)
10 Column        cursor=0, col=1, dest=r5    (name)
11 Column        cursor=0, col=2, dest=r6    (age)
12 ResultRow     start=r5, count=2
13 Next          cursor=0, if_next=loop
14 Halt
```

## Layer 5: VDBE (Phase 5)

The executor (`pyturso/vdbe/execute.py`) runs the program:

1. `Init` jumps to the body.
2. `Transaction` starts a read transaction.
3. `OpenRead` creates a `BTreeCursor` on the table's root page.
4. `Rewind` positions the cursor at the first row.
5. For each row:
   - `Column` reads the `dept` value from the record.
   - `Ne` compares it with `'eng'` — jump to skip if not equal.
   - `Column` reads `age`.
   - `Le` compares with 25 — jump to skip if ≤ 25.
   - `Column` reads `name` and `age` into result registers.
   - `ResultRow` emits the registers as a result row.
   - `Next` advances the cursor.
6. When the cursor is exhausted, `Halt` stops the program.

## Layer 6: Result

The `Connection.execute()` method collects the result rows (a list of
`tuple[Value, ...]`) and applies ORDER BY post-processing (sorting by `age`
descending). The caller receives the sorted rows.

## What each phase adds

- **Phase 5**: the basic scan loop (Init → OpenRead → Rewind → Column →
  ResultRow → Next → Halt).
- **Phase 6**: WHERE expression compilation (AND/OR, comparisons, CASE,
  BETWEEN, IN, LIKE, functions).
- **Phase 9**: index-based access (seek instead of scan when an index matches).
- **Phase 10**: compound SELECTs, subqueries, DISTINCT, GROUP BY, aggregates.