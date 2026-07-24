"""lexer — text → token stream.

Ports: sqlite/parser/src/lexer.rs (``Lexer`` iterator, ``eat_*`` methods).
Phase: 3
Status: IMPLEMENTED.

Scans SQL text into :class:`pyturso.parser.token.Token` objects, skipping
whitespace and comments. Every token carries its byte offset for error
messages. The lexer is a simple character-by-character scanner that mirrors
the Rust ``Lexer::next()`` dispatch table:

  - whitespace / ``--`` / ``/* */`` → skipped (not emitted)
  - ``'...'`` → STRING literal (doubled-quote escape ``''``)
  - ``"..."``, `` `...` `` → ID (quoted identifier; doubled-quote/backtick escape)
  - ``[...]`` → ID (bracket identifier; close on first ``]``)
  - ``x'...'`` / ``X'...'`` → BLOB literal (even-length hex required)
  - ``0x...`` → INTEGER (hex integer)
  - ``123`` → INTEGER (decimal); ``.5`` / ``1.5`` / ``1e5`` → FLOAT
  - ``?`` / ``?N`` / ``$name`` / ``:name`` / ``@name`` → VARIABLE
  - identifiers/keywords (via :func:`keyword_or_id`)
  - operators / punctuation

Errors (unterminated string, bad hex, malformed number) raise
:class:`pyturso.parser.errors.ParseError` with the token position.
"""

from __future__ import annotations

from pyturso.parser.errors import ParseError
from pyturso.parser.token import (
    Token,
    TokenType,
    is_identifier_continue,
    is_identifier_start,
    keyword_or_id,
)

__all__ = ["tokenize"]


def tokenize(sql: str) -> list[Token]:
    """Tokenize ``sql`` into a list of tokens (whitespace/comments skipped).

    Raises:
        ParseError: on an unterminated string/blob, malformed number, bad
            hex integer, or unrecognized character.
    """
    lexer = _Lexer(sql)
    return lexer.run()


