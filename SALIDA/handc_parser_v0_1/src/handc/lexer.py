from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import re
import unicodedata

from .diagnostics import Diagnostic, SrcLoc

# Token kinds
TK_NEWLINE="NEWLINE"
TK_INDENT="INDENT"
TK_DEDENT="DEDENT"
TK_EOF="EOF"
TK_IDENT="IDENT"
TK_NUMBER="NUMBER"
TK_STRING="STRING"
TK_OP="OP"
TK_COLON="COLON"
TK_COMMA="COMMA"
TK_LPAREN="LPAREN"
TK_RPAREN="RPAREN"
TK_EQ="EQ"
TK_KEYWORD="KEYWORD"
TK_EMOJI="EMOJI"

# Canonical keywords (HAND Core v0.1)
KEYWORDS={
    # control
    "if","else","while","return",
    # IO
    "ask","show","log",
    # literals
    "true","false","null",
    # types (core)
    "Int","Float","Bool","Text","Null","List","Map","Record","Result","Any","Never",
}

# Operators and punctuation
OPS={"==","!=",">=","<=","<",">","+","-","*","/","%"}
SINGLE={":":TK_COLON,",":TK_COMMA,"(":TK_LPAREN,")":TK_RPAREN,"=":TK_EQ}

# Identifier patterns:
# - ASCII identifier
_re_ident_ascii=re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# - Unicode identifier start = any letter (or underscore), continue = letter/digit/underscore
_re_ident_uni=re.compile(r"(?:[A-Za-z_]|[^\W\d_])(?:[A-Za-z0-9_]|[\d]|[^\W_])*", re.UNICODE)

_re_number=re.compile(r"(?:\d+\.\d+|\d+)")
_re_string=re.compile(r'"([^"\\]|\\.)*"')

# Emoji tokenization: treat "So" sequences + ZWJ/VS + skin tones as a single token.
ZWJ="\u200d"
VS15="\ufe0e"
VS16="\ufe0f"
SKIN_TONE_RANGE=range(0x1F3FB, 0x1F400)

def _is_surrogate(ch: str) -> bool:
    o=ord(ch)
    return 0xD800 <= o <= 0xDFFF

def _is_emoji_start(ch: str) -> bool:
    return unicodedata.category(ch) == "So"

def _is_emoji_continue(ch: str) -> bool:
    if ch in (ZWJ, VS15, VS16):
        return True
    o=ord(ch)
    if o in SKIN_TONE_RANGE:
        return True
    return unicodedata.category(ch) == "So"

@dataclass(frozen=True)
class Span:
    file: str
    line: int
    col: int
    end_col: int  # exclusive

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    span: Span

