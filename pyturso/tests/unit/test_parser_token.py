"""Unit tests for pyturso.parser.token — token kinds, keyword table, rules.

Ports/verified against: sqlite/parser/src/token.rs TokenType,
sqlite/parser/src/lexer.rs keyword_or_id_token, is_identifier_start/continue.
"""

from __future__ import annotations

import pytest

from pyturso.parser.token import (
    KEYWORD_TABLE,
    Token,
    TokenType,
    is_identifier_continue,
    is_identifier_start,
    keyword_or_id,
)


# --- TokenType enum -------------------------------------------------------
class TestTokenType:
    def test_eof_is_zero(self) -> None:
        assert TokenType.EOF.value == 0

    def test_select_kind(self) -> None:
        assert TokenType.SELECT.value == 139

    def test_distinct_values(self) -> None:
        # Spot-check a few kinds exist.
        assert TokenType.SEMI in TokenType
        assert TokenType.PLUS in TokenType
        assert len({TokenType.SEMI, TokenType.PLUS, TokenType.EOF}) == 3


# --- keyword_or_id --------------------------------------------------------
class TestKeywordOrId:
    def test_keyword_uppercase(self) -> None:
        assert keyword_or_id("SELECT") is TokenType.SELECT
        assert keyword_or_id("FROM") is TokenType.FROM
        assert keyword_or_id("WHERE") is TokenType.WHERE

    def test_keyword_lowercase(self) -> None:
        assert keyword_or_id("select") is TokenType.SELECT
        assert keyword_or_id("from") is TokenType.FROM

    def test_keyword_mixed_case(self) -> None:
        assert keyword_or_id("Select") is TokenType.SELECT
        assert keyword_or_id("OrDeR") is TokenType.ORDER

    def test_non_keyword_is_id(self) -> None:
        assert keyword_or_id("mytable") is TokenType.ID
        assert keyword_or_id("foo") is TokenType.ID

    def test_join_kw_group(self) -> None:
        # CROSS, FULL, INNER, LEFT, NATURAL, OUTER, RIGHT all map to JOIN_KW.
        for kw in ("CROSS", "FULL", "INNER", "LEFT", "NATURAL", "OUTER", "RIGHT"):
            assert keyword_or_id(kw) is TokenType.JOIN_KW

    def test_like_kw_group(self) -> None:
        for kw in ("LIKE", "GLOB", "REGEXP"):
            assert keyword_or_id(kw) is TokenType.LIKE_KW

    def test_ctime_kw_group(self) -> None:
        for kw in ("CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP"):
            assert keyword_or_id(kw) is TokenType.CTIME_KW

    def test_autoincrement_maps_to_autoincr(self) -> None:
        assert keyword_or_id("AUTOINCREMENT") is TokenType.AUTOINCR

    def test_column_maps_to_columnkw(self) -> None:
        assert keyword_or_id("COLUMN") is TokenType.COLUMNKW

    def test_temporary_maps_to_temp(self) -> None:
        assert keyword_or_id("TEMPORARY") is TokenType.TEMP


# --- KEYWORD_TABLE completeness -------------------------------------------
class TestKeywordTable:
    def test_table_non_empty(self) -> None:
        assert len(KEYWORD_TABLE) > 100  # ~130 keywords

    def test_all_values_are_token_types(self) -> None:
        for v in KEYWORD_TABLE.values():
            assert isinstance(v, TokenType)

    def test_keys_are_uppercase(self) -> None:
        for k in KEYWORD_TABLE:
            assert k == k.upper()


# --- is_identifier_start / continue ---------------------------------------
class TestIdentifierRules:
    def test_letters_start(self) -> None:
        for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert is_identifier_start(c)

    def test_underscore_starts(self) -> None:
        assert is_identifier_start("_")

    def test_digit_does_not_start(self) -> None:
        assert not is_identifier_start("0")
        assert not is_identifier_start("9")

    def test_non_ascii_starts(self) -> None:
        assert is_identifier_start("é")
        assert is_identifier_start("中")

    def test_digit_continues(self) -> None:
        assert is_identifier_continue("0")
        assert is_identifier_continue("9")

    def test_dollar_continues(self) -> None:
        assert is_identifier_continue("$")

    def test_dollar_does_not_start(self) -> None:
        assert not is_identifier_start("$")

    def test_space_neither(self) -> None:
        assert not is_identifier_start(" ")
        assert not is_identifier_continue(" ")


# --- Token dataclass ------------------------------------------------------
class TestToken:
    def test_fields(self) -> None:
        t = Token(value="SELECT", token_type=TokenType.SELECT, offset=0)
        assert t.value == "SELECT"
        assert t.token_type is TokenType.SELECT
        assert t.offset == 0

    def test_frozen(self) -> None:
        t = Token("x", TokenType.ID, 0)
        with pytest.raises(Exception):
            t.value = "y"  # type: ignore[misc]

    def test_equality(self) -> None:
        t1 = Token("SELECT", TokenType.SELECT, 0)
        t2 = Token("SELECT", TokenType.SELECT, 0)
        assert t1 == t2

    def test_repr(self) -> None:
        t = Token("SELECT", TokenType.SELECT, 42)
        r = repr(t)
        assert "SELECT" in r and "42" in r