class _Lexer:
    """Character-by-character scanner. Ports ``sqlite::parser::Lexer``."""

    def __init__(self, input_str: str) -> None:
        self._input: str = input_str
        self._offset: int = 0
        self._tokens: list[Token] = []

    def run(self) -> list[Token]:
        """Scan the entire input, returning the token list."""
        n = len(self._input)
        while self._offset < n:
            ch = self._peek()
            if ch is None:
                break
            if ch.isascii() and ch.isspace():
                self._skip_whitespace()
                continue
            if ch == "-" and self._peek_at(1) == "-":
                self._skip_line_comment()
                continue
            if ch == "/" and self._peek_at(1) == "*":
                self._skip_block_comment()
                continue
            # A token starts here.
            prev_offset = self._offset
            self._scan_token()
            # Safety: if _scan_token did not advance, we would infinite-loop.
            if self._offset == prev_offset:
                raise ParseError(
                    f"lexer stalled at offset {self._offset}",
                    self._offset, self._peek_or_empty(),
                )
        self._tokens.append(Token("", TokenType.EOF, self._offset))
        return self._tokens

    # --- scan helpers ---
    def _peek(self) -> str | None:
        if self._offset < len(self._input):
            return self._input[self._offset]
        return None

    def _peek_at(self, ahead: int) -> str | None:
        idx = self._offset + ahead
        if idx < len(self._input):
            return self._input[idx]
        return None

    def _advance(self) -> str:
        if self._offset >= len(self._input):
            return ""
        ch = self._input[self._offset]
        self._offset += 1
        return ch

    # --- skip whitespace/comments ---
    def _peek_or_empty(self) -> str:
        """Peek without None — returns '' at EOF. Use in scan methods."""
        if self._offset < len(self._input):
            return self._input[self._offset]
        return ""

    def _skip_whitespace(self) -> None:
        while True:
            ch = self._peek()
            if ch is not None and ch.isascii() and ch.isspace():
                self._offset += 1
            else:
                break

    def _skip_line_comment(self) -> None:
        # Already at '-' of '--'; consume to end of line (inclusive).
        while self._peek_or_empty() and self._peek_or_empty() != "\n":
            self._offset += 1
        if self._peek_or_empty() == "\n":
            self._offset += 1

    def _skip_block_comment(self) -> None:
        # Already at '/' of '/*'; consume to '*/' (or EOF).
        start = self._offset
        self._offset += 2  # skip /*
        while self._offset < len(self._input):
            if self._peek() == "*" and self._peek_at(1) == "/":
                self._offset += 2
                return
            self._offset += 1
        raise ParseError(
            f"unterminated block comment at offset {start}", start, "*/"
        )

    # --- scan one token ---
    def _scan_token(self) -> None:
        start = self._offset
        ch = self._peek_or_empty()
        assert ch is not None

        # Single-char tokens
        simple: dict[str, TokenType] = {
            "(": TokenType.LP,
            ")": TokenType.RP,
            ";": TokenType.SEMI,
            "+": TokenType.PLUS,
            "*": TokenType.STAR,
            "%": TokenType.REM,
            ",": TokenType.COMMA,
            "~": TokenType.BITNOT,
        }
        if ch in simple:
            self._advance()
            self._emit(simple[ch], start)
            return

        # Dot: could be a float (.5) or DOT operator
        if ch == ".":
            nxt = self._peek_at(1)
            if nxt is not None and nxt.isdigit():
                self._scan_float(start)
                return
            self._advance()
            self._emit(TokenType.DOT, start)
            return

        # Minus: could be -> or ->> or MINUS
        if ch == "-":
            self._advance()
            if self._peek_or_empty() == ">":
                self._advance()
                if self._peek_or_empty() == ">":
                    self._advance()
                self._emit(TokenType.PTR, start)
                return
            self._emit(TokenType.MINUS, start)
            return

        # Slash: already handled for comments; must be SLASH
        if ch == "/":
            self._advance()
            self._emit(TokenType.SLASH, start)
            return

        # Equals
        if ch == "=":
            self._advance()
            if self._peek_or_empty() == "=":
                self._advance()  # == is also EQ in SQLite
            self._emit(TokenType.EQ, start)
            return

        # Less-than family: <= << <> <
        if ch == "<":
            self._advance()
            if self._peek_or_empty() == "=":
                self._advance()
                self._emit(TokenType.LE, start)
            elif self._peek_or_empty() == "<":
                self._advance()
                self._emit(TokenType.LSHIFT, start)
            elif self._peek_or_empty() == ">":
                self._advance()
                self._emit(TokenType.NE, start)
            else:
                self._emit(TokenType.LT, start)
            return

        # Greater-than family: >= >> >
        if ch == ">":
            self._advance()
            if self._peek_or_empty() == "=":
                self._advance()
                self._emit(TokenType.GE, start)
            elif self._peek_or_empty() == ">":
                self._advance()
                self._emit(TokenType.RSHIFT, start)
            else:
                self._emit(TokenType.GT, start)
            return

        # Not-equal: !=
        if ch == "!":
            self._advance()
            if self._peek_or_empty() == "=":
                self._advance()
                self._emit(TokenType.NE, start)
                return
            raise ParseError(
                f"expected '=' after '!' at offset {start}", start, "="
            )

        # Pipe: || or |
        if ch == "|":
            self._advance()
            if self._peek_or_empty() == "|":
                self._advance()
                self._emit(TokenType.CONCAT, start)
                return
            self._emit(TokenType.BITOR, start)
            return

        # Ampersand: && or &
        if ch == "&":
            self._advance()
            if self._peek_or_empty() == "&":
                self._advance()
                self._emit(TokenType.BITAND, start)  # TODO: array overlap
                return
            self._emit(TokenType.BITAND, start)
            return

        # String / quoted identifier literals: ' " `
        if ch in ("'", '"', "`"):
            self._scan_quoted(start, ch)
            return

        # Bracket identifier: [ ]
        if ch == "[":
            self._scan_bracket(start)
            return

        # Numbers: 0x... hex, digits, .5
        if ch.isdigit():
            self._scan_number(start)
            return

        # Parameters: ? ?N $ : @
        if ch == "?":
            self._advance()
            while self._peek_or_empty() and self._peek_or_empty().isdigit():
                self._advance()
            self._emit(TokenType.VARIABLE, start)
            return
        if ch in ("$", ":"):
            nxt = self._peek_at(1)
            if nxt is not None and (is_identifier_start(nxt)):
                self._advance()  # consume the sigil
                while self._peek_or_empty() and is_identifier_continue(self._peek_or_empty()):
                    self._advance()
                self._emit(TokenType.VARIABLE, start)
                return
            # Bare colon → DOT-like or standalone
            if ch == ":":
                self._advance()
                self._emit(TokenType.DOT, start)  # SQLite maps bare : to DOT
                return
            # Bare $ — skip as unrecognized
            self._advance()
            raise ParseError(
                f"bad variable name at offset {start}", start, ch
            )
        if ch == "@":
            self._advance()
            nxt = self._peek_or_empty()
            if nxt is not None and is_identifier_start(nxt):
                while self._peek_or_empty() and is_identifier_continue(self._peek_or_empty()):
                    self._advance()
                self._emit(TokenType.VARIABLE, start)
                return
            raise ParseError(
                f"bad variable name at offset {start}", start, ch
            )

        # Identifiers/keywords/blobs
        if is_identifier_start(ch):
            self._scan_id_or_blob(start)
            return

        # Unrecognized
        raise ParseError(
            f"unrecognized character {ch!r} at offset {start}", start, ch
        )

    # --- scan specific token types ---
    def _scan_quoted(self, start: int, quote: str) -> None:
        """Scan '...' (STRING), "..." or `...` (ID). Doubled-quote escape."""
        tt = TokenType.STRING if quote == "'" else TokenType.ID
        self._advance()  # consume opening quote
        buf: list[str] = []
        while True:
            ch = self._peek_or_empty()
            if not ch:
                raise ParseError(
                    f"non-terminated literal starting at offset {start}",
                    start, quote,
                )
            if ch == quote:
                self._advance()
                if self._peek_or_empty() == quote:
                    buf.append(quote)  # escaped doubled quote
                    self._advance()
                    continue
                break
            buf.append(ch)
            self._advance()
        self._emit(tt, start, value="".join(buf))

    def _scan_bracket(self, start: int) -> None:
        """Scan [...] bracket identifier."""
        self._advance()  # consume [
        buf: list[str] = []
        while True:
            ch = self._peek_or_empty()
            if not ch:
                raise ParseError(
                    f"non-terminated bracket starting at offset {start}",
                    start, "]",
                )
            if ch == "]":
                self._advance()
                break
            buf.append(ch)
            self._advance()
        self._emit(TokenType.ID, start, value="".join(buf))

    def _scan_number(self, start: int) -> None:
        """Scan 0x... (hex int), decimal int, or float."""
        first = self._advance()
        # Hex: 0x...
        if first == "0" and self._peek_or_empty() in ("x", "X"):
            self._advance()  # consume x/X
            hex_start = self._offset
            while self._peek_or_empty() and self._peek_or_empty() in "0123456789abcdefABCDEF_":
                self._advance()
            if self._offset == hex_start:
                raise ParseError(
                    f"malformed hex integer at offset {start}", start, "0x"
                )
            # A trailing identifier char is a bad number
            if self._peek_or_empty() and is_identifier_start(self._peek_or_empty()):
                raise ParseError(
                    f"bad number at offset {start}", start, ""
                )
            hex_str = self._input[hex_start:self._offset].replace("_", "")
            self._emit(TokenType.INTEGER, start, value=str(int(hex_str, 16)))
            return

        # Decimal digits
        while self._peek_or_empty() and (self._peek_or_empty().isdigit() or self._peek_or_empty() == "_"):
            self._advance()
        # Float?
        if self._peek_or_empty() == ".":
            self._scan_float(start)
            return
        if self._peek_or_empty() in ("e", "E"):
            self._scan_exponent(start)
            return
        # Trailing identifier char = bad number
        if self._peek_or_empty() and is_identifier_start(self._peek_or_empty()):
            raise ParseError(
                f"bad number at offset {start}", start, ""
            )
        # Plain integer
        int_str = self._input[start:self._offset].replace("_", "")
        self._emit(TokenType.INTEGER, start, value=int_str)

    def _scan_float(self, start: int) -> None:
        """Scan the fractional part of a float (digits already consumed or .N)."""
        if self._peek_or_empty() == ".":
            self._advance()  # consume .
            while self._peek_or_empty() and (self._peek_or_empty().isdigit() or self._peek_or_empty() == "_"):
                self._advance()
        # Exponent?
        if self._peek_or_empty() in ("e", "E"):
            self._scan_exponent(start)
            return
        float_str = self._input[start:self._offset].replace("_", "")
        self._emit(TokenType.FLOAT, start, value=float_str)

    def _scan_exponent(self, start: int) -> None:
        """Scan e[+-]digits as part of a float."""
        self._advance()  # consume e/E
        if self._peek_or_empty() in ("+", "-"):
            self._advance()
        exp_start = self._offset
        while self._peek_or_empty() and (self._peek_or_empty().isdigit() or self._peek_or_empty() == "_"):
            self._advance()
        if self._offset == exp_start:
            raise ParseError(
                f"bad exponent part at offset {start}", start, ""
            )
        float_str = self._input[start:self._offset].replace("_", "")
        self._emit(TokenType.FLOAT, start, value=float_str)

    def _scan_id_or_blob(self, start: int) -> None:
        """Scan an identifier, keyword, or x'...' blob literal."""
        first = self._advance()
        # Blob: x'...' or X'...'
        if first in ("x", "X") and self._peek_or_empty() == "'":
            self._advance()  # consume '
            hex_start = self._offset
            while self._peek_or_empty() and self._peek_or_empty() in "0123456789abcdefABCDEF":
                self._advance()
            hex_end = self._offset
            if self._peek_or_empty() != chr(39):
                raise ParseError(
                    f"non-terminated literal starting at offset {start}",
                    start, "'",
                )
            self._advance()  # consume closing '
            if (hex_end - hex_start) % 2 != 0:
                raise ParseError(
                    f"odd-length blob hex at offset {start}", start, "'"
                )
            blob_hex = self._input[hex_start:hex_end]
            self._emit(TokenType.BLOB, start, value=blob_hex)
            return

        # Regular identifier or keyword
        while self._peek_or_empty() and is_identifier_continue(self._peek_or_empty()):
            self._advance()
        word = self._input[start:self._offset]
        tt = keyword_or_id(word)
        self._emit(tt, start, value=word)

    # --- emit ---
    def _emit(self, tt: TokenType, start: int, *, value: str | None = None) -> None:
        """Append a token with the given type and value (default: source slice)."""
        if value is None:
            value = self._input[start:self._offset]
        self._tokens.append(Token(value=value, token_type=tt, offset=start))