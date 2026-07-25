"""Unit tests for pyturso.parser.lexer — text → token stream.

Ports/verified against: sqlite/parser/src/lexer.rs (Lexer, eat_* methods).
Tests valid tokenization (every token kind) + rejection cases (unterminated
strings, bad hex, malformed numbers).
"""

from __future__ import annotations

import pytest

from pyturso.parser.errors import ParseError
from pyturso.parser.lexer import tokenize
from pyturso.parser.token import Token, TokenType


def _types(sql: str) -> list[TokenType]:
    """Token types for a SQL string (excluding EOF)."""
    toks = tokenize(sql)
    return [t.token_type for t in toks if t.token_type is not TokenType.EOF]


def _toks(sql: str) -> list[Token]:
    return [t for t in tokenize(sql) if t.token_type is not TokenType.EOF]


# --- whitespace and comments are skipped -----------------------------------
class TestSkipped:
    def test_whitespace_skipped(self) -> None:
        assert _types("  SELECT  ") == [TokenType.SELECT]

    def test_line_comment_skipped(self) -> None:
        toks = _types("SELECT -- comment\n1")
        assert toks == [TokenType.SELECT, TokenType.INTEGER]

    def test_block_comment_skipped(self) -> None:
        toks = _types("/* comment */ SELECT")
        assert toks == [TokenType.SELECT]

    def test_mixed_whitespace_comment(self) -> None:
        toks = _types("-- a\n/* b */  SELECT  -- c\n1")
        assert toks == [TokenType.SELECT, TokenType.INTEGER]

    def test_empty_string_produces_eof_only(self) -> None:
        toks = tokenize("")
        assert len(toks) == 1 and toks[0].token_type is TokenType.EOF

    def test_only_whitespace(self) -> None:
        toks = tokenize("   \n\t  ")
        assert len(toks) == 1 and toks[0].token_type is TokenType.EOF


# --- keywords and identifiers ----------------------------------------------
class TestKeywordsAndIds:
    def test_keyword(self) -> None:
        toks = _toks("SELECT")
        assert len(toks) == 1
        assert toks[0].token_type is TokenType.SELECT
        assert toks[0].value == "SELECT"

    def test_keyword_case_insensitive(self) -> None:
        for kw in ("select", "SELECT", "Select"):
            assert _toks(kw)[0].token_type is TokenType.SELECT

    def test_identifier(self) -> None:
        toks = _toks("mytable")
        assert toks[0].token_type is TokenType.ID
        assert toks[0].value == "mytable"

    def test_identifier_with_digits(self) -> None:
        assert _toks("col1")[0].token_type is TokenType.ID

    def test_identifier_with_underscore(self) -> None:
        assert _toks("_private")[0].token_type is TokenType.ID

    def test_dollar_identifier(self) -> None:
        assert _toks("a$b")[0].token_type is TokenType.ID


# --- quoted identifiers ----------------------------------------------------
class TestQuotedIds:
    def test_double_quoted_id(self) -> None:
        t = _toks('"my column"')[0]
        assert t.token_type is TokenType.ID
        assert t.value == "my column"

    def test_backtick_id(self) -> None:
        t = _toks("`weird name`")[0]
        assert t.token_type is TokenType.ID
        assert t.value == "weird name"

    def test_bracket_id(self) -> None:
        t = _toks("[col]")[0]
        assert t.token_type is TokenType.ID
        assert t.value == "col"

    def test_double_quote_escape(self) -> None:
        # '' inside "..." is an escaped quote.
        t = _toks('"a""b"')[0]
        assert t.token_type is TokenType.ID
        assert t.value == 'a"b'

    def test_double_single_quote_escape(self) -> None:
        # '' inside '...' is an escaped quote.
        t = _toks("'a''b'")[0]
        assert t.token_type is TokenType.STRING
        assert t.value == "a'b"


# --- string literals -------------------------------------------------------
class TestStrings:
    def test_string(self) -> None:
        t = _toks("'hello world'")[0]
        assert t.token_type is TokenType.STRING
        assert t.value == "hello world"

    def test_empty_string(self) -> None:
        t = _toks("''")[0]
        assert t.token_type is TokenType.STRING
        assert t.value == ""

    def test_string_with_special_chars(self) -> None:
        t = _toks("'a;b\\nc'")[0]
        assert t.token_type is TokenType.STRING


# --- blob literals ---------------------------------------------------------
class TestBlobs:
    def test_blob(self) -> None:
        t = _toks("x'00ff'")[0]
        assert t.token_type is TokenType.BLOB
        assert t.value == "00ff"

    def test_blob_uppercase_x(self) -> None:
        t = _toks("X'ABCD'")[0]
        assert t.token_type is TokenType.BLOB

    def test_blob_empty(self) -> None:
        t = _toks("x''")[0]
        assert t.token_type is TokenType.BLOB
        assert t.value == ""


