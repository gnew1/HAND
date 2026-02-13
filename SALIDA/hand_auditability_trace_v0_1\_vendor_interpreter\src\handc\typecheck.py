from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .diagnostics import Diagnostic, SrcLoc
from . import ast as A
from . import types as T

# ------------------- Typing environment Γ -------------------

@dataclass
class Binding:
    typ: T.Type
    proven_non_null: bool = False  # flow refinement

class Env:
    def __init__(self):
        self.frames: List[Dict[str, Binding]] = [{}]

    def push(self):
        self.frames.append({})

    def pop(self):
        self.frames.pop()

    def get(self, name: str) -> Optional[Binding]:
        for fr in reversed(self.frames):
            if name in fr:
                return fr[name]
        return None

    def set(self, name: str, typ: T.Type):
        self.frames[-1][name] = Binding(typ, proven_non_null=False)

    def refine_non_null(self, name: str):
        b=self.get(name)
        if b is None:
            return
        b.proven_non_null=True

    def current_type(self, name: str) -> Optional[T.Type]:
        b=self.get(name)
        if b is None:
            return None
        if b.proven_non_null and isinstance(b.typ, T.OptionalT):
            return b.typ.inner
        return b.typ

# ------------------- Typechecker -------------------

class TypeChecker:
    def __init__(self, filename: str="<input>"):
        self.filename=filename
        self.diags: List[Diagnostic]=[]
        self.err_n=0
        self.env=Env()
        self.current_return: Optional[T.Type]=None

    def error(self, code: str, msg: str, line: int, col: int, fix: str|None=None):
        self.err_n += 1
        self.diags.append(Diagnostic(
            idref=f"4🐛{self.err_n}",
            code=code,
            severity="error",
            message_human=msg,
            src=SrcLoc(self.filename, line, col),
            fix=fix
        ))

    # ---- Spec-mapped rules Γ ⊢ e : T ----

    def type_of_expr(self, e: A.Expr) -> T.Type:
        if isinstance(e, A.Literal):
            if e.kind=="Int":
                return T.INT
            if e.kind=="Float":
                return T.FLOAT
            if e.kind=="Bool":
                return T.BOOL
            if e.kind=="Text":
                return T.TEXT
            if e.kind=="Null":
                return T.NULL
            return T.ANY

        if isinstance(e, A.Var):
            b=self.env.get(e.name)
            if b is None:
                self.error("HND-TC-0101", f"Undefined variable '{e.name}'.", 1, 1, f"Declare '{e.name}' before use (assign or add parameter type).")
                return T.ANY
            t=self.env.current_type(e.name)
            assert t is not None
            return t

        if isinstance(e, A.Paren):
            return self.type_of_expr(e.expr)

        if isinstance(e, A.Unary):
            t=self.type_of_expr(e.expr)
            if e.op=="-":
                if t==T.INT or t==T.FLOAT:
                    return t
                self.error("HND-TC-0201", f"Unary '-' requires Int or Float, got {t}.", 1, 1, "Ensure the expression is numeric (Int/Float).")
                return T.ANY
            self.error("HND-TC-0200", f"Unknown unary operator '{e.op}'.", 1, 1)
            return T.ANY

        if isinstance(e, A.Binary):
            lt=self.type_of_expr(e.left)
            rt=self.type_of_expr(e.right)

            if e.op in ("+","-","*","/","%"):
                # Numeric ops
                if lt in (T.INT, T.FLOAT) and rt in (T.INT, T.FLOAT):
                    if lt==T.FLOAT or rt==T.FLOAT or e.op=="/":
                        return T.FLOAT
                    return T.INT
                # Text concatenation for +
                if e.op=="+" and lt==T.TEXT and rt==T.TEXT:
                    return T.TEXT
                self.error("HND-TC-0202", f"Operator '{e.op}' not defined for {lt} and {rt}.", 1, 1, "Use numeric types for arithmetic, or Text + Text for concatenation.")
                return T.ANY

            if e.op in ("==","!="):
                # allow compare any (but warn? v0.1 only error on Optional w/out verify? keep permissive)
                # If comparing Optional[T] with Null: ok
                return T.BOOL

            if e.op in ("<","<=",">",">="):
                if lt in (T.INT, T.FLOAT) and rt in (T.INT, T.FLOAT):
                    return T.BOOL
                self.error("HND-TC-0203", f"Comparison '{e.op}' requires numeric operands, got {lt} and {rt}.", 1, 1)
                return T.BOOL

            self.error("HND-TC-0200", f"Unknown binary operator '{e.op}'.", 1, 1)
            return T.ANY

        if isinstance(e, A.Call):
            # v0.1: only builtin functions
            if e.callee=="len":
                if len(e.args)!=1:
                    self.error("HND-TC-0301", "len() expects exactly 1 argument.", 1, 1, "Call len(x).")
                    return T.INT
                # accept Any for now
                _=self.type_of_expr(e.args[0])
                return T.INT
            if e.callee=="ok":
                # ok(x) -> Result[T, Text]
                if len(e.args)!=1:
                    self.error("HND-TC-0302", "ok() expects exactly 1 argument.", 1, 1, "Call ok(value).")
                    return T.ANY
                ot=self.type_of_expr(e.args[0])
                return T.ResultT(ot, T.TEXT)
            if e.callee=="err":
                if len(e.args)!=1:
                    self.error("HND-TC-0303", "err() expects exactly 1 argument.", 1, 1)
                    return T.ANY
                et=self.type_of_expr(e.args[0])
                return T.ResultT(T.ANY, et)
            # unknown call: treat as Any, but if variable bound to function not supported yet
            self.error("HND-TC-0300", f"Unknown function '{e.callee}' in v0.1.", 1, 1, "Define the function with 🔧 or use a supported builtin.")
            for a in e.args:
                self.type_of_expr(a)
            return T.ANY

        return T.ANY

    # ---- TypeExpr (syntax) -> Type (semantic) ----
    def lower_typeexpr(self, te: A.TypeExpr) -> T.Type:
        if isinstance(te, A.TypeName):
            n=te.name
            if n=="Int": return T.INT
            if n=="Float": return T.FLOAT
            if n=="Bool": return T.BOOL
            if n=="Text": return T.TEXT
            if n=="Null": return T.NULL
            if n=="Any": return T.ANY
            if n=="Never": return T.NEVER
            return T.RecordT(n)

        if isinstance(te, A.TypeOptional):
            return T.OptionalT(self.lower_typeexpr(te.inner))

        if isinstance(te, A.TypeApp):
            base=te.base.name
            args=[self.lower_typeexpr(a) for a in te.args]

            def bad_arity(expected: str):
                self.error(
                    "HND-TC-1001",
                    f"Type '{base}' expects {expected}, got {len(args)} argument(s).",
                    1, 1,
                    f"Use {base}[{expected}] with the correct number of type arguments."
                )

            if base=="List":
                if len(args)!=1:
                    bad_arity("T")
                    return T.ANY
                return T.ListT(args[0])

            if base=="Map":
                if len(args)!=2:
                    bad_arity("K,V")
                    return T.ANY
                return T.MapT(args[0], args[1])

            if base=="Result":
                if len(args)!=2:
                    bad_arity("T,E")
                    return T.ANY
                return T.ResultT(args[0], args[1])

            if base=="Record":
                if len(args)!=1:
                    bad_arity("Name")
                    return T.ANY
                if isinstance(te.args[0], A.TypeName):
                    return T.RecordT(te.args[0].name)
                return T.ANY

            return T.ANY

        return T.ANY

