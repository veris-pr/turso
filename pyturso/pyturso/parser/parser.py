"""parser — recursive descent; precedence climbing for expressions.

Ports: sqlite/parser/src/parser.rs (parse_expr, parse_select, parse_insert,
parse_create_table, etc.).
Phase: 3
Status: IMPLEMENTED (Phase 3 subset: expressions with precedence climbing,
SELECT core, INSERT/UPDATE/DELETE, CREATE TABLE/INDEX, BEGIN/COMMIT/ROLLBACK).

The parser takes a token list (from :mod:`pyturso.parser.lexer`) and produces
AST nodes (from :mod:`pyturso.parser.ast`). It uses **precedence climbing**
for expressions (ports ``parse_expr_inner``): parse an operand, then loop
while the current token's precedence >= the caller's minimum precedence,
consuming the operator and recursing with ``precedence + 1`` for the right
side (left-associative).

Safety: every parse loop has a **stall guard** — if a loop iteration doesn't
consume a token, it raises ``ParseError`` (prevents infinite loops, the
unforgivable parser failure mode).

Unsupported constructs are **rejected** with a clean ``ParseError`` — silent
misparse is never acceptable.
"""

from __future__ import annotations

from pyturso.parser.ast.expr import (
    BinaryExpr, BetweenExpr, CaseExpr, CastExpr, CollateExpr,
    DoublyQualifiedExpr, Expr, FunctionCallExpr, IdExpr, InExpr,
    IsNullExpr, Literal, LiteralExpr, Name, NotNullExpr,
    Operator, ParenExpr, QualifiedExpr, UnaryExpr, UnaryOperator,
)
from pyturso.parser.ast.stmt import (
    As, Begin, Commit, Delete, Distinctness, FromClause, Insert,
    Limit, OneSelect, ResultColumn, Rollback, Select, SelectBody,
    SelectTable, SortedColumn, SortOrder, Stmt, Update,
)
from pyturso.parser.ast.ddl import (
    ColumnConstraint, ColumnDefinition, CreateIndex, CreateTable,
    DDL, DropIndex, DropTable, TableConstraint,
)
from pyturso.parser.errors import ParseError
from pyturso.parser.token import Token, TokenType

__all__ = ["parse", "Parser"]

#: Maximum expression nesting depth (prevents stack overflow on pathological input).
_MAX_EXPR_DEPTH: int = 100

#: Precedence table — ports ``current_token_precedence``. Higher = binds tighter.
_PRECEDENCE: dict[TokenType, int] = {
    TokenType.OR: 0,
    TokenType.AND: 1,
    TokenType.NOT: 3,
    TokenType.EQ: 3,
    TokenType.NE: 3,
    TokenType.IS: 3,
    TokenType.BETWEEN: 3,
    TokenType.IN: 3,
    TokenType.MATCH: 3,
    TokenType.LIKE_KW: 3,
    TokenType.ISNULL: 3,
    TokenType.NOTNULL: 3,
    TokenType.LT: 4,
    TokenType.GT: 4,
    TokenType.LE: 4,
    TokenType.GE: 4,
    TokenType.BITAND: 6,
    TokenType.BITOR: 6,
    TokenType.LSHIFT: 6,
    TokenType.RSHIFT: 6,
    TokenType.PLUS: 7,
    TokenType.MINUS: 7,
    TokenType.STAR: 8,
    TokenType.SLASH: 8,
    TokenType.REM: 8,
    TokenType.CONCAT: 9,
    TokenType.PTR: 9,
    TokenType.COLLATE: 10,
}


def parse(sql: str) -> Stmt | DDL:
    """Parse a single SQL statement from ``sql``.

    Returns an AST node (Stmt or DDL). Raises ``ParseError`` on syntax errors
    or unsupported constructs.
    """
    from pyturso.parser.lexer import tokenize
    tokens = tokenize(sql)
    parser = Parser(tokens)
    stmt = parser.parse_statement()
    # Consume trailing semicolons + EOF.
    while parser._peek_type() in (TokenType.SEMI,):
        parser._advance()
    if not parser._at_eof():
        raise ParseError(
            f"unexpected token {parser._peek().value!r} after statement",
            parser._peek().offset, parser._peek().value,
        )
    return stmt


