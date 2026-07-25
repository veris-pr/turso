# Dot-Command Parity Table

**Status:** current · **Phase:** 12

| Command | pyturso | tursodb | Notes |
|---|---|---|---|
| `.quit` | ✅ | ✅ | Exits the REPL |
| `.exit` | ✅ | ✅ | Alias for .quit |
| `.tables` | ✅ | ✅ | Lists all tables in the schema |
| `.schema` | ✅ | ✅ | Prints CREATE TABLE statements |
| `.schema <table>` | ✅ | ✅ | Prints schema for a specific table |
| `.open <path>` | ✅ | ✅ | Opens a new database (simplified) |
| `.mode <mode>` | ✅ | ✅ | Sets output mode (list/table/line) |
| `.read <file>` | ✅ | ✅ | Reads and executes SQL from a file |
| `.explain on\|off` | ✅ | ✅ | Toggles EXPLAIN mode (acknowledged) |
| `.help` | ✅ | ✅ | Lists available commands |
| `.databases` | ❌ | ✅ | Not implemented (single-database only) |
| `.dump` | ❌ | ✅ | Not implemented (use tools/dbdump.py) |
| `.indices` | ❌ | ✅ | Not implemented (use PRAGMA index_list) |
| `.nullvalue` | ❌ | ✅ | Not implemented (NULL renders as empty) |
| `.separator` | ❌ | ✅ | Not implemented (pipe separator only) |
| `.show` | ❌ | ✅ | Not implemented |
| `.width` | ❌ | ✅ | Not implemented (table mode only) |
| `.timer` | ❌ | ✅ | Not implemented |
| `.stats` | ❌ | ✅ | Not implemented |