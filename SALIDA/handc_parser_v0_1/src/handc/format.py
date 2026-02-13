from __future__ import annotations
from typing import List, Optional
from . import ast as A

IND=" " * 4

def format_hand(prog: A.Program) -> str:
    out: List[str] = []
    for item in prog.items:
        if isinstance(item, A.Section):
            out.extend(_fmt_section(item, 0))
        else:
            out.extend(_fmt_stmt(item, 0))
    # ensure trailing newline
    s="\n".join(out).rstrip() + "\n"
    return s

def _fmt_section(sec: A.Section, level: int) -> List[str]:
    prefix = IND*level
    line = prefix + sec.emoji
    if sec.header:
        line += " " + sec.header
    if sec.has_colon:
        line += ":"
    lines=[line]
    if sec.has_colon and sec.body is not None:
        if sec.body:
            for st in sec.body:
                lines.extend(_fmt_stmt(st, level+1))
        # empty block allowed: emit nothing
    return lines

def _fmt_stmt(st: A.Stmt, level: int) -> List[str]:
    p=IND*level
    if isinstance(st, A.FuncDef):
        head = p + "🔧 FUNCIÓN " + st.name + "(" + ", ".join(st.params) + "):"
        lines=[head]
        for s in st.body:
            lines.extend(_fmt_stmt(s, level+1))
        if not st.body:
            lines.append(IND*(level+1) + "return null")
        return lines
    if isinstance(st, A.IfStmt):
        lines=[p + "if " + _fmt_expr(st.cond) + ":"]
        for s in st.then_body:
            lines.extend(_fmt_stmt(s, level+1))
        if not st.then_body:
            lines.append(IND*(level+1) + "show null")
        if st.else_body is not None:
            lines.append(p + "else:")
            for s in st.else_body:
                lines.extend(_fmt_stmt(s, level+1))
            if not st.else_body:
                lines.append(IND*(level+1) + "show null")
        return lines
    if isinstance(st, A.WhileStmt):
        lines=[p + "while " + _fmt_expr(st.cond) + ":"]
        for s in st.body:
            lines.extend(_fmt_stmt(s, level+1))
        if not st.body:
            lines.append(IND*(level+1) + "show null")
        return lines
    if isinstance(st, A.ReturnStmt):
        if st.value is None:
            return [p + "return"]
        return [p + "return " + _fmt_expr(st.value)]
    if isinstance(st, A.ShowStmt):
        return [p + "show " + _fmt_expr(st.value)]
    if isinstance(st, A.AssignStmt):
        return [p + f"{st.name} = {_fmt_expr(st.value)}"]
    if isinstance(st, A.ExprStmt):
        return [p + _fmt_expr(st.expr)]
    raise TypeError(f"Unknown stmt: {st}")

def _fmt_expr(e: A.Expr) -> str:
    if isinstance(e, A.Literal):
        if e.kind == "Text":
            # escape backslash and quotes, keep \n etc
            s = str(e.value)
            s = s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n")
            return f"\"{s}\""
        if e.kind == "Bool":
            return "true" if bool(e.value) else "false"
        if e.kind == "Null":
            return "null"
        if e.kind in ("Int","Float"):
            return str(e.value)
        return "null"
    if isinstance(e, A.Var):
        return e.name
    if isinstance(e, A.Unary):
        return f"{e.op}{_fmt_expr(e.expr)}"
    if isinstance(e, A.Binary):
        return f"{_fmt_expr(e.left)} {e.op} {_fmt_expr(e.right)}"
    if isinstance(e, A.Call):
        return f"{e.fn}(" + ", ".join(_fmt_expr(a) for a in e.args) + ")"
    if isinstance(e, A.Paren):
        return "(" + _fmt_expr(e.expr) + ")"
    raise TypeError(f"Unknown expr: {e}")
