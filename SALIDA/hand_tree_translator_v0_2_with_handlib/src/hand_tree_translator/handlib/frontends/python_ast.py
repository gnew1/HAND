from __future__ import annotations

import ast
from typing import Dict, Any, List, Optional

from ..types import (
    SourceUnit, TranslationResult, Diagnostic, Severity,
    Program, Assign, If, While, ForRange, FuncDef, Return, ExprStmt,
    Name, Const, BinOp, Compare, Call, Expr, Stmt
)

# This frontend is intentionally strict: it only accepts a conservative subset.
# Extension strategy: implement more visitors or delegate to other Python-to-IR passes.

class Unsupported(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
        self.msg = msg

def _expr(node: ast.AST) -> Expr:
    if isinstance(node, ast.Name):
        return Name(node.id)
    if isinstance(node, ast.Constant):
        return Const(node.value)
    if isinstance(node, ast.BinOp):
        op = type(node.op).__name__
        return BinOp(op, _expr(node.left), _expr(node.right))
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        op = type(node.ops[0]).__name__
        return Compare(op, _expr(node.left), _expr(node.comparators[0]))
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            func = node.func.id
        else:
            raise Unsupported("Only simple function calls are supported (no attributes/methods).")
        return Call(func, [_expr(a) for a in node.args])
    raise Unsupported(f"Unsupported expression: {type(node).__name__}")

def _stmt(node: ast.stmt) -> Stmt:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return Assign(node.targets[0].id, _expr(node.value))
    if isinstance(node, ast.If):
        test = _expr(node.test)
        then = [_stmt(s) for s in node.body]
        otherwise = [_stmt(s) for s in node.orelse] if node.orelse else []
        return If(test, then, otherwise)
    if isinstance(node, ast.While):
        test = _expr(node.test)
        body = [_stmt(s) for s in node.body]
        return While(test, body)
    if isinstance(node, ast.For):
        # only range(...) for now
        if not isinstance(node.target, ast.Name):
            raise Unsupported("for target must be a simple name")
        if not (isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"):
            raise Unsupported("for loops supported only for range(...)")
        args = node.iter.args
        if len(args) == 1:
            start, stop, step = Const(0), _expr(args[0]), Const(1)
        elif len(args) == 2:
            start, stop, step = _expr(args[0]), _expr(args[1]), Const(1)
        elif len(args) == 3:
            start, stop, step = _expr(args[0]), _expr(args[1]), _expr(args[2])
        else:
            raise Unsupported("range() with 1..3 args supported")
        body = [_stmt(s) for s in node.body]
        return ForRange(node.target.id, start, stop, step, body)
    if isinstance(node, ast.FunctionDef):
        if node.decorator_list:
            raise Unsupported("decorators not supported in subset")
        params = [a.arg for a in node.args.args]
        body = [_stmt(s) for s in node.body]
        return FuncDef(node.name, params, body)
    if isinstance(node, ast.Return):
        return Return(_expr(node.value) if node.value else None)
    if isinstance(node, ast.Expr):
        return ExprStmt(_expr(node.value))
    raise Unsupported(f"Unsupported statement: {type(node).__name__}")

def translate_python(unit: SourceUnit, opts: Dict[str, Any]) -> TranslationResult:
    try:
        tree = ast.parse(unit.text)
        prog = Program([_stmt(s) for s in tree.body])
        return TranslationResult(ok=True, language="python", hand_ir=prog.__dict__)  # backend will accept node objects too
    except Unsupported as e:
        return TranslationResult(
            ok=False,
            language="python",
            diagnostics=[Diagnostic(Severity.ERROR, e.msg, code="PY_SUBSET_UNSUPPORTED")],
            passthrough_reason=e.msg
        )
    except SyntaxError as e:
        return TranslationResult(
            ok=False,
            language="python",
            diagnostics=[Diagnostic(Severity.ERROR, f"Python syntax error: {e}", span=(e.lineno or 0, e.offset or 0), code="PY_SYNTAX")],
            passthrough_reason="syntax_error"
        )
