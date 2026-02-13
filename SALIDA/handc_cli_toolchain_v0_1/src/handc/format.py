from __future__ import annotations
from typing import List
from . import ast as A

IND=" " * 4

def format_hand(program: A.Program) -> str:
    out=[]
    for item in program.items:
        out.extend(_fmt_top(item, 0))
    # Ensure final newline
    if not out or not out[-1].endswith("\n"):
        out.append("\n")
    return "".join(out)

def _fmt_top(item: A.TopItem, level: int) -> List[str]:
    if isinstance(item, A.Section):
        return _fmt_section(item, level)
    return _fmt_stmt(item, level)

def _fmt_section(sec: A.Section, level: int) -> List[str]:
    pad=IND*level
    line = pad + f"{sec.emoji} {sec.header}".rstrip()
    if sec.has_colon:
        line += ":"
    lines=[line+"\n"]
    if sec.body is not None:
        for st in sec.body:
            lines.extend(_fmt_stmt(st, level+1))
    return lines

def _fmt_stmt(st: A.Stmt, level: int) -> List[str]:
    pad=IND*level
    if isinstance(st, A.FuncDef):
        params=", ".join(_fmt_param(p) for p in st.params)
        head=f"{pad}🔧 {st.name}({params})"
        if st.return_type is not None:
            head += f" -> {_fmt_type(st.return_type)}"
        head += ":\n"
        lines=[head]
        for s in st.body:
            lines.extend(_fmt_stmt(s, level+1))
        return lines
    if isinstance(st, A.IfStmt):
        lines=[f"{pad}if {_fmt_expr(st.cond)}:\n"]
        for s in st.then_body:
            lines.extend(_fmt_stmt(s, level+1))
        if st.else_body is not None:
            lines.append(f"{pad}else:\n")
            for s in st.else_body:
                lines.extend(_fmt_stmt(s, level+1))
        return lines
    if isinstance(st, A.WhileStmt):
        lines=[f"{pad}while {_fmt_expr(st.cond)}:\n"]
        for s in st.body:
            lines.extend(_fmt_stmt(s, level+1))
        return lines
    if isinstance(st, A.ReturnStmt):
        if st.value is None:
            return [f"{pad}return\n"]
        return [f"{pad}return {_fmt_expr(st.value)}\n"]
    if isinstance(st, A.ShowStmt):
        return [f"{pad}show {_fmt_expr(st.value)}\n"]
    if isinstance(st, A.VerifyStmt):
        return [f"{pad}🔍 {_fmt_expr(st.expr)}\n"]
    if isinstance(st, A.AssignStmt):
        line=f"{pad}{st.name}"
        if st.declared_type is not None:
            line += f": {_fmt_type(st.declared_type)}"
        line += f" = {_fmt_expr(st.value)}\n"
        return [line]
    if isinstance(st, A.ExprStmt):
        return [f"{pad}{_fmt_expr(st.expr)}\n"]
    raise TypeError(f"Unknown stmt: {st}")

def _fmt_param(p: A.Param) -> str:
    if p.type is None:
        return p.name
    return f"{p.name}: {_fmt_type(p.type)}"

def _fmt_type(t: A.TypeExpr) -> str:
    if isinstance(t, A.TypeName):
        return t.name
    if isinstance(t, A.TypeOptional):
        return _fmt_type(t.inner) + "?"
    if isinstance(t, A.TypeApp):
        args=", ".join(_fmt_type(a) for a in t.args)
        return f"{t.base.name}[{args}]"
    raise TypeError(f"Unknown TypeExpr: {t}")

def _fmt_expr(e: A.Expr) -> str:
    if isinstance(e, A.Literal):
        if e.kind=="Text":
            return str(e.value)
        if e.kind=="Bool":
            return "true" if e.value else "false"
        if e.kind=="Null":
            return "null"
        return str(e.value)
    if isinstance(e, A.Var):
        return e.name
    if isinstance(e, A.Unary):
        return f"{e.op}{_fmt_expr(e.expr)}"
    if isinstance(e, A.Binary):
        return f"{_fmt_expr(e.left)} {e.op} {_fmt_expr(e.right)}"
    if isinstance(e, A.Call):
        args=", ".join(_fmt_expr(a) for a in e.args)
        return f"{e.callee}({args})"
    if isinstance(e, A.Paren):
        return f"({_fmt_expr(e.expr)})"
    raise TypeError(f"Unknown expr: {e}")