# ---- Statements ----
    def check_stmt(self, st: A.Stmt):
        if isinstance(st, A.AssignStmt):
            rhs=self.type_of_expr(st.value)
            if st.declared_type is not None:
                dt=self.lower_typeexpr(st.declared_type)
                if not T.assignable(rhs, dt):
                    self.error("HND-TC-1101", f"Cannot assign {rhs} to '{st.name}' of type {dt}.", 1, 1,
                               f"Change the declared type of '{st.name}' or convert the value to {dt}.")
                self.env.set(st.name, dt)
            else:
                # infer: if assigning null to something already declared Optional, keep Optional
                prev=self.env.get(st.name)
                if prev is not None and isinstance(prev.typ, T.OptionalT) and rhs==T.NULL:
                    self.env.set(st.name, prev.typ)
                else:
                    self.env.set(st.name, rhs)
            return

        if isinstance(st, A.ShowStmt):
            _=self.type_of_expr(st.value)
            return

        if isinstance(st, A.ExprStmt):
            _=self.type_of_expr(st.expr)
            return

        if isinstance(st, A.VerifyStmt):
            # only pattern recognized: (Var != null)
            expr=st.expr
            if isinstance(expr, A.Binary) and expr.op=="!=" and isinstance(expr.left, A.Var) and isinstance(expr.right, A.Literal) and expr.right.kind=="Null":
                name=expr.left.name
                bt=self.env.get(name)
                if bt is None:
                    self.error("HND-TC-1201", f"VERIFY references undefined variable '{name}'.", 1, 1, f"Declare '{name}' before VERIFY.")
                    return
                if not isinstance(bt.typ, T.OptionalT):
                    # verifying non-optional is redundant but ok
                    return
                self.env.refine_non_null(name)
                return
            # keyword verify x : treat as non-null check only if x is optional
            if isinstance(expr, A.Var):
                name=expr.name
                bt=self.env.get(name)
                if bt and isinstance(bt.typ, T.OptionalT):
                    self.env.refine_non_null(name)
                    return
            # otherwise, VERIFY is allowed but doesn't refine
            _=self.type_of_expr(expr)
            return

        if isinstance(st, A.ReturnStmt):
            if self.current_return is None:
                # return at top-level is allowed but type is Any
                if st.value is not None:
                    _=self.type_of_expr(st.value)
                return
            if st.value is None:
                # returning null: only ok if return type optional or Null
                if not (self.current_return==T.NULL or isinstance(self.current_return, T.OptionalT)):
                    self.error("HND-TC-1301", f"Return type is {self.current_return}, but 'return' has no value.", 1, 1,
                               f"Return a value of type {self.current_return}, or declare return type as Optional ({self.current_return}?).")
                return
            rt=self.type_of_expr(st.value)
            if not T.assignable(rt, self.current_return):
                self.error("HND-TC-1302", f"Return type mismatch: expected {self.current_return}, got {rt}.", 1, 1,
                           f"Return a {self.current_return}, or change function return type.")
            return

        if isinstance(st, A.IfStmt):
            ct=self.type_of_expr(st.cond)
            if ct != T.BOOL and not isinstance(ct, T.AnyT):
                self.error("HND-TC-1401", f"If condition must be Bool, got {ct}.", 1, 1, "Use a boolean expression in if condition.")
            # flow: check then/else in separate scopes, then merge bindings conservatively
            before=self._snapshot_env()
            then_env=self._check_block_with_env(st.then_body, before)
            else_env=before
            if st.else_body is not None:
                else_env=self._check_block_with_env(st.else_body, before)
            self._merge_env(before, then_env, else_env)
            return

        if isinstance(st, A.WhileStmt):
            ct=self.type_of_expr(st.cond)
            if ct != T.BOOL and not isinstance(ct, T.AnyT):
                self.error("HND-TC-1501", f"While condition must be Bool, got {ct}.", 1, 1)
            # conservative: check body but do not assume it runs
            before=self._snapshot_env()
            _=self._check_block_with_env(st.body, before)
            self._restore_env(before)
            return

        if isinstance(st, A.FuncDef):
            # bind function name in env as Any (call typing not supported yet)
            # enter scope with params
            old_return=self.current_return
            self.env.push()
            for p in st.params:
                if p.type is None:
                    self.env.set(p.name, T.ANY)
                else:
                    self.env.set(p.name, self.lower_typeexpr(p.type))
            self.current_return = self.lower_typeexpr(st.return_type) if st.return_type else None
            for s in st.body:
                self.check_stmt(s)
            self.current_return = old_return
            self.env.pop()
            return

    def _snapshot_env(self) -> List[Dict[str, Binding]]:
        # deep copy frames and bindings (bindings are mutable due to refinement)
        snap=[]
        for fr in self.env.frames:
            snap.append({k: Binding(v.typ, v.proven_non_null) for k,v in fr.items()})
        return snap

    def _restore_env(self, snap: List[Dict[str, Binding]]):
        self.env.frames = [{k: Binding(v.typ, v.proven_non_null) for k,v in fr.items()} for fr in snap]

    def _check_block_with_env(self, block: List[A.Stmt], snap: List[Dict[str, Binding]]) -> List[Dict[str, Binding]]:
        self._restore_env(snap)
        self.env.push()
        for s in block:
            self.check_stmt(s)
        # capture resulting env (including outer + inner). Pop inner scope first, but keep changes to outer? v0.1 simple: flatten
        # We'll merge inner frame into outer frame on exit.
        inner=self.env.frames.pop()
        outer=self.env.frames[-1]
        outer.update(inner)
        result=self._snapshot_env()
        return result

    def _merge_env(self, before: List[Dict[str, Binding]], then_env: List[Dict[str, Binding]], else_env: List[Dict[str, Binding]]):
        # merge only top frame variables (global for v0.1)
        merged={}
        # collect union of names
        names=set()
        for fr in then_env:
            names |= set(fr.keys())
        for fr in else_env:
            names |= set(fr.keys())
        for name in names:
            t_then=self._lookup_in_snap(then_env, name)
            t_else=self._lookup_in_snap(else_env, name)
            if t_then is None:
                t=t_else.typ
            elif t_else is None:
                t=t_then.typ
            else:
                t=T.join(t_then.typ, t_else.typ)
            merged[name]=Binding(t, False)
        # restore base env and apply merged to last frame
        self._restore_env(before)
        self.env.frames[-1].update(merged)

    def _lookup_in_snap(self, snap: List[Dict[str, Binding]], name: str) -> Optional[Binding]:
        for fr in reversed(snap):
            if name in fr:
                return fr[name]
        return None

def typecheck(program: A.Program, filename: str="<input>") -> List[Diagnostic]:
    tc=TypeChecker(filename)
    for item in program.items:
        if isinstance(item, A.Section):
            # typecheck section body only
            if item.body:
                tc.env.push()
                for st in item.body:
                    tc.check_stmt(st)
                tc.env.pop()
        else:
            tc.check_stmt(item)
    return tc.diags
