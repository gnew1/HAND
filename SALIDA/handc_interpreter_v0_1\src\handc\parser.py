from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from .lexer import (
    Token,
    TK_NEWLINE, TK_INDENT, TK_DEDENT, TK_EOF,
    TK_IDENT, TK_KEYWORD, TK_NUMBER, TK_STRING, TK_OP,
    TK_COLON, TK_COMMA, TK_LPAREN, TK_RPAREN, TK_EQ, TK_EMOJI,
    TK_LBRACK, TK_RBRACK, TK_QMARK
)
from .diagnostics import Diagnostic, SrcLoc
from . import ast as A

FUNC_EMOJIS={"🔧","🛠"}
VERIFY_EMOJI="🔍"

@dataclass
class ParseResult:
    program: Optional[A.Program]
    diagnostics: List[Diagnostic]

class Parser:
    def __init__(self, tokens: List[Token], filename: str="<input>"):
        self.toks=tokens
        self.i=0
        self.filename=filename
        self.diagnostics: List[Diagnostic]=[]
        self.err_n=0

    def _at(self) -> Token:
        if self.i >= len(self.toks):
            return self.toks[-1]
        return self.toks[self.i]

    def _peek(self, k: int=1) -> Token:
        j=self.i+k
        if j < len(self.toks):
            return self.toks[j]
        return self.toks[-1]

    def _accept(self, kind: str, value: str|None=None) -> Optional[Token]:
        t=self._at()
        if t.kind==kind and (value is None or t.value==value):
            self.i += 1
            return t
        return None

    def _expect(self, kind: str, value: str|None=None, code: str="HND-PARSE-0001", msg: str="Unexpected token"):
        t=self._at()
        if t.kind==kind and (value is None or t.value==value):
            self.i += 1
            return t
        self.err_n += 1
        self.diagnostics.append(Diagnostic(
            idref=f"3🐛{self.err_n}",
            code=code,
            severity="error",
            message_human=f"{msg}: expected {kind}{'='+value if value else ''}, got {t.kind}({t.value})",
            src=SrcLoc(self.filename, t.span.line, t.span.col),
            fix="Check HAND syntax near this location."
        ))
        return t

    def parse(self) -> ParseResult:
        items=[]
        while self._at().kind != TK_EOF:
            if self._at().kind == TK_EMOJI:
                if self._at().value in FUNC_EMOJIS:
                    items.append(self._parse_funcdef())
                    self._accept(TK_NEWLINE)
                    continue
                if self._at().value == VERIFY_EMOJI:
                    items.append(self._parse_verify())
                    self._accept(TK_NEWLINE)
                    continue
                sec=self._parse_section()
                items.append(sec)
                continue
            if self._accept(TK_NEWLINE):
                continue
            if self._at().kind in (TK_KEYWORD, TK_IDENT):
                items.append(self._parse_stmt())
                self._accept(TK_NEWLINE)
                continue
            # recovery
            self._expect(self._at().kind, code="HND-PARSE-RECOVER", msg="Unrecognized top-level token")
            self.i += 1
        return ParseResult(A.Program(items), self.diagnostics)

    def _parse_section(self) -> A.Section:
        emo=self._expect(TK_EMOJI, msg="Section must start with an emoji").value
        parts=[]
        has_colon=False
        while self._at().kind not in (TK_NEWLINE, TK_EOF):
            if self._accept(TK_COLON):
                has_colon=True
                break
            t=self._at()
            self.i += 1
            parts.append(t.value)
        self._expect(TK_NEWLINE, msg="Expected newline after section header")
        body=None
        if has_colon and self._accept(TK_INDENT):
            body=self._parse_block()
            self._expect(TK_DEDENT, msg="Expected DEDENT to close section block")
        return A.Section(emoji=emo, header=" ".join(parts).strip(), has_colon=has_colon, body=body)

    def _parse_block(self) -> List[A.Stmt]:
        stmts=[]
        while self._at().kind not in (TK_DEDENT, TK_EOF):
            if self._accept(TK_NEWLINE):
                continue
            if self._at().kind==TK_EMOJI and self._at().value==VERIFY_EMOJI:
                stmts.append(self._parse_verify())
                self._accept(TK_NEWLINE)
                continue
            stmts.append(self._parse_stmt())
            self._accept(TK_NEWLINE)
        return stmts

    def _parse_stmt(self) -> A.Stmt:
        t=self._at()
        if t.kind==TK_EMOJI and t.value in FUNC_EMOJIS:
            return self._parse_funcdef()
        if t.kind==TK_KEYWORD and t.value=="verify":
            return self._parse_verify()
        if t.kind==TK_KEYWORD and t.value=="if":
            return self._parse_if()
        if t.kind==TK_KEYWORD and t.value=="while":
            return self._parse_while()
        if t.kind==TK_KEYWORD and t.value=="return":
            return self._parse_return()
        if t.kind==TK_KEYWORD and t.value=="show":
            return self._parse_show()
        if t.kind==TK_IDENT and self._looks_like_assign():
            return self._parse_assign()
        expr=self._parse_expr()
        return A.ExprStmt(expr)

    def _looks_like_assign(self) -> bool:
        if self._at().kind != TK_IDENT:
            return False
        j=self.i+1
        if j >= len(self.toks):
            return False
        if self.toks[j].kind==TK_COLON:
            k=j+1
            while k < len(self.toks) and self.toks[k].kind not in (TK_EQ, TK_NEWLINE, TK_EOF):
                k += 1
            return k < len(self.toks) and self.toks[k].kind==TK_EQ
        return self.toks[j].kind==TK_EQ

    def _parse_assign(self) -> A.AssignStmt:
        name=self._expect(TK_IDENT, msg="Expected identifier in assignment").value
        declared=None
        if self._accept(TK_COLON):
            declared=self._parse_typeexpr()
        self._expect(TK_EQ, msg="Expected '=' in assignment")
        value=self._parse_expr()
        return A.AssignStmt(name=name, declared_type=declared, value=value)

    def _parse_verify(self) -> A.VerifyStmt:
        if self._at().kind==TK_EMOJI:
            self._expect(TK_EMOJI, value=VERIFY_EMOJI, msg="Expected 🔍")
        else:
            self._expect(TK_KEYWORD, value="verify", msg="Expected verify keyword")
        expr=self._parse_expr()
        return A.VerifyStmt(expr)

    def _parse_funcdef(self) -> A.FuncDef:
        emo=self._expect(TK_EMOJI, msg="Function must start with 🛠 or 🔧").value
        # Optional label: IDENT right after emoji, but only if a second IDENT follows.
        if self._at().kind==TK_IDENT and self._peek(1).kind==TK_IDENT:
            self.i += 1
        name=self._expect(TK_IDENT, msg="Expected function name").value
        self._expect(TK_LPAREN, msg="Expected '(' after function name")
        params=[]
        if self._at().kind != TK_RPAREN:
            params.append(self._parse_param())
            while self._accept(TK_COMMA):
                params.append(self._parse_param())
        self._expect(TK_RPAREN, msg="Expected ')' after parameters")
        ret_type=None
        if self._at().kind==TK_OP and self._at().value=="->":
            self.i += 1
            ret_type=self._parse_typeexpr()
        self._expect(TK_COLON, msg="Expected ':' after function signature")
        self._expect(TK_NEWLINE, msg="Expected newline after function ':'")
        self._expect(TK_INDENT, msg="Expected INDENT to start function body")
        body=self._parse_block()
        self._expect(TK_DEDENT, msg="Expected DEDENT after function body")
        return A.FuncDef(name=name, params=params, return_type=ret_type, body=body)

    def _parse_param(self) -> A.Param:
        name=self._expect(TK_IDENT, msg="Expected parameter name").value
        texpr=None
        if self._accept(TK_COLON):
            texpr=self._parse_typeexpr()
        return A.Param(name=name, type=texpr)

    def _parse_if(self) -> A.IfStmt:
        self._expect(TK_KEYWORD, value="if", msg="Expected 'if'")
        cond=self._parse_expr()
        self._expect(TK_COLON, msg="Expected ':' after if condition")
        self._expect(TK_NEWLINE, msg="Expected newline after if ':'")
        self._expect(TK_INDENT, msg="Expected INDENT to start if body")
        then_body=self._parse_block()
        self._expect(TK_DEDENT, msg="Expected DEDENT after if body")
        else_body=None
        if self._at().kind==TK_KEYWORD and self._at().value=="else":
            self.i += 1
            self._expect(TK_COLON, msg="Expected ':' after else")
            self._expect(TK_NEWLINE, msg="Expected newline after else ':'")
            self._expect(TK_INDENT, msg="Expected INDENT to start else body")
            else_body=self._parse_block()
            self._expect(TK_DEDENT, msg="Expected DEDENT after else body")
        return A.IfStmt(cond=cond, then_body=then_body, else_body=else_body)

    def _parse_while(self) -> A.WhileStmt:
        self._expect(TK_KEYWORD, value="while", msg="Expected 'while'")
        cond=self._parse_expr()
        self._expect(TK_COLON, msg="Expected ':' after while condition")
        self._expect(TK_NEWLINE, msg="Expected newline after while ':'")
        self._expect(TK_INDENT, msg="Expected INDENT to start while body")
        body=self._parse_block()
        self._expect(TK_DEDENT, msg="Expected DEDENT after while body")
        return A.WhileStmt(cond=cond, body=body)

    def _parse_return(self) -> A.ReturnStmt:
        self._expect(TK_KEYWORD, value="return", msg="Expected 'return'")
        if self._at().kind in (TK_NEWLINE, TK_DEDENT, TK_EOF):
            return A.ReturnStmt(None)
        return A.ReturnStmt(self._parse_expr())

    def _parse_show(self) -> A.ShowStmt:
        self._expect(TK_KEYWORD, value="show", msg="Expected 'show'")
        return A.ShowStmt(self._parse_expr())

    # --- Type expressions ---
    def _parse_typeexpr(self) -> A.TypeExpr:
        base=self._parse_typeprimary()
        if self._accept(TK_QMARK):
            return A.TypeOptional(base)
        return base

    def _parse_typeprimary(self) -> A.TypeExpr:
        if self._at().kind==TK_KEYWORD and self._at().value in ("Int","Float","Bool","Text","Null","List","Map","Record","Result","Any","Never","Optional"):
            name=self._at().value
            self.i += 1
            tname=A.TypeName(name)
        elif self._at().kind==TK_IDENT:
            name=self._at().value
            self.i += 1
            tname=A.TypeName(name)
        else:
            t=self._at()
            self._expect(TK_IDENT, code="HND-TYPE-0001", msg="Expected type name")
            tname=A.TypeName("Any")
        if self._accept(TK_LBRACK):
            args=[self._parse_typeexpr()]
            while self._accept(TK_COMMA):
                args.append(self._parse_typeexpr())
            self._expect(TK_RBRACK, msg="Expected ']' to close type arguments")
            return A.TypeApp(base=tname, args=args)
        return tname

    # --- Expressions ---
    def _parse_expr(self) -> A.Expr:
        return self._parse_equality()

    def _parse_equality(self) -> A.Expr:
        expr=self._parse_compare()
        while self._at().kind==TK_OP and self._at().value in ("==","!="):
            op=self._at().value; self.i += 1
            right=self._parse_compare()
            expr=A.Binary(expr, op, right)
        return expr

    def _parse_compare(self) -> A.Expr:
        expr=self._parse_term()
        while self._at().kind==TK_OP and self._at().value in ("<","<=",">",">="):
            op=self._at().value; self.i += 1
            right=self._parse_term()
            expr=A.Binary(expr, op, right)
        return expr

    def _parse_term(self) -> A.Expr:
        expr=self._parse_factor()
        while self._at().kind==TK_OP and self._at().value in ("+","-"):
            op=self._at().value; self.i += 1
            right=self._parse_factor()
            expr=A.Binary(expr, op, right)
        return expr

    def _parse_factor(self) -> A.Expr:
        expr=self._parse_unary()
        while self._at().kind==TK_OP and self._at().value in ("*","/","%"):
            op=self._at().value; self.i += 1
            right=self._parse_unary()
            expr=A.Binary(expr, op, right)
        return expr

    def _parse_unary(self) -> A.Expr:
        if self._at().kind==TK_OP and self._at().value=="-":
            self.i += 1
            return A.Unary("-", self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> A.Expr:
        t=self._at()
        if t.kind==TK_NUMBER:
            self.i += 1
            if "." in t.value:
                return A.Literal("Float", float(t.value))
            return A.Literal("Int", int(t.value))
        if t.kind==TK_STRING:
            self.i += 1
            return A.Literal("Text", t.value)
        if t.kind==TK_EMOJI:
            # In expr position, treat emoji as Text literal (quoted)
            self.i += 1
            return A.Literal("Text", f"\"{t.value}\"")
        if t.kind==TK_KEYWORD and t.value in ("true","false"):
            self.i += 1
            return A.Literal("Bool", t.value=="true")
        if t.kind==TK_KEYWORD and t.value=="null":
            self.i += 1
            return A.Literal("Null", None)
        if t.kind==TK_KEYWORD and t.value=="ask":
            # builtin input function; tokenized as keyword for determinism
            self.i += 1
            name=t.value
            if self._accept(TK_LPAREN):
                args=[]
                if self._at().kind != TK_RPAREN:
                    args.append(self._parse_expr())
                    while self._accept(TK_COMMA):
                        args.append(self._parse_expr())
                self._expect(TK_RPAREN, msg="Expected ')' after call arguments")
                return A.Call(callee=name, args=args)
            self._expect(TK_LPAREN, code="HND-EXPR-0002", msg="ask must be called: ask(prompt)")
            return A.Literal("Null", None)
        if t.kind==TK_IDENT:
            self.i += 1
            name=t.value
            if self._accept(TK_LPAREN):
                args=[]
                if self._at().kind != TK_RPAREN:
                    args.append(self._parse_expr())
                    while self._accept(TK_COMMA):
                        args.append(self._parse_expr())
                self._expect(TK_RPAREN, msg="Expected ')' after call arguments")
                return A.Call(callee=name, args=args)
            return A.Var(name)
        if self._accept(TK_LPAREN):
            expr=self._parse_expr()
            self._expect(TK_RPAREN, msg="Expected ')'")
            return A.Paren(expr)
        self._expect(TK_IDENT, code="HND-EXPR-0001", msg="Expected expression")
        self.i += 1
        return A.Literal("Null", None)

def parse(tokens: List[Token], filename: str="<input>") -> ParseResult:
    return Parser(tokens, filename).parse()