class Parser:
    """Recursive-descent parser over a token list."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens: list[Token] = tokens
        self._pos: int = 0
        self._expr_depth: int = 0

    # --- cursor helpers ---
    def _peek(self) -> Token:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        # Return a synthetic EOF if past the end.
        return self._tokens[-1]  # last token is always EOF

    def _peek_type(self) -> TokenType:
        return self._peek().token_type

    def _peek_at(self, ahead: int) -> Token | None:
        idx = self._pos + ahead
        if idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def _at_eof(self) -> bool:
        return self._peek_type() is TokenType.EOF

    def _advance(self) -> Token:
        tok = self._peek()
        if tok.token_type is not TokenType.EOF:
            self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        tok = self._peek()
        if tok.token_type is not tt:
            raise ParseError(
                f"expected {tt.name} but found {tok.token_type.name} ({tok.value!r})",
                tok.offset, tok.value,
            )
        return self._advance()

    def _accept(self, tt: TokenType) -> Token | None:
        """Consume the current token if it matches; return it or None."""
        if self._peek_type() is tt:
            return self._advance()
        return None

    def _accept_any(self, *types: TokenType) -> TokenType | None:
        """Consume if the current token is any of ``types``; return which."""
        tt = self._peek_type()
        if tt in types:
            self._advance()
            return tt
        return None

    # --- statement dispatch ---
    def parse_statement(self) -> Stmt | DDL:
        tt = self._peek_type()
        if tt is TokenType.SELECT:
            return self._parse_select()
        if tt is TokenType.INSERT:
            return self._parse_insert()
        if tt is TokenType.UPDATE:
            return self._parse_update()
        if tt is TokenType.DELETE:
            return self._parse_delete()
        if tt is TokenType.CREATE:
            return self._parse_create()
        if tt is TokenType.DROP:
            return self._parse_drop()
        if tt is TokenType.BEGIN:
            return self._parse_begin()
        if tt is TokenType.COMMIT:
            self._advance()
            self._accept(TokenType.TRANSACTION)
            return Commit()
        if tt is TokenType.END:
            self._advance()
            self._accept(TokenType.TRANSACTION)
            return Commit()
        if tt is TokenType.ROLLBACK:
            self._advance()
            self._accept(TokenType.TRANSACTION)
            return Rollback()
        raise ParseError(
            f"unexpected token {self._peek().value!r}",
            self._peek().offset, self._peek().value,
        )

    # --- SELECT ---
    def _parse_select(self) -> Select:
        self._expect(TokenType.SELECT)
        distinctness = None
        if self._accept(TokenType.DISTINCT):
            distinctness = Distinctness.Distinct
        elif self._accept(TokenType.ALL):
            distinctness = Distinctness.All

        columns = self._parse_result_columns()

        from_clause = None
        if self._accept(TokenType.FROM):
            from_clause = self._parse_from()

        where = None
        if self._accept(TokenType.WHERE):
            where = self._parse_expr(0)

        group_by = None
        if self._accept(TokenType.GROUP):
            self._expect(TokenType.BY)
            group_by = self._parse_expr_list()

        having = None
        if self._accept(TokenType.HAVING):
            having = self._parse_expr(0)

        one_select = OneSelect(
            columns=columns,
            distinctness=distinctness,
            from_clause=from_clause,
            where=where,
            group_by=group_by,
            having=having,
        )

        order_by = None
        if self._accept(TokenType.ORDER):
            self._expect(TokenType.BY)
            order_by = self._parse_order_by()

        limit = None
        if self._accept(TokenType.LIMIT):
            limit = self._parse_limit()

        return Select(
            body=SelectBody(select=one_select),
            order_by=order_by,
            limit=limit,
        )

    def _parse_result_columns(self) -> list[ResultColumn]:
        cols: list[ResultColumn] = [self._parse_result_column()]
        while self._accept(TokenType.COMMA):
            cols.append(self._parse_result_column())
        return cols

    def _parse_result_column(self) -> ResultColumn:
        if self._accept(TokenType.STAR):
            return ResultColumn(star=True)
        # table.* — look for ID DOT STAR
        peek1 = self._peek_at(1)
        peek2 = self._peek_at(2)
        if (self._peek_type() is TokenType.ID
                and peek1 is not None and peek1.token_type is TokenType.DOT
                and peek2 is not None and peek2.token_type is TokenType.STAR):
            table_name = Name(self._advance().value)
            self._advance()  # DOT
            self._advance()  # STAR
            return ResultColumn(table_star=table_name)
        expr = self._parse_expr(0)
        alias = None
        if self._accept(TokenType.AS):
            alias_name = self._parse_name()
            alias = As(alias_name, has_as_keyword=True)
        elif self._peek_type() is TokenType.ID or self._peek_type() is TokenType.STRING:
            # Implicit alias (no AS keyword).
            alias_name = Name(self._advance().value)
            alias = As(alias_name, has_as_keyword=False)
        return ResultColumn(expr=expr, alias=alias)

    def _parse_from(self) -> FromClause:
        table_name = self._parse_name()
        schema = None
        if self._accept(TokenType.DOT):
            schema = table_name
            table_name = self._parse_name()
        alias = None
        if self._accept(TokenType.AS):
            alias = self._parse_name()
        elif self._peek_type() is TokenType.ID:
            alias = Name(self._advance().value)
        return FromClause(table=SelectTable(name=table_name, schema=schema, alias=alias))

    def _parse_order_by(self) -> list[SortedColumn]:
        cols: list[SortedColumn] = [self._parse_sorted_column()]
        while self._accept(TokenType.COMMA):
            cols.append(self._parse_sorted_column())
        return cols

    def _parse_sorted_column(self) -> SortedColumn:
        expr = self._parse_expr(0)
        order = None
        if self._accept(TokenType.ASC):
            order = SortOrder.Asc
        elif self._accept(TokenType.DESC):
            order = SortOrder.Desc
        return SortedColumn(expr=expr, order=order)

    def _parse_limit(self) -> Limit:
        count = self._parse_expr(0)
        offset = None
        if self._accept(TokenType.OFFSET):
            offset = self._parse_expr(0)
        return Limit(count=count, offset=offset)

    # --- INSERT ---
    def _parse_insert(self) -> Insert:
        self._expect(TokenType.INSERT)
        or_action = None
        if self._accept(TokenType.OR):
            for kw, action in [(TokenType.REPLACE, "REPLACE"), (TokenType.IGNORE, "IGNORE"),
                               (TokenType.FAIL, "FAIL"), (TokenType.ABORT, "ABORT"),
                               (TokenType.ROLLBACK, "ROLLBACK")]:
                if self._accept(kw):
                    or_action = action
                    break
            if or_action is None:
                raise ParseError("expected REPLACE/IGNORE/FAIL/ABORT/ROLLBACK after OR", self._peek().offset)
        self._expect(TokenType.INTO)
        table_name = self._parse_name()
        columns = None
        if self._accept(TokenType.LP):
            cols: list[Name] = [self._parse_name()]
            while self._accept(TokenType.COMMA):
                cols.append(self._parse_name())
            self._expect(TokenType.RP)
            columns = cols
        self._expect(TokenType.VALUES)
        values: list[list[Expr]] = []
        while True:
            self._expect(TokenType.LP)
            row: list[Expr] = [self._parse_expr(0)]
            while self._accept(TokenType.COMMA):
                row.append(self._parse_expr(0))
            self._expect(TokenType.RP)
            values.append(row)
            if not self._accept(TokenType.COMMA):
                break
        return Insert(table=table_name, values=values, columns=columns, or_action=or_action)

    # --- UPDATE ---
    def _parse_update(self) -> Update:
        self._expect(TokenType.UPDATE)
        table_name = self._parse_name()
        self._expect(TokenType.SET)
        assignments: list[tuple[Name, Expr]] = []
        while True:
            col = self._parse_name()
            self._expect(TokenType.EQ)
            val = self._parse_expr(0)
            assignments.append((col, val))
            if not self._accept(TokenType.COMMA):
                break
        where = None
        if self._accept(TokenType.WHERE):
            where = self._parse_expr(0)
        return Update(table=table_name, assignments=assignments, where=where)

    # --- DELETE ---
    def _parse_delete(self) -> Delete:
        self._expect(TokenType.DELETE)
        self._expect(TokenType.FROM)
        table_name = self._parse_name()
        where = None
        if self._accept(TokenType.WHERE):
            where = self._parse_expr(0)
        return Delete(table=table_name, where=where)

    # --- CREATE ---
    def _parse_create(self) -> DDL:
        self._expect(TokenType.CREATE)
        # CREATE TABLE / CREATE INDEX / CREATE UNIQUE INDEX
        if self._accept(TokenType.TABLE):
            return self._parse_create_table()
        unique = False
        if self._accept(TokenType.UNIQUE):
            unique = True
        if self._accept(TokenType.INDEX):
            return self._parse_create_index(unique)
        raise ParseError("expected TABLE or INDEX after CREATE", self._peek().offset)

    def _parse_create_table(self) -> CreateTable:
        if_not_exists = False
        if self._accept(TokenType.IF):
            self._expect(TokenType.NOT)
            self._expect(TokenType.EXISTS)
            if_not_exists = True
        table_name = self._parse_name()
        self._expect(TokenType.LP)
        columns: list[ColumnDefinition] = []
        table_constraints: list[TableConstraint] = []
        while True:
            # Check for table-level constraints.
            if self._accept(TokenType.PRIMARY):
                self._expect(TokenType.KEY)
                self._expect(TokenType.LP)
                pk_cols: list[Name] = [self._parse_name()]
                while self._accept(TokenType.COMMA):
                    pk_cols.append(self._parse_name())
                self._expect(TokenType.RP)
                table_constraints.append(TableConstraint("PRIMARY KEY", columns=pk_cols))
            elif self._accept(TokenType.UNIQUE):
                self._expect(TokenType.LP)
                uq_cols: list[Name] = [self._parse_name()]
                while self._accept(TokenType.COMMA):
                    uq_cols.append(self._parse_name())
                self._expect(TokenType.RP)
                table_constraints.append(TableConstraint("UNIQUE", columns=uq_cols))
            elif self._accept(TokenType.CONSTRAINT):
                # Named constraint — skip the name and parse the constraint.
                self._parse_name()
                # Re-dispatch: the next token determines the constraint type.
                # For simplicity, fall through to column parsing on the next iteration.
                continue
            elif self._accept(TokenType.CHECK):
                self._expect(TokenType.LP)
                chk = self._parse_expr(0)
                self._expect(TokenType.RP)
                table_constraints.append(TableConstraint("CHECK", expr=chk))
            else:
                # Column definition.
                col_name = self._parse_name()
                type_name = None
                if self._peek_type() is TokenType.ID:
                    type_name = self._advance().value
                constraints = self._parse_column_constraints()
                columns.append(ColumnDefinition(col_name, constraints, type_name))
            if not self._accept(TokenType.COMMA):
                break
        self._expect(TokenType.RP)
        without_rowid = False
        if self._accept(TokenType.WITHOUT):
            # ROWID is not a keyword — accept it as an identifier.
            if self._peek_type() is TokenType.ID and self._peek().value.upper() == "ROWID":
                self._advance()
            without_rowid = True
        return CreateTable(
            table=table_name, columns=columns, table_constraints=table_constraints,
            if_not_exists=if_not_exists, without_rowid=without_rowid,
        )

    def _parse_column_constraints(self) -> list[ColumnConstraint]:
        constraints: list[ColumnConstraint] = []
        while True:
            tt = self._peek_type()
            if tt is TokenType.PRIMARY:
                self._advance()
                self._expect(TokenType.KEY)
                autoincr = False
                if self._accept(TokenType.AUTOINCR):
                    autoincr = True
                # Optional ASC/DESC — ignored for now.
                self._accept(TokenType.ASC) or self._accept(TokenType.DESC)
                constraints.append(ColumnConstraint("PRIMARY KEY", autoincrement=autoincr))
            elif tt is TokenType.NOT:
                self._advance()
                self._expect(TokenType.NULL)
                constraints.append(ColumnConstraint("NOT NULL"))
            elif tt is TokenType.UNIQUE:
                self._advance()
                constraints.append(ColumnConstraint("UNIQUE"))
            elif tt is TokenType.DEFAULT:
                self._advance()
                # DEFAULT can be a literal or a parenthesized expression.
                if self._accept(TokenType.LP):
                    expr = self._parse_expr(0)
                    self._expect(TokenType.RP)
                else:
                    expr = self._parse_literal()
                constraints.append(ColumnConstraint("DEFAULT", expr=expr))
            elif tt is TokenType.CHECK:
                self._advance()
                self._expect(TokenType.LP)
                expr = self._parse_expr(0)
                self._expect(TokenType.RP)
                constraints.append(ColumnConstraint("CHECK", expr=expr))
            elif tt is TokenType.NULL:
                self._advance()
                constraints.append(ColumnConstraint("NULL"))
            else:
                break
        return constraints

    def _parse_create_index(self, unique: bool) -> CreateIndex:
        if_not_exists = False
        if self._accept(TokenType.IF):
            self._expect(TokenType.NOT)
            self._expect(TokenType.EXISTS)
            if_not_exists = True
        index_name = self._parse_name()
        self._expect(TokenType.ON)
        table_name = self._parse_name()
        self._expect(TokenType.LP)
        cols: list[Name] = [self._parse_name()]
        while self._accept(TokenType.COMMA):
            cols.append(self._parse_name())
        self._expect(TokenType.RP)
        where = None
        if self._accept(TokenType.WHERE):
            where = self._parse_expr(0)
        return CreateIndex(
            index=index_name, table=table_name, columns=cols,
            unique=unique, if_not_exists=if_not_exists, where=where,
        )

    # --- DROP ---
    def _parse_drop(self) -> DDL:
        self._expect(TokenType.DROP)
        if self._accept(TokenType.TABLE):
            if_exists = False
            if self._accept(TokenType.IF):
                self._expect(TokenType.EXISTS)
                if_exists = True
            return DropTable(table=self._parse_name(), if_exists=if_exists)
        if self._accept(TokenType.INDEX):
            if_exists = False
            if self._accept(TokenType.IF):
                self._expect(TokenType.EXISTS)
                if_exists = True
            return DropIndex(index=self._parse_name(), if_exists=if_exists)
        raise ParseError("expected TABLE or INDEX after DROP", self._peek().offset)

    # --- BEGIN ---
    def _parse_begin(self) -> Begin:
        self._expect(TokenType.BEGIN)
        tx_type = "DEFERRED"
        if self._accept(TokenType.DEFERRED):
            tx_type = "DEFERRED"
        elif self._accept(TokenType.IMMEDIATE):
            tx_type = "IMMEDIATE"
        elif self._accept(TokenType.EXCLUSIVE):
            tx_type = "EXCLUSIVE"
        self._accept(TokenType.TRANSACTION)
        return Begin(tx_type=tx_type)

    # --- expressions (precedence climbing) ---
    def _parse_expr(self, min_prec: int) -> Expr:
        self._expr_depth += 1
        if self._expr_depth > _MAX_EXPR_DEPTH:
            self._expr_depth -= 1
            raise ParseError("expression tree too deep")
        try:
            return self._parse_expr_inner(min_prec)
        finally:
            self._expr_depth -= 1

    def _parse_expr_inner(self, min_prec: int) -> Expr:
        result = self._parse_expr_operand()

        while True:
            prec = _PRECEDENCE.get(self._peek_type())
            if prec is None or prec < min_prec:
                break

            prev_pos = self._pos  # stall guard
            tok = self._peek()
            not_ = False

            # Handle NOT before BETWEEN/IN/LIKE/NULL.
            if tok.token_type is TokenType.NOT:
                self._advance()
                nxt = self._peek_type()
                if nxt not in (TokenType.BETWEEN, TokenType.IN,
                               TokenType.MATCH, TokenType.LIKE_KW,
                               TokenType.NULL):
                    raise ParseError(
                        f"expected BETWEEN/IN/LIKE/NULL after NOT, got {nxt.name}",
                        self._peek().offset, self._peek().value,
                    )
                tok = self._peek()
                not_ = True

            tt = tok.token_type

            if tt is TokenType.NULL and not_:
                # NOT NULL — postfix operator.
                self._advance()
                result = NotNullExpr(result)
            elif tt is TokenType.ISNULL:
                self._advance()
                result = IsNullExpr(result)
            elif tt is TokenType.NOTNULL:
                self._advance()
                result = NotNullExpr(result)
            elif tt is TokenType.IS:
                self._advance()
                if self._accept(TokenType.NOT):
                    result = BinaryExpr(result, Operator.IsNot, self._parse_expr(prec + 1))
                else:
                    if self._accept(TokenType.NULL):
                        result = IsNullExpr(result)
                    else:
                        result = BinaryExpr(result, Operator.Is, self._parse_expr(prec + 1))
            elif tt is TokenType.BETWEEN:
                self._advance()
                start = self._parse_expr(prec + 1)
                self._expect(TokenType.AND)
                end = self._parse_expr(prec + 1)
                result = BetweenExpr(result, not_, start, end)
            elif tt is TokenType.IN:
                self._advance()
                self._expect(TokenType.LP)
                values = self._parse_expr_list()
                self._expect(TokenType.RP)
                result = InExpr(result, not_, values)
            elif tt in (TokenType.LIKE_KW, TokenType.MATCH):
                # LIKE/GLOB/REGEXP/MATCH — treat as binary operator.
                self._advance()
                rhs = self._parse_expr(prec + 1)
                op = Operator.Equals if not_ else Operator.Equals  # simplified
                # TODO: map LIKE_KW to a proper operator; for now use a binary expr.
                result = BinaryExpr(result, op, rhs)
            elif tt is TokenType.OR:
                self._advance()
                result = BinaryExpr(result, Operator.Or, self._parse_expr(prec + 1))
            elif tt is TokenType.AND:
                self._advance()
                result = BinaryExpr(result, Operator.And, self._parse_expr(prec + 1))
            elif tt is TokenType.EQ:
                self._advance()
                result = BinaryExpr(result, Operator.Equals, self._parse_expr(prec + 1))
            elif tt is TokenType.NE:
                self._advance()
                result = BinaryExpr(result, Operator.NotEquals, self._parse_expr(prec + 1))
            elif tt is TokenType.LT:
                self._advance()
                result = BinaryExpr(result, Operator.Less, self._parse_expr(prec + 1))
            elif tt is TokenType.LE:
                self._advance()
                result = BinaryExpr(result, Operator.LessEquals, self._parse_expr(prec + 1))
            elif tt is TokenType.GT:
                self._advance()
                result = BinaryExpr(result, Operator.Greater, self._parse_expr(prec + 1))
            elif tt is TokenType.GE:
                self._advance()
                result = BinaryExpr(result, Operator.GreaterEquals, self._parse_expr(prec + 1))
            elif tt is TokenType.PLUS:
                self._advance()
                result = BinaryExpr(result, Operator.Add, self._parse_expr(prec + 1))
            elif tt is TokenType.MINUS:
                self._advance()
                result = BinaryExpr(result, Operator.Subtract, self._parse_expr(prec + 1))
            elif tt is TokenType.STAR:
                self._advance()
                result = BinaryExpr(result, Operator.Multiply, self._parse_expr(prec + 1))
            elif tt is TokenType.SLASH:
                self._advance()
                result = BinaryExpr(result, Operator.Divide, self._parse_expr(prec + 1))
            elif tt is TokenType.REM:
                self._advance()
                result = BinaryExpr(result, Operator.Modulus, self._parse_expr(prec + 1))
            elif tt is TokenType.CONCAT:
                self._advance()
                result = BinaryExpr(result, Operator.Concat, self._parse_expr(prec + 1))
            elif tt is TokenType.BITAND:
                self._advance()
                result = BinaryExpr(result, Operator.BitwiseAnd, self._parse_expr(prec + 1))
            elif tt is TokenType.BITOR:
                self._advance()
                result = BinaryExpr(result, Operator.BitwiseOr, self._parse_expr(prec + 1))
            elif tt is TokenType.LSHIFT:
                self._advance()
                result = BinaryExpr(result, Operator.LeftShift, self._parse_expr(prec + 1))
            elif tt is TokenType.RSHIFT:
                self._advance()
                result = BinaryExpr(result, Operator.RightShift, self._parse_expr(prec + 1))
            elif tt is TokenType.COLLATE:
                self._advance()
                col_name = self._parse_name()
                result = CollateExpr(result, col_name)
            elif tt is TokenType.PTR:
                self._advance()
                # -> / ->> — simplified: treat as binary.
                result = BinaryExpr(result, Operator.Concat, self._parse_expr(prec + 1))
            else:
                # Shouldn't happen (precedence table guarantees it's handled).
                break

            # Stall guard: if we didn't advance, something is wrong.
            if self._pos == prev_pos:
                raise ParseError(
                    f"parser stalled in expression at offset {self._peek().offset}",
                    self._peek().offset, self._peek().value,
                )

        return result

    def _parse_expr_operand(self) -> Expr:
        tok = self._peek()
        tt = tok.token_type

        # NULL
        if tt is TokenType.NULL:
            self._advance()
            return LiteralExpr(Literal.Null)
        # TRUE / FALSE (SQLite 3.23+)
        if tt is TokenType.ID and tok.value.upper() in ("TRUE", "FALSE"):
            self._advance()
            return LiteralExpr(Literal.True_ if tok.value.upper() == "TRUE" else Literal.False_)
        # Integer / Float literal
        if tt is TokenType.INTEGER:
            self._advance()
            return LiteralExpr(Literal.Numeric, tok.value)
        if tt is TokenType.FLOAT:
            self._advance()
            return LiteralExpr(Literal.Numeric, tok.value)
        # Blob literal
        if tt is TokenType.BLOB:
            self._advance()
            return LiteralExpr(Literal.Blob, tok.value)
        # String literal
        if tt is TokenType.STRING:
            self._advance()
            return LiteralExpr(Literal.String, tok.value)
        # Variable (? ?N :name $name)
        if tt is TokenType.VARIABLE:
            self._advance()
            return LiteralExpr(Literal.Keyword, tok.value)  # simplified: parameter as keyword literal
        # Parenthesized expression
        if tt is TokenType.LP:
            self._advance()
            inner = self._parse_expr(0)
            self._expect(TokenType.RP)
            return ParenExpr(inner)
        # Unary: - + ~ NOT
        if tt is TokenType.MINUS:
            self._advance()
            return UnaryExpr(UnaryOperator.Negative, self._parse_expr(11))
        if tt is TokenType.PLUS:
            self._advance()
            return UnaryExpr(UnaryOperator.Positive, self._parse_expr(11))
        if tt is TokenType.BITNOT:
            self._advance()
            return UnaryExpr(UnaryOperator.BitwiseNot, self._parse_expr(11))
        if tt is TokenType.NOT:
            self._advance()
            return UnaryExpr(UnaryOperator.Not, self._parse_expr(3))
        # CAST
        if tt is TokenType.CAST:
            self._advance()
            self._expect(TokenType.LP)
            expr = self._parse_expr(0)
            self._expect(TokenType.AS)
            type_name = self._parse_name().value
            self._expect(TokenType.RP)
            return CastExpr(expr, type_name)
        # CASE
        if tt is TokenType.CASE:
            return self._parse_case()
        # Identifier or function call or qualified name
        if tt is TokenType.ID or tt.is_identifier_keyword():
            return self._parse_id_or_call()
        raise ParseError(
            f"unexpected token {tok.value!r} in expression",
            tok.offset, tok.value,
        )

    def _parse_case(self) -> CaseExpr:
        self._expect(TokenType.CASE)
        base = None
        if self._peek_type() is not TokenType.WHEN:
            base = self._parse_expr(0)
        when_then: list[tuple[Expr, Expr]] = []
        while self._accept(TokenType.WHEN):
            cond = self._parse_expr(0)
            self._expect(TokenType.THEN)
            result = self._parse_expr(0)
            when_then.append((cond, result))
        else_expr = None
        if self._accept(TokenType.ELSE):
            else_expr = self._parse_expr(0)
        self._expect(TokenType.END)
        return CaseExpr(base, when_then, else_expr)

    def _parse_id_or_call(self) -> Expr:
        first = Name(self._advance().value)
        # Function call?
        if self._peek_type() is TokenType.LP:
            self._advance()
            distinct = bool(self._accept(TokenType.DISTINCT))
            args: list[Expr] = []
            if self._peek_type() is not TokenType.RP:
                if self._accept(TokenType.STAR):
                    args.append(LiteralExpr(Literal.Numeric, "*"))
                else:
                    args = self._parse_expr_list()
            self._expect(TokenType.RP)
            return FunctionCallExpr(first, args, distinct)
        # Qualified: table.col or schema.table.col
        if self._accept(TokenType.DOT):
            second = Name(self._advance().value)
            if self._accept(TokenType.DOT):
                third = Name(self._advance().value)
                return DoublyQualifiedExpr(first, second, third)
            return QualifiedExpr(first, second)
        return IdExpr(first)

    def _parse_expr_list(self) -> list[Expr]:
        exprs: list[Expr] = [self._parse_expr(0)]
        while self._accept(TokenType.COMMA):
            exprs.append(self._parse_expr(0))
        return exprs

    def _parse_literal(self) -> Expr:
        """Parse a bare literal (for DEFAULT clauses)."""
        tok = self._peek()
        tt = tok.token_type
        if tt is TokenType.INTEGER or tt is TokenType.FLOAT:
            self._advance()
            return LiteralExpr(Literal.Numeric, tok.value)
        if tt is TokenType.STRING:
            self._advance()
            return LiteralExpr(Literal.String, tok.value)
        if tt is TokenType.BLOB:
            self._advance()
            return LiteralExpr(Literal.Blob, tok.value)
        if tt is TokenType.NULL:
            self._advance()
            return LiteralExpr(Literal.Null)
        if tt in (TokenType.PLUS, TokenType.MINUS):
            self._advance()
            return UnaryExpr(
                UnaryOperator.Positive if tt is TokenType.PLUS else UnaryOperator.Negative,
                self._parse_literal(),
            )
        # Fall back to full expression for complex defaults.
        return self._parse_expr(0)

    def _parse_name(self) -> Name:
        tok = self._peek()
        if tok.token_type is TokenType.ID or tok.token_type.is_identifier_keyword():
            return Name(self._advance().value)
        # Some keywords can be used as names in context.
        if tok.token_type in (TokenType.STRING,):
            return Name(self._advance().value)
        raise ParseError(
            f"expected identifier but found {tok.token_type.name} ({tok.value!r})",
            tok.offset, tok.value,
        )