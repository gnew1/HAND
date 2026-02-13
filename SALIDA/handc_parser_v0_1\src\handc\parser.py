from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .lexer import (
    Token,
    TK_NEWLINE, TK_INDENT, TK_DEDENT, TK_EOF,
    TK_IDENT, TK_KEYWORD, TK_NUMBER, TK_STRING, TK_OP,
    TK_COLON, TK_COMMA, TK_LPAREN, TK_RPAREN, TK_EQ, TK_EMOJI
)
from .diagnostics import Diagnostic, SrcLoc
from . import ast as A

# ---------------------------------------------------------------------------
# HAND Core v0.1 grammar (PEG-ish, layout-sensitive)
#
# Program        <- (Section / Stmt NEWLINE)* EOF
# Section        <- EMOJI SectionTail (':' NEWLINE INDENT Block DEDENT)? NEWLINE
# Stmt           <- FuncDef / IfStmt / WhileStmt / Return / Show / Assign / ExprStmt
# FuncDef        <- '🔧' IdentOrLabel? IDENT '(' ParamList? ')' ':' NEWLINE INDENT Block DEDENT
# IfStmt         <- 'if' Expr ':' NEWLINE INDENT Block DEDENT ('else' ':' NEWLINE INDENT Block DEDENT)?
# WhileStmt      <- 'while' Expr ':' NEWLINE INDENT Block DEDENT
# Return         <- 'return' Expr?
# Show           <- 'show' Expr
# Assign         <- IDENT '=' Expr
# ExprStmt       <- Expr
#
# Expr precedence:
# Equality -> Compare ((==|!=) Compare)*
# Compare  -> Term ((<|<=|>|>=) Term)*
# Term     -> Factor ((+|-) Factor)*
# Factor   -> Unary ((*|/|%) Unary)*
# Unary    -> ('-' Unary) | Primary
# Primary  -> NUMBER | STRING | true|false|null | IDENT ( '(' args? ')' )? | '(' Expr ')'
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    program: Optional[A.Program]
    diagnostics: List[Diagnostic]