def lex(text: str, filename: str="<input>") -> Tuple[List[Token], List[Diagnostic]]:
    """Deterministic lexer for HAND Core v0.1 (UTF-8).

    Rule: same bytes -> same tokens on any OS.
    We normalize line endings (CRLF/CR -> LF) but DO NOT normalize Unicode codepoints.
    """
    diagnostics: List[Diagnostic] = []
    tokens: List[Token] = []

    text = text.replace("\r\n","\n").replace("\r","\n")

    # Avoid spurious last empty line when source ends with \n.
    if text.endswith("\n"):
        lines = text[:-1].split("\n")
    else:
        lines = text.split("\n")

    indent_stack=[0]
    lex_err_n=0
    ind_err_n=0

    def lex_error(line:int, col:int, code:str, msg:str, fix:str|None=None):
        nonlocal lex_err_n
        lex_err_n += 1
        diagnostics.append(Diagnostic(
            idref=f"1🐛{lex_err_n}",
            code=code,
            severity="error",
            message_human=msg,
            src=SrcLoc(filename, line, col),
            fix=fix
        ))

    def ind_error(line:int, code:str, msg:str, fix:str|None=None):
        nonlocal ind_err_n
        ind_err_n += 1
        diagnostics.append(Diagnostic(
            idref=f"2🐛{ind_err_n}",
            code=code,
            severity="error",
            message_human=msg,
            src=SrcLoc(filename, line, 1),
            fix=fix
        ))

    for li, raw in enumerate(lines, start=1):
        line=raw

        # Tabs forbidden
        if "\t" in line:
            col=line.index("\t")+1
            lex_error(li, col, "HND-LEX-0002", "Tabs are forbidden. Use spaces only.", "Replace tabs with 4 spaces per indent level.")

        # Surrogate detection (defensive)
        for idx,ch in enumerate(line):
            if _is_surrogate(ch):
                lex_error(li, idx+1, "HND-LEX-0003", "Invalid Unicode surrogate code point in source.", "Ensure the file is valid UTF-8 text.")

        if line.strip()=="":
            tokens.append(Token(TK_NEWLINE,"\n",Span(filename,li,1,1)))
            continue

        m=re.match(r"[ ]*", line)
        indent=len(m.group(0))

        if indent % 4 != 0:
            ind_error(li, "HND-INDENT-0001", "Indentation must be a multiple of 4 spaces.", "Use 4 spaces per indent level.")

        if indent > indent_stack[-1]:
            if indent - indent_stack[-1] != 4:
                ind_error(li, "HND-INDENT-0002", f"Indentation jump too large: {indent_stack[-1]} -> {indent}.", "Increase indentation by exactly 4 spaces.")
            indent_stack.append(indent)
            tokens.append(Token(TK_INDENT,"",Span(filename,li,1,1)))
        elif indent < indent_stack[-1]:
            while indent_stack and indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append(Token(TK_DEDENT,"",Span(filename,li,1,1)))
            if indent != indent_stack[-1]:
                ind_error(li, "HND-INDENT-0003", f"Dedent does not match any previous indentation level: got {indent}.", "Match a previous indentation level (multiples of 4).")

        i=indent
        col=i+1

        while i < len(line):
            ch=line[i]

            if ch==" ":
                i+=1; col+=1; continue

            # Emoji token
            if ord(ch) > 127 and _is_emoji_start(ch):
                j=i+1
                while j < len(line) and ord(line[j]) > 127 and _is_emoji_continue(line[j]):
                    j+=1
                val=line[i:j]
                tokens.append(Token(TK_EMOJI, val, Span(filename, li, col, col+(j-i))))
                col += (j-i); i=j; continue

            # String
            sm=_re_string.match(line,i)
            if sm:
                s=sm.group(0)
                tokens.append(Token(TK_STRING, s, Span(filename, li, col, col+len(s))))
                i=sm.end()
                col=i+1
                continue

            # Identifier / keyword (ASCII or Unicode)
            im=_re_ident_uni.match(line,i) or _re_ident_ascii.match(line,i)
            if im:
                ident=im.group(0)
                kind=TK_KEYWORD if ident in KEYWORDS else TK_IDENT
                tokens.append(Token(kind, ident, Span(filename, li, col, col+len(ident))))
                i=im.end()
                col=i+1
                continue

            # Number
            nm=_re_number.match(line,i)
            if nm:
                n=nm.group(0)
                tokens.append(Token(TK_NUMBER, n, Span(filename, li, col, col+len(n))))
                i=nm.end()
                col=i+1
                continue

            # Two-character operators
            if i+1 < len(line) and line[i:i+2] in OPS:
                op=line[i:i+2]
                tokens.append(Token(TK_OP, op, Span(filename, li, col, col+2)))
                i+=2; col+=2; continue

            # One-character operators
            if ch in OPS:
                tokens.append(Token(TK_OP, ch, Span(filename, li, col, col+1)))
                i+=1; col+=1; continue

            # Punctuation
            if ch in SINGLE:
                tokens.append(Token(SINGLE[ch], ch, Span(filename, li, col, col+1)))
                i+=1; col+=1; continue

            # Other non-ASCII chars outside strings are forbidden (except emoji/ident handled above)
            if ord(ch) > 127:
                lex_error(li, col, "HND-LEX-0004", f"Non-ASCII character '{ch}' is not allowed here in HAND Core v0.1.", "Move it into a string literal, use an identifier, or replace it.")
                i+=1; col+=1; continue

            lex_error(li, col, "HND-LEX-0001", f"Unexpected character '{ch}'.", "Remove or replace the character.")
            i+=1; col+=1

        tokens.append(Token(TK_NEWLINE,"\n",Span(filename,li,len(line)+1,len(line)+1)))

    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token(TK_DEDENT,"",Span(filename,len(lines),1,1)))

    tokens.append(Token(TK_EOF,"",Span(filename,len(lines)+1,1,1)))
    return tokens, diagnostics
