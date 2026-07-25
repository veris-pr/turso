"""token — token kinds, keyword table, identifier rules.

Ports: sqlite/parser/src/token.rs (TokenType), sqlite/parser/src/lexer.rs
(keyword_or_id_token, is_identifier_start, is_identifier_continue, Token).
Phase: 3
Status: IMPLEMENTED.

The token kinds mirror the Rust ``TokenType`` enum exactly (``TK_*`` names
without the prefix — the HOWTO says to mirror names so cross-reading stays
mechanical). The keyword table maps case-insensitive keyword strings to their
token kinds; any non-keyword identifier-ish word is ``ID``.

Keyword context-sensitivity: in SQLite, many keywords can be used as
identifiers in certain positions (e.g. ``ORDER`` as a column name in
``SELECT order FROM t``). The lexer always produces the keyword token type;
the parser decides whether to treat it as an identifier based on context.
So there is no "may-be-identifier" set in the lexer — that rule lives in the
parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Union

__all__ = ["TokenType", "Token", "KEYWORD_TABLE",
           "is_identifier_start", "is_identifier_continue",
           "keyword_or_id"]


class TokenType(IntEnum):
    """Token kinds. Ports ``sqlite::parser::token::TokenType`` (TK_* prefix dropped)."""

    EOF = 0
    SEMI = 1
    EXPLAIN = 2
    QUERY = 3
    PLAN = 4
    BEGIN = 5
    TRANSACTION = 6
    DEFERRED = 7
    IMMEDIATE = 8
    EXCLUSIVE = 9
    COMMIT = 10
    END = 11
    ROLLBACK = 12
    SAVEPOINT = 13
    RELEASE = 14
    TO = 15
    TABLE = 16
    CREATE = 17
    IF = 18
    NOT = 19
    EXISTS = 20
    TEMP = 21
    LP = 22         # left paren
    RP = 23         # right paren
    AS = 24
    COMMA = 25
    WITHOUT = 26
    ABORT = 27
    ACTION = 28
    AFTER = 29
    ANALYZE = 30
    ASC = 31
    ATTACH = 32
    BEFORE = 33
    BY = 34
    CASCADE = 35
    CAST = 36
    CONFLICT = 37
    DATABASE = 38
    DESC = 39
    DETACH = 40
    EACH = 41
    FAIL = 42
    OR = 43
    AND = 44
    IS = 45
    ISNOT = 46
    MATCH = 47
    LIKE_KW = 48    # LIKE, GLOB, REGEXP, MATCH
    BETWEEN = 49
    IN = 50
    ISNULL = 51
    NOTNULL = 52
    NE = 53         # !=
    EQ = 54         # =
    GT = 55         # >
    LE = 56         # <=
    LT = 57         # <
    GE = 58         # >=
    ESCAPE = 59
    ID = 60
    COLUMNKW = 61
    DO = 62
    FOR = 63
    IGNORE = 64
    INITIALLY = 65
    INSTEAD = 66
    NO = 67
    KEY = 68
    OF = 69
    OFFSET = 70
    PRAGMA = 71
    RAISE = 72
    RECURSIVE = 73
    REPLACE = 74
    RESTRICT = 75
    ROW = 76
    ROWS = 77
    TRIGGER = 78
    VACUUM = 79
    VIEW = 80
    VIRTUAL = 81
    WITH = 82
    NULLS = 83
    FIRST = 84
    LAST = 85
    CURRENT = 86
    FOLLOWING = 87
    PARTITION = 88
    PRECEDING = 89
    RANGE = 90
    UNBOUNDED = 91
    EXCLUDE = 92
    GROUPS = 93
    OTHERS = 94
    TIES = 95
    GENERATED = 96
    ALWAYS = 97
    MATERIALIZED = 98
    REINDEX = 99
    RENAME = 100
    CTIME_KW = 101  # CURRENT_DATE, CURRENT_TIME, CURRENT_TIMESTAMP
    ANY = 102
    BITAND = 103    # &
    BITOR = 104     # |
    LSHIFT = 105    # <<
    RSHIFT = 106    # >>
    PLUS = 107      # +
    MINUS = 108     # -
    STAR = 109      # *
    SLASH = 110     # /
    REM = 111       # %
    CONCAT = 112    # ||
    PTR = 113       # ->
    COLLATE = 114
    BITNOT = 115    # ~
    ON = 116
    INDEXED = 117
    STRING = 118
    JOIN_KW = 119   # CROSS, FULL, INNER, LEFT, NATURAL, OUTER, RIGHT
    CONSTRAINT = 120
    DEFAULT = 121
    NULL = 122
    PRIMARY = 123
    UNIQUE = 124
    CHECK = 125
    REFERENCES = 126
    AUTOINCR = 127  # AUTOINCREMENT
    INSERT = 128
    DELETE = 129
    UPDATE = 130
    SET = 131
    DEFERRABLE = 132
    FOREIGN = 133
    DROP = 134
    UNION = 135
    ALL = 136
    EXCEPT = 137
    INTERSECT = 138
    SELECT = 139
    VALUES = 140
    DISTINCT = 141
    DOT = 142       # .
    FROM = 143
    JOIN = 144
    USING = 145
    ORDER = 146
    GROUP = 147
    HAVING = 148
    LIMIT = 149
    WHERE = 150
    RETURNING = 151
    INTO = 152
    NOTHING = 153
    BLOB = 154      # x'...'
    FLOAT = 155
    INTEGER = 156
    VARIABLE = 157  # ?, ?N, :name
    CASE = 158
    WHEN = 159
    THEN = 160
    ELSE = 161
    INDEX = 162
    ALTER = 163
    ADD = 164
    WINDOW = 165
    OVER = 166
    FILTER = 167
    WITHIN = 168
    OPTIMIZE = 169
    TYPE = 170
    CONCURRENT = 171
    ILLEGAL = 185

    def is_identifier_keyword(self) -> bool:
        """Whether this token type is a keyword that can be used as an identifier
        in some contexts (the parser decides context-sensitivity)."""
        # Keywords that SQLite allows as identifiers in certain positions.
        # The lexer always produces the keyword token type; the parser treats
        # it as an ID when the grammar position expects an identifier.
        return self in (
            TokenType.END, TokenType.AFTER, TokenType.BEFORE, TokenType.FILTER,
            TokenType.FIRST, TokenType.FOLLOWING, TokenType.KEY, TokenType.LAST,
            TokenType.OTHERS, TokenType.PARTITION, TokenType.PRECEDING,
            TokenType.RANGE, TokenType.ROW, TokenType.ROWS, TokenType.TIES,
            TokenType.UNBOUNDED, TokenType.WINDOW, TokenType.WITHIN,
            TokenType.GROUPS, TokenType.EXCLUDE, TokenType.NULLS,
            TokenType.CURRENT, TokenType.GENERATED, TokenType.ALWAYS,
            TokenType.TYPE, TokenType.CONCURRENT, TokenType.OPTIMIZE, TokenType.LIKE_KW, TokenType.REPLACE, TokenType.ROW, TokenType.ROWS,
        )


#: Case-insensitive keyword → TokenType table. Ports ``keyword_or_id_token``.
#: Any word not in this table is ``ID``.
KEYWORD_TABLE: dict[str, TokenType] = {
    "ABORT": TokenType.ABORT,
    "ACTION": TokenType.ACTION,
    "ADD": TokenType.ADD,
    "AFTER": TokenType.AFTER,
    "ALL": TokenType.ALL,
    "ALTER": TokenType.ALTER,
    "ALWAYS": TokenType.ALWAYS,
    "ANALYZE": TokenType.ANALYZE,
    "AND": TokenType.AND,
    "AS": TokenType.AS,
    "ASC": TokenType.ASC,
    "ATTACH": TokenType.ATTACH,
    "AUTOINCREMENT": TokenType.AUTOINCR,
    "BEFORE": TokenType.BEFORE,
    "BEGIN": TokenType.BEGIN,
    "BETWEEN": TokenType.BETWEEN,
    "BY": TokenType.BY,
    "CASCADE": TokenType.CASCADE,
    "CASE": TokenType.CASE,
    "CAST": TokenType.CAST,
    "CHECK": TokenType.CHECK,
    "COLLATE": TokenType.COLLATE,
    "COLUMN": TokenType.COLUMNKW,
    "COMMIT": TokenType.COMMIT,
    "CONCURRENT": TokenType.CONCURRENT,
    "CONFLICT": TokenType.CONFLICT,
    "CONSTRAINT": TokenType.CONSTRAINT,
    "CREATE": TokenType.CREATE,
    "CROSS": TokenType.JOIN_KW,
    "CURRENT": TokenType.CURRENT,
    "CURRENT_DATE": TokenType.CTIME_KW,
    "CURRENT_TIME": TokenType.CTIME_KW,
    "CURRENT_TIMESTAMP": TokenType.CTIME_KW,
    "DATABASE": TokenType.DATABASE,
    "DEFAULT": TokenType.DEFAULT,
    "DEFERRABLE": TokenType.DEFERRABLE,
    "DEFERRED": TokenType.DEFERRED,
    "DELETE": TokenType.DELETE,
    "DESC": TokenType.DESC,
    "DETACH": TokenType.DETACH,
    "DISTINCT": TokenType.DISTINCT,
    "DO": TokenType.DO,
    "DROP": TokenType.DROP,
    "EACH": TokenType.EACH,
    "ELSE": TokenType.ELSE,
    "END": TokenType.END,
    "ESCAPE": TokenType.ESCAPE,
    "EXCEPT": TokenType.EXCEPT,
    "EXCLUDE": TokenType.EXCLUDE,
    "EXCLUSIVE": TokenType.EXCLUSIVE,
    "EXISTS": TokenType.EXISTS,
    "EXPLAIN": TokenType.EXPLAIN,
    "FAIL": TokenType.FAIL,
    "FILTER": TokenType.FILTER,
    "FIRST": TokenType.FIRST,
    "FOLLOWING": TokenType.FOLLOWING,
    "FOR": TokenType.FOR,
    "FOREIGN": TokenType.FOREIGN,
    "FROM": TokenType.FROM,
    "FULL": TokenType.JOIN_KW,
    "GENERATED": TokenType.GENERATED,
    "GLOB": TokenType.LIKE_KW,
    "GROUP": TokenType.GROUP,
    "GROUPS": TokenType.GROUPS,
    "HAVING": TokenType.HAVING,
    "IF": TokenType.IF,
    "IGNORE": TokenType.IGNORE,
    "IMMEDIATE": TokenType.IMMEDIATE,
    "IN": TokenType.IN,
    "INDEX": TokenType.INDEX,
    "INDEXED": TokenType.INDEXED,
    "INITIALLY": TokenType.INITIALLY,
    "INNER": TokenType.JOIN_KW,
    "INSERT": TokenType.INSERT,
    "INSTEAD": TokenType.INSTEAD,
    "INTERSECT": TokenType.INTERSECT,
    "INTO": TokenType.INTO,
    "IS": TokenType.IS,
    "ISNULL": TokenType.ISNULL,
    "JOIN": TokenType.JOIN,
    "KEY": TokenType.KEY,
    "LAST": TokenType.LAST,
    "LEFT": TokenType.JOIN_KW,
    "LIKE": TokenType.LIKE_KW,
    "LIMIT": TokenType.LIMIT,
    "MATCH": TokenType.MATCH,
    "MATERIALIZED": TokenType.MATERIALIZED,
    "NATURAL": TokenType.JOIN_KW,
    "NO": TokenType.NO,
    "NOT": TokenType.NOT,
    "NOTHING": TokenType.NOTHING,
    "NOTNULL": TokenType.NOTNULL,
    "NULL": TokenType.NULL,
    "NULLS": TokenType.NULLS,
    "OF": TokenType.OF,
    "OFFSET": TokenType.OFFSET,
    "ON": TokenType.ON,
    "OPTIMIZE": TokenType.OPTIMIZE,
    "OR": TokenType.OR,
    "ORDER": TokenType.ORDER,
    "OTHERS": TokenType.OTHERS,
    "OUTER": TokenType.JOIN_KW,
    "OVER": TokenType.OVER,
    "PARTITION": TokenType.PARTITION,
    "PLAN": TokenType.PLAN,
    "PRAGMA": TokenType.PRAGMA,
    "PRECEDING": TokenType.PRECEDING,
    "PRIMARY": TokenType.PRIMARY,
    "QUERY": TokenType.QUERY,
    "RAISE": TokenType.RAISE,
    "RANGE": TokenType.RANGE,
    "RECURSIVE": TokenType.RECURSIVE,
    "REFERENCES": TokenType.REFERENCES,
    "REGEXP": TokenType.LIKE_KW,
    "REINDEX": TokenType.REINDEX,
    "RELEASE": TokenType.RELEASE,
    "RENAME": TokenType.RENAME,
    "REPLACE": TokenType.REPLACE,
    "RESTRICT": TokenType.RESTRICT,
    "RETURNING": TokenType.RETURNING,
    "RIGHT": TokenType.JOIN_KW,
    "ROLLBACK": TokenType.ROLLBACK,
    "ROW": TokenType.ROW,
    "ROWS": TokenType.ROWS,
    "SAVEPOINT": TokenType.SAVEPOINT,
    "SELECT": TokenType.SELECT,
    "SET": TokenType.SET,
    "TABLE": TokenType.TABLE,
    "TEMP": TokenType.TEMP,
    "TEMPORARY": TokenType.TEMP,
    "THEN": TokenType.THEN,
    "TIES": TokenType.TIES,
    "TO": TokenType.TO,
    "TRANSACTION": TokenType.TRANSACTION,
    "TRIGGER": TokenType.TRIGGER,
    "TYPE": TokenType.TYPE,
    "UNBOUNDED": TokenType.UNBOUNDED,
    "UNION": TokenType.UNION,
    "UNIQUE": TokenType.UNIQUE,
    "UPDATE": TokenType.UPDATE,
    "USING": TokenType.USING,
    "VACUUM": TokenType.VACUUM,
    "VALUES": TokenType.VALUES,
    "VIEW": TokenType.VIEW,
    "VIRTUAL": TokenType.VIRTUAL,
    "WHEN": TokenType.WHEN,
    "WHERE": TokenType.WHERE,
    "WINDOW": TokenType.WINDOW,
    "WITH": TokenType.WITH,
    "WITHIN": TokenType.WITHIN,
    "WITHOUT": TokenType.WITHOUT,
}


def keyword_or_id(word: str) -> TokenType:
    """Classify a word as a keyword or an identifier.

    Ports ``keyword_or_id_token``. Case-insensitive lookup: if the uppercased
    word is in the keyword table, return its token type; otherwise ``ID``.
    """
    return KEYWORD_TABLE.get(word.upper(), TokenType.ID)


def is_identifier_start(b: str) -> bool:
    """Whether ``b`` can start an identifier. Ports ``is_identifier_start``.

    Letters (ASCII upper/lower), underscore, or any non-ASCII byte (UTF-8
    multi-byte chars are valid identifier chars in SQLite).
    """
    return (
        b.isascii() and (b.isalpha() or b == "_")
        or not b.isascii()
    )


def is_identifier_continue(b: str) -> bool:
    """Whether ``b`` can continue an identifier. Ports ``is_identifier_continue``.

    Letters, digits, underscore, ``$``, or any non-ASCII byte.
    """
    return (
        b.isascii() and (b.isalnum() or b in ("_", "$"))
        or not b.isascii()
    )


@dataclass(frozen=True)
class Token:
    """A lexer token. Ports ``sqlite::parser::lexer::Token``.

    ``value`` is the token's text; ``token_type`` is its kind; ``offset`` is
    the byte offset in the source where the token starts (for error messages).
    pyturso adds ``offset`` (the Rust carries it implicitly via the input slice).
    """

    value: str
    token_type: TokenType
    offset: int

    def __repr__(self) -> str:
        return f"Token({self.token_type.name}, {self.value!r}, @{self.offset})"