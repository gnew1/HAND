from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Union

# ---- Program ----

@dataclass(frozen=True)
class Program:
    items: List['TopItem']

TopItem = Union['Section', 'Stmt']

# ---- Sections ----

@dataclass(frozen=True)
class Section:
    emoji: str
    header: str          # textual header after emoji (joined tokens)
    has_colon: bool      # whether line ended with ':'
    body: Optional[List['Stmt']]  # for block sections like ▶️ INICIAR:

# ---- Type expressions (syntax-level) ----

TypeExpr = Union['TypeName','TypeApp','TypeOptional']

@dataclass(frozen=True)
class TypeName:
    name: str            # e.g., Int, Text, User

@dataclass(frozen=True)
class TypeApp:
    base: TypeName       # List, Map, Result
    args: List[TypeExpr] # generic args

@dataclass(frozen=True)
class TypeOptional:
    inner: TypeExpr

@dataclass(frozen=True)
class Param:
    name: str
    type: Optional[TypeExpr] = None

# ---- Statements ----

Stmt = Union[
    'FuncDef','IfStmt','WhileStmt','ReturnStmt','ShowStmt','AssignStmt','ExprStmt','VerifyStmt'
]

@dataclass(frozen=True)
class FuncDef:
    name: str
    params: List[Param]
    return_type: Optional[TypeExpr]
    body: List[Stmt]

@dataclass(frozen=True)
class IfStmt:
    cond: 'Expr'
    then_body: List[Stmt]
    else_body: Optional[List[Stmt]]

@dataclass(frozen=True)
class WhileStmt:
    cond: 'Expr'
    body: List[Stmt]

@dataclass(frozen=True)
class ReturnStmt:
    value: Optional['Expr']

@dataclass(frozen=True)
class ShowStmt:
    value: 'Expr'

@dataclass(frozen=True)
class AssignStmt:
    name: str
    declared_type: Optional[TypeExpr]
    value: 'Expr'

@dataclass(frozen=True)
class VerifyStmt:
    expr: 'Expr'   # usually x != null; typechecker may refine

@dataclass(frozen=True)
class ExprStmt:
    expr: 'Expr'

# ---- Expressions ----

Expr = Union['Literal','Var','Binary','Unary','Call','Paren']

@dataclass(frozen=True)
class Literal:
    kind: str  # "Int"|"Float"|"Bool"|"Null"|"Text"
    value: object

@dataclass(frozen=True)
class Var:
    name: str

@dataclass(frozen=True)
class Unary:
    op: str
    expr: Expr

@dataclass(frozen=True)
class Binary:
    left: Expr
    op: str
    right: Expr

@dataclass(frozen=True)
class Call:
    callee: str
    args: List[Expr]

@dataclass(frozen=True)
class Paren:
    expr: Expr
