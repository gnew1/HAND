from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class Diagnostic:
    severity: Severity
    message: str
    span: Optional[Tuple[int,int]] = None  # (lineno, col) best-effort
    code: Optional[str] = None            # machine-readable id

@dataclass
class SourceUnit:
    """One input file."""
    path: str
    language: str
    text: str

@dataclass
class TranslationResult:
    ok: bool
    language: str
    hand_text: Optional[str] = None
    hand_ir: Optional[Dict[str, Any]] = None
    diagnostics: List[Diagnostic] = field(default_factory=list)
    passthrough_reason: Optional[str] = None  # why it went to no_traducible

# -------------------------
# Minimal, stable HAND-IR v0
# -------------------------
# This IR is designed for progressive enrichment: you can add node types,
# extra fields, emojis, and type annotations without breaking old emitters.

@dataclass
class Node:
    kind: str
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Program(Node):
    body: List['Stmt'] = field(default_factory=list)

    def __init__(self, body: Optional[List['Stmt']] = None, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Program", meta=meta or {})
        self.body = body or []

# Statements
@dataclass
class Stmt(Node): ...

@dataclass
class Assign(Stmt):
    target: str = ""
    value: 'Expr' = None  # type: ignore

    def __init__(self, target: str, value: 'Expr', meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Assign", meta=meta or {})
        self.target = target
        self.value = value

@dataclass
class If(Stmt):
    test: 'Expr' = None  # type: ignore
    then: List['Stmt'] = field(default_factory=list)
    otherwise: List['Stmt'] = field(default_factory=list)

    def __init__(self, test: 'Expr', then: List['Stmt'], otherwise: Optional[List['Stmt']] = None, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="If", meta=meta or {})
        self.test = test
        self.then = then
        self.otherwise = otherwise or []

@dataclass
class While(Stmt):
    test: 'Expr' = None  # type: ignore
    body: List['Stmt'] = field(default_factory=list)

    def __init__(self, test: 'Expr', body: List['Stmt'], meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="While", meta=meta or {})
        self.test = test
        self.body = body

@dataclass
class ForRange(Stmt):
    var: str = ""
    start: 'Expr' = None  # type: ignore
    stop: 'Expr' = None   # type: ignore
    step: 'Expr' = None   # type: ignore
    body: List['Stmt'] = field(default_factory=list)

    def __init__(self, var: str, start: 'Expr', stop: 'Expr', step: 'Expr', body: List['Stmt'], meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="ForRange", meta=meta or {})
        self.var = var
        self.start = start
        self.stop = stop
        self.step = step
        self.body = body

@dataclass
class FuncDef(Stmt):
    name: str = ""
    params: List[str] = field(default_factory=list)
    body: List['Stmt'] = field(default_factory=list)

    def __init__(self, name: str, params: List[str], body: List['Stmt'], meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="FuncDef", meta=meta or {})
        self.name = name
        self.params = params
        self.body = body

@dataclass
class Return(Stmt):
    value: Optional['Expr'] = None

    def __init__(self, value: Optional['Expr'] = None, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Return", meta=meta or {})
        self.value = value

@dataclass
class ExprStmt(Stmt):
    expr: 'Expr' = None  # type: ignore

    def __init__(self, expr: 'Expr', meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="ExprStmt", meta=meta or {})
        self.expr = expr

# Expressions
@dataclass
class Expr(Node): ...

@dataclass
class Name(Expr):
    id: str = ""
    def __init__(self, id: str, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Name", meta=meta or {})
        self.id = id

@dataclass
class Const(Expr):
    value: Any = None
    def __init__(self, value: Any, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Const", meta=meta or {})
        self.value = value

@dataclass
class BinOp(Expr):
    op: str = ""
    left: Expr = None  # type: ignore
    right: Expr = None # type: ignore

    def __init__(self, op: str, left: Expr, right: Expr, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="BinOp", meta=meta or {})
        self.op = op
        self.left = left
        self.right = right

@dataclass
class Compare(Expr):
    op: str = ""
    left: Expr = None  # type: ignore
    right: Expr = None # type: ignore

    def __init__(self, op: str, left: Expr, right: Expr, meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Compare", meta=meta or {})
        self.op = op
        self.left = left
        self.right = right

@dataclass
class Call(Expr):
    func: str = ""
    args: List[Expr] = field(default_factory=list)

    def __init__(self, func: str, args: List[Expr], meta: Optional[Dict[str,Any]] = None):
        super().__init__(kind="Call", meta=meta or {})
        self.func = func
        self.args = args
