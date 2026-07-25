# Public API Reference

**Status:** current · **Phase:** 5+

## Database

```python
from pyturso.database import Database

# Open a database file
db = Database.open("path/to/file.db")

# Create an in-memory database
db = Database.open_memory()

# Open from raw bytes
db = Database.from_bytes(raw_bytes)

# Open a connection
conn = db.connect()

# Close
db.close()
```

## Connection

```python
# Execute SQL (returns list of result rows for SELECT)
rows = conn.execute("SELECT * FROM t WHERE x > 1")

# Prepare (returns a VDBE Program)
prog = conn.prepare("SELECT * FROM t")

# Transaction control
conn.execute("BEGIN")
conn.execute("COMMIT")
conn.execute("ROLLBACK")

# PRAGMA
info = conn.execute("PRAGMA table_info(t)")

# Properties
conn.schema       # Schema (cached, lazy-loaded)
conn.in_transaction  # bool
```

## Statement

```python
from pyturso.statement import Statement

stmt = Statement(prog, db.pager)

# Step (returns one row or None)
row = stmt.step()

# Run (returns all rows)
rows = stmt.run()

# Reset
stmt.reset()

# Finalize
stmt.finalize()

# Iterate
for row in stmt:
    print(row)
```

## Value

```python
from pyturso.types.value import Value

Value.null()
Value.integer(42)
Value.real(3.14)
Value.text("hello")
Value.blob(b"\x00\xff")

v.is_null, v.is_integer, v.is_real, v.is_text, v.is_blob
v.type_of()  # StorageClass
```

## Result rows

Each result row is a `tuple[Value, ...]`:

```python
rows = conn.execute("SELECT id, name FROM t")
for row in rows:
    id_val = row[0]    # Value
    name_val = row[1]  # Value
    print(id_val.payload, name_val.payload)
```