class Parser:
    def __init__(self, tokens: List[Token], filename: str):
        self.toks = tokens
        self.i = 0
        self.filename = filename
        self.diags: List[Diagnostic] = []
        self.err_n = 0

    def _peek(self, k: int = 0) -> Token:
        j = min(self.i + k, len(self.toks) - 1)
        return self.toks[j]

    def _at(self, kind: str, value: Optional[str] = None) -> bool:
        t = self._peek()
        if t.kind != kind:
            return False
        return (value is None) or (t.value == value)

    def _take(self) -> Token:
        t = self._peek()
        self.i = min(self.i + 1, len(self.toks))
        return t

    def _expect(self, kind: str, value: Optional[str] = None, code: str="HND-PARSE-0001", msg: str="Unexpected token.") -> Token:
        if self._at(kind, value):
            return self._take()
        self._error(self._peek(), code, msg)
        return self._take()

    def _error(self, tok: Token, code: str, msg: str):
        self.err_n += 1
        self.diags.append(Diagnostic(
            idref=f"3🐛{self.err_n}",
            code=code,
            severity="error",
            message_human=msg,
            src=SrcLoc(self.filename, tok.span.line, tok.span.col),
            fix=None
        ))

    def parse(self) -> ParseResult:
        items: List[A.TopItem] = []
        # tolerate leading NEWLINEs
        while self._at(TK_NEWLINE):
            self._take()
        while not self._at(TK_EOF):
            if self._at(TK_EMOJI):
                sec = self._parse_section()
                if sec:
                    items.append(sec)
                continue
            stmt = self._parse_stmt()
            items.append(stmt)
            # consume optional NEWLINEs after a statement
            while self._at(TK_NEWLINE):
                self._take()
        return ParseResult(A.Program(items), self.diags)

    # ---- Sections ----
    def _parse_section(self) -> Optional[A.Section]:
        emoji = self._expect(TK_EMOJI, msg="Expected section emoji.").value
        # gather tokens until COLON or NEWLINE
        parts: List[str] = []
        has_colon = False
        while not self._at(TK_NEWLINE) and not self._at(TK_EOF) and not self._at(TK_COLON):
            t = self._take()
            parts.append(t.value)
        if self._at(TK_COLON):
            has_colon = True
            self._take()  # colon
        header = " ".join(parts).strip()
        # newline required
        self._expect(TK_NEWLINE, msg="Expected newline after section header.")
        body: Optional[List[A.Stmt]] = None
        if has_colon:
            # optional block
            if self._at(TK_INDENT):
                self._take()
                body = self._parse_block()
                self._expect(TK_DEDENT, msg="Expected DEDENT to close section block.")
            else:
                body = []
        # consume extra blank lines
        while self._at(TK_NEWLINE):
            self._take()
        return A.Section(emoji=emoji, header=header, has_colon=has_colon, body=body)

    # ---- Blocks ----
    def _parse_block(self) -> List[A.Stmt]:
        stmts: List[A.Stmt] = []
        while not self._at(TK_DEDENT) and not self._at(TK_EOF):
            if self._at(TK_NEWLINE):
                self._take()
                continue
            if self._at(TK_EMOJI):
                # inside blocks, emojis are allowed only as raw section-like statement
                sec = self._parse_section()
                stmts.append(A.ExprStmt(expr=A.Literal("Text", f"[SECTION {sec.emoji} {sec.header}]")))
                continue
            s = self._parse_stmt()
            stmts.append(s)
            while self._at(TK_NEWLINE):
                self._take()
        return stmts

    # ---- Statements ----
    def _parse_stmt(self) -> A.Stmt:
        if self._at(TK_EMOJI) and self._peek().value == "🔧":
            return self._parse_funcdef()
        if self._at(TK_KEYWORD, "if"):
            return self._parse_if()
        if self._at(TK_KEYWORD, "while"):
            return self._parse_while()
        if self._at(TK_KEYWORD, "return"):
            return self._parse_return()
        if self._at(TK_KEYWORD, "show"):
            return self._parse_show()

        # assignment lookahead: IDENT '='
        if self._at(TK_IDENT) and self._peek(1).kind == TK_EQ:
            name = self._take().value
            self._take()  # '='
            expr = self._parse_expr()
            return A.AssignStmt(name=name, value=expr)

        # otherwise expression statement
        expr = self._parse_expr()
        return A.ExprStmt(expr=expr)

    def _parse_funcdef(self) -> A.FuncDef:
        self._expect(TK_EMOJI, "🔧", msg="Expected 🔧 for function definition.")
        # Optional label (e.g., FUNCIÓN / FUNCTION) as IDENT
        name_tok = self._peek()
        label = None
        if name_tok.kind == TK_IDENT and self._peek(1).kind == TK_IDENT and self._peek(2).kind == TK_LPAREN:
            label = self._take().value
        # function name
        fn = self._expect(TK_IDENT, msg="Expected function name.").value
        self._expect(TK_LPAREN, msg="Expected '(' after function name.")
        params: List[str] = []
        if not self._at(TK_RPAREN):
            params.append(self._expect(TK_IDENT, msg="Expected parameter name.").value)
            while self._at(TK_COMMA):
                self._take()
                params.append(self._expect(TK_IDENT, msg="Expected parameter name after comma.").value)
        self._expect(TK_RPAREN, msg="Expected ')' after parameters.")
        self._expect(TK_COLON, msg="Expected ':' after function signature.")
        self._expect(TK_NEWLINE, msg="Expected newline after function header.")
        self._expect(TK_INDENT, msg="Expected INDENT to start function body.")
        body = self._parse_block()
        self._expect(TK_DEDENT, msg="Expected DEDENT to close function body.")
        return A.FuncDef(name=fn, params=params, body=body)

    def _parse_if(self) -> A.IfStmt:
        self._expect(TK_KEYWORD, "if", msg="Expected 'if'.")
        cond = self._parse_expr()
        self._expect(TK_COLON, msg="Expected ':' after if condition.")
        self._expect(TK_NEWLINE, msg="Expected newline after if header.")
        self._expect(TK_INDENT, msg="Expected INDENT to start if body.")
        then_body = self._parse_block()
        self._expect(TK_DEDENT, msg="Expected DEDENT to close if body.")
        else_body: Optional[List[A.Stmt]] = None
        if self._at(TK_KEYWORD, "else"):
            self._take()
            self._expect(TK_COLON, msg="Expected ':' after else.")
            self._expect(TK_NEWLINE, msg="Expected newline after else.")
            self._expect(TK_INDENT, msg="Expected INDENT to start else body.")
            else_body = self._parse_block()
            self._expect(TK_DEDENT, msg="Expected DEDENT to close else body.")
        return A.IfStmt(cond=cond, then_body=then_body, else_body=else_body)

    def _parse_while(self) -> A.WhileStmt:
        self._expect(TK_KEYWORD, "while", msg="Expected 'while'.")
        cond = self._parse_expr()
        self._expect(TK_COLON, msg="Expected ':' after while condition.")
        self._expect(TK_NEWLINE, msg="Expected newline after while header.")
        self._expect(TK_INDENT, msg="Expected INDENT to start while body.")
        body = self._parse_block()
        self._expect(TK_DEDENT, msg="Expected DEDENT to close while body.")
        return A.WhileStmt(cond=cond, body=body)

    def _parse_return(self) -> A.ReturnStmt:
        self._take()  # return
        if self._at(TK_NEWLINE) or self._at(TK_DEDENT) or self._at(TK_EOF):
            return A.ReturnStmt(value=None)
        val = self._parse_expr()
        return A.ReturnStmt(value=val)

    def _parse_show(self) -> A.ShowStmt:
        self._take()  # show
        val = self._parse_expr()
        return A.ShowStmt(value=val)

    # ---- Expressions ----
    def _parse_expr(self) -> A.Expr:
        return self._parse_equality()

    def _parse_equality(self) -> A.Expr:
        expr = self._parse_compare()
        while self._at(TK_OP) and self._peek().value in ("==","!="):
            op = self._take().value
            rhs = self._parse_compare()
            expr = A.Binary(expr, op, rhs)
        return expr

    def _parse_compare(self) -> A.Expr:
        expr = self._parse_term()
        while self._at(TK_OP) and self._peek().value in ("<","<=",">",">="):
            op = self._take().value
            rhs = self._parse_term()
            expr = A.Binary(expr, op, rhs)
        return expr

    def _parse_term(self) -> A.Expr:
        expr = self._parse_factor()
        while self._at(TK_OP) and self._peek().value in ("+","-"):
            op = self._take().value
            rhs = self._parse_factor()
            expr = A.Binary(expr, op, rhs)
        return expr

    def _parse_factor(self) -> A.Expr:
        expr = self._parse_unary()
        while self._at(TK_OP) and self._peek().value in ("*","/","%"):
            op = self._take().value
            rhs = self._parse_unary()
            expr = A.Binary(expr, op, rhs)
        return expr

    def _parse_unary(self) -> A.Expr:
        if self._at(TK_OP, "-"):
            op = self._take().value
            return A.Unary(op, self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> A.Expr:
        t = self._peek()

        if t.kind == TK_NUMBER:
            tok = self._take()
            if "." in tok.value:
                return A.Literal("Float", float(tok.value))
            return A.Literal("Int", int(tok.value))

        if t.kind == TK_STRING:
            tok = self._take()
            raw = tok.value[1:-1]
            # Deterministic unescape: only \n \t \r \\ \" are interpreted.
            val_chars: List[str] = []
            k = 0
            while k < len(raw):
                c = raw[k]
                if c != "\\":
                    val_chars.append(c)
                    k += 1
                    continue
                k += 1
                if k >= len(raw):
                    val_chars.append("\\")
                    break
                e = raw[k]
                k += 1
                if e == "n":
                    val_chars.append("\n")
                elif e == "t":
                    val_chars.append("\t")
                elif e == "r":
                    val_chars.append("\r")
                elif e == "\\":
                    val_chars.append("\\")
                elif e == '"':
                    val_chars.append('"')
                else:
                    # Unknown escapes are preserved literally (backslash + char).
                    val_chars.append("\\" + e)
            val = "".join(val_chars)
            return A.Literal("Text", val)

        if t.kind == TK_KEYWORD and t.value in ("true","false"):
            self._take()
            return A.Literal("Bool", t.value == "true")

        if t.kind == TK_KEYWORD and t.value == "null":
            self._take()
            return A.Literal("Null", None)

        if t.kind == TK_IDENT:
            name = self._take().value
            # call?
            if self._at(TK_LPAREN):
                self._take()
                args: List[A.Expr] = []
                if not self._at(TK_RPAREN):
                    args.append(self._parse_expr())
                    while self._at(TK_COMMA):
                        self._take()
                        args.append(self._parse_expr())
                self._expect(TK_RPAREN, msg="Expected ')' after call args.")
                return A.Call(fn=name, args=args)
            return A.Var(name=name)

        if t.kind == TK_LPAREN:
            self._take()
            expr = self._parse_expr()
            self._expect(TK_RPAREN, msg="Expected ')' after expression.")
            return A.Paren(expr=expr)

        if t.kind == TK_EMOJI:
            # treat emoji as literal Text (v0.1 parser support)
            self._take()
            return A.Literal("Text", t.value)

        # fallback
        self._error(t, "HND-PARSE-0099", f"Unexpected token in expression: {t.kind} '{t.value}'.")
        self._take()
        return A.Literal("Never", None)

def parse(tokens: List[Token], filename: str="<input>") -> ParseResult:
    return Parser(tokens, filename).parse()