# --- numeric literals ------------------------------------------------------
class TestNumbers:
    def test_integer(self) -> None:
        t = _toks("42")[0]
        assert t.token_type is TokenType.INTEGER
        assert t.value == "42"

    def test_zero(self) -> None:
        assert _toks("0")[0].token_type is TokenType.INTEGER

    def test_hex_integer(self) -> None:
        t = _toks("0xFF")[0]
        assert t.token_type is TokenType.INTEGER
        assert t.value == "255"  # parsed to decimal

    def test_hex_uppercase(self) -> None:
        t = _toks("0XAB")[0]
        assert t.token_type is TokenType.INTEGER

    def test_float_dot(self) -> None:
        t = _toks("3.14")[0]
        assert t.token_type is TokenType.FLOAT

    def test_float_leading_dot(self) -> None:
        t = _toks(".5")[0]
        assert t.token_type is TokenType.FLOAT

    def test_float_exponent(self) -> None:
        t = _toks("1e5")[0]
        assert t.token_type is TokenType.FLOAT

    def test_float_exponent_positive(self) -> None:
        t = _toks("1.0e+3")[0]
        assert t.token_type is TokenType.FLOAT

    def test_float_exponent_negative(self) -> None:
        t = _toks("2.5e-2")[0]
        assert t.token_type is TokenType.FLOAT

    def test_negative_integer(self) -> None:
        toks = _toks("-42")
        assert toks[0].token_type is TokenType.MINUS
        assert toks[1].token_type is TokenType.INTEGER


# --- operators and punctuation ---------------------------------------------
class TestOperators:
    @pytest.mark.parametrize("sql,expected", [
        ("(", TokenType.LP), (")", TokenType.RP),
        (";", TokenType.SEMI), (",", TokenType.COMMA),
        ("+", TokenType.PLUS), ("-", TokenType.MINUS),
        ("*", TokenType.STAR), ("/", TokenType.SLASH),
        ("%", TokenType.REM), (".", TokenType.DOT),
        ("~", TokenType.BITNOT),
    ])
    def test_single_char(self, sql: str, expected: TokenType) -> None:
        assert _toks(sql)[0].token_type is expected

    @pytest.mark.parametrize("sql,expected", [
        ("=", TokenType.EQ), ("==", TokenType.EQ),
        ("!=", TokenType.NE), ("<>", TokenType.NE),
        ("<", TokenType.LT), ("<=", TokenType.LE),
        (">", TokenType.GT), (">=", TokenType.GE),
        ("||", TokenType.CONCAT), ("|", TokenType.BITOR),
        ("&", TokenType.BITAND), ("<<", TokenType.LSHIFT),
        (">>", TokenType.RSHIFT),
    ])
    def test_multi_char(self, sql: str, expected: TokenType) -> None:
        assert _toks(sql)[0].token_type is expected

    def test_arrow(self) -> None:
        assert _toks("->")[0].token_type is TokenType.PTR


# --- parameters ------------------------------------------------------------
class TestParameters:
    def test_question_mark(self) -> None:
        t = _toks("?")[0]
        assert t.token_type is TokenType.VARIABLE

    def test_question_number(self) -> None:
        t = _toks("?1")[0]
        assert t.token_type is TokenType.VARIABLE
        assert t.value == "?1"

    def test_dollar_name(self) -> None:
        t = _toks("$name")[0]
        assert t.token_type is TokenType.VARIABLE

    def test_colon_name(self) -> None:
        t = _toks(":param")[0]
        assert t.token_type is TokenType.VARIABLE


# --- positions -------------------------------------------------------------
class TestPositions:
    def test_token_has_offset(self) -> None:
        toks = tokenize("SELECT 1")
        select_tok = toks[0]
        assert select_tok.offset == 0
        one_tok = toks[1]
        assert one_tok.offset == 7  # after "SELECT "

    def test_eof_offset(self) -> None:
        toks = tokenize("SELECT")
        eof = toks[-1]
        assert eof.token_type is TokenType.EOF
        assert eof.offset == 6


# --- a real SQL statement --------------------------------------------------
class TestRealSQL:
    def test_select_statement(self) -> None:
        toks = _types("SELECT a, b FROM t WHERE c > 1")
        assert toks == [
            TokenType.SELECT, TokenType.ID, TokenType.COMMA,
            TokenType.ID, TokenType.FROM, TokenType.ID,
            TokenType.WHERE, TokenType.ID, TokenType.GT, TokenType.INTEGER,
        ]

    def test_select_with_string(self) -> None:
        toks = _types("SELECT 'hello' AS greeting")
        assert toks == [
            TokenType.SELECT, TokenType.STRING, TokenType.AS, TokenType.ID,
        ]


# --- rejection cases -------------------------------------------------------
class TestRejection:
    def test_unterminated_string(self) -> None:
        with pytest.raises(ParseError, match="non-terminated"):
            tokenize("'hello")

    def test_unterminated_quoted_id(self) -> None:
        with pytest.raises(ParseError, match="non-terminated"):
            tokenize('"myid')

    def test_unterminated_bracket(self) -> None:
        with pytest.raises(ParseError, match="non-terminated"):
            tokenize("[col")

    def test_unterminated_block_comment(self) -> None:
        with pytest.raises(ParseError, match="block comment"):
            tokenize("/* no end")

    def test_odd_hex_blob(self) -> None:
        with pytest.raises(ParseError, match="odd-length"):
            tokenize("x'abc'")  # 3 hex chars — odd

    def test_malformed_hex(self) -> None:
        with pytest.raises(ParseError, match="hex"):
            tokenize("0x")  # no hex digits

    def test_bad_number_trailing_identifier(self) -> None:
        with pytest.raises(ParseError, match="bad number"):
            tokenize("123abc")

    def test_bang_without_equals(self) -> None:
        with pytest.raises(ParseError, match="expected"):
            tokenize("!")

    def test_unrecognized_char(self) -> None:
        with pytest.raises(ParseError, match="unrecognized"):
            tokenize("#unknown")