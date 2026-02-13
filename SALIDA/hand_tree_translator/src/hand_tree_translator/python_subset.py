"""
Python -> Simple HAND translator (conservative subset).

If we see an AST node we don't support in `safe` mode, we raise UnsupportedConstruct
so the caller can quarantine the file.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .hand_format import hand_header


class UnsupportedConstruct(Exception):
    pass


def _op_to_str(op: ast.AST) -> str:
    table = {
        ast.Add: "+",
        ast.Sub: "-",
        ast.Mult: "*",
        ast.Div: "/",
        ast.Mod: "%",
        ast.Pow: "**",
        ast.BitAnd: "&",
        ast.BitOr: "|",
        ast.BitXor: "^",
        ast.And: "and",
        ast.Or: "or",
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Is: "is",
        ast.IsNot: "is_not",
        ast.In: "in",
        ast.NotIn: "not_in",
    }
    for k, v in table.items():
        if isinstance(op, k):
            return v
    raise UnsupportedConstruct(f"Unsupported operator: {type(op).__name__}")


def _expr(e: ast.AST) -> str:
    if isinstance(e, ast.Constant):
        if isinstance(e.value, str):
            return f'"{e.value}"'
        return str(e.value)
    if isinstance(e, ast.Name):
        return e.id
    if isinstance(e, ast.BinOp):
        return f"{_expr(e.left)} {_op_to_str(e.op)} {_expr(e.right)}"
    if isinstance(e, ast.UnaryOp):
        if isinstance(e.op, ast.USub):
            return f"-{_expr(e.operand)}"
        if isinstance(e.op, ast.Not):
            return f"not {_expr(e.operand)}"
        raise UnsupportedConstruct(f"Unsupported unary op: {type(e.op).__name__}")
    if isinstance(e, ast.Compare):
        if len(e.ops) != 1 or len(e.comparators) != 1:
            raise UnsupportedConstruct("Chained comparisons not supported in safe mode.")
        return f"{_expr(e.left)} {_op_to_str(e.ops[0])} {_expr(e.comparators[0])}"
    if isinstance(e, ast.Call):
        # Special-case print(...) -> show ...
        if isinstance(e.func, ast.Name) and e.func.id == "print":
            args = ", ".join(_expr(a) for a in e.args)
            return f"show {args}"
        # Generic call
        func = _expr(e.func) if not isinstance(e.func, ast.Attribute) else f"{_expr(e.func.value)}.{e.func.attr}"
        args = ", ".join(_expr(a) for a in e.args)
        return f"call {func}({args})"
    if isinstance(e, ast.Attribute):
        return f"{_expr(e.value)}.{e.attr}"
    if isinstance(e, ast.Subscript):
        return f"{_expr(e.value)}[{_expr(e.slice)}]"
    if isinstance(e, ast.List):
        return "[" + ", ".join(_expr(elt) for elt in e.elts) + "]"
    if isinstance(e, ast.Dict):
        items = []
        for k, v in zip(e.keys, e.values):
            items.append(f"{_expr(k)}: {_expr(v)}")
        return "{" + ", ".join(items) + "}"
    raise UnsupportedConstruct(f"Unsupported expression: {type(e).__name__}")


def _stmt(s: ast.stmt, indent: int) -> List[str]:
    sp = " " * (4 * indent)
    if isinstance(s, ast.Assign):
        if len(s.targets) != 1:
            raise UnsupportedConstruct("Multiple assignment targets not supported.")
        t = s.targets[0]
        if not isinstance(t, ast.Name):
            raise UnsupportedConstruct("Only name assignments supported.")
        return [f"{sp}{t.id} = {_expr(s.value)}"]
    if isinstance(s, ast.AnnAssign):
        if not isinstance(s.target, ast.Name):
            raise UnsupportedConstruct("Only name annotated assignments supported.")
        if s.value is None:
            raise UnsupportedConstruct("Annotated assign without value not supported.")
        return [f"{sp}{s.target.id}: {_expr(s.annotation)} = {_expr(s.value)}"]
    if isinstance(s, ast.Expr):
        # Expression statement: could be print, call...
        line = _expr(s.value)
        return [f"{sp}{line}"]
    if isinstance(s, ast.Return):
        if s.value is None:
            return [f"{sp}return"]
        return [f"{sp}return {_expr(s.value)}"]
    if isinstance(s, ast.If):
        out = [f"{sp}if {_expr(s.test)}:"]
        for b in s.body:
            out += _stmt(b, indent + 1)
        if s.orelse:
            out.append(f"{sp}else:")
            for b in s.orelse:
                out += _stmt(b, indent + 1)
        return out
    if isinstance(s, ast.While):
        out = [f"{sp}while {_expr(s.test)}:"]
        for b in s.body:
            out += _stmt(b, indent + 1)
        return out
    if isinstance(s, ast.For):
        if not isinstance(s.target, ast.Name):
            raise UnsupportedConstruct("Only for-name targets supported.")
        out = [f"{sp}for {s.target.id} in {_expr(s.iter)}:"]
        for b in s.body:
            out += _stmt(b, indent + 1)
        return out
    if isinstance(s, ast.FunctionDef):
        args = ", ".join(a.arg for a in s.args.args)
        out = [f"{sp}🔧 FUNCIÓN {s.name}({args}):"]
        # Note: body is indented under function
        for b in s.body:
            out += _stmt(b, indent + 1)
        return out
    raise UnsupportedConstruct(f"Unsupported statement: {type(s).__name__}")


def python_to_simple_hand(source: str, program_name: str, source_path: str) -> str:
    tree = ast.parse(source)
    lines: List[str] = []
    lines += hand_header(program_name=program_name, source_path=source_path, lang="python")

    # Entry point section: we translate top-level statements under ▶️ INICIAR,
    # but hoist function defs as separate top-level blocks (still valid in HAND style).
    funcs: List[ast.FunctionDef] = []
    main: List[ast.stmt] = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            funcs.append(n)
        else:
            main.append(n)

    # Functions
    for fn in funcs:
        lines += _stmt(fn, indent=0)
        lines.append("")

    # Main
    lines.append("▶️ INICIAR:")
    for st in main:
        lines += _stmt(st, indent=1)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
