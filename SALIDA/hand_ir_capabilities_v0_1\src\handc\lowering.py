from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import ast as A

# ------------------------
# Origin (traceable)
# ------------------------

@dataclass(frozen=True)
class Origin:
    actor: str   # 👤 / ⭐ / 🤖
    ref: str     # [Origin][Emoji][ID].[SubID]
    note: Optional[str]=None

def _mk_origin(actor: str, emoji: str, node_id: str, sub: str, origin: str="AST") -> Dict[str, Any]:
    # Format: [Origen][Emoji][ID].[SubID]
    return {
        "actor": actor,
        "ref": f"[{origin}][{emoji}][{node_id}].{sub}"
    }

class _IdGen:
    def __init__(self):
        self.n=0
    def next(self) -> str:
        self.n += 1
        return f"N{self.n}"

# ------------------------
# Type lowering
# ------------------------

def lower_type(te: Optional[A.TypeExpr], ids: _IdGen, emoji: str="🏷️") -> Optional[Dict[str, Any]]:
    if te is None:
        return None
    if isinstance(te, A.TypeName):
        k=te.name
        if k in ("Int","Float","Bool","Text","Null","Any","Never"):
            return {"kind": k}
        # nominal record / user type
        return {"kind": "Record", "name": k, "args": []}

    if isinstance(te, A.TypeOptional):
        inner=lower_type(te.inner, ids, emoji=emoji) or {"kind":"Any"}
        return {"kind":"Optional", "args":[inner]}

    if isinstance(te, A.TypeApp):
        base=te.base.name
        args=[lower_type(a, ids, emoji=emoji) or {"kind":"Any"} for a in te.args]
        if base=="List":
            return {"kind":"List","args":args}
        if base=="Map":
            return {"kind":"Map","args":args}
        if base=="Result":
            return {"kind":"Result","args":args}
        if base=="Record":
            # Record[Name]
            if te.args and isinstance(te.args[0], A.TypeName):
                return {"kind":"Record","name":te.args[0].name,"args":[]}
            return {"kind":"Record","name":"Record","args":[]}
        # fallback
        return {"kind":"Record","name":base,"args":args}

    return {"kind":"Any"}

# ------------------------
# Expr lowering
# ------------------------

def lower_expr(e: A.Expr, ids: _IdGen) -> Dict[str, Any]:
    if isinstance(e, A.Literal):
        # preserve literal kind via "type" when available
        tmap={"Int":"Int","Float":"Float","Bool":"Bool","Text":"Text","Null":"Null"}
        tt=tmap.get(e.kind, None)
        out={"kind":"lit","value": e.value}
        if tt:
            out["type"]={"kind":tt}
        return out

    if isinstance(e, A.Var):
        return {"kind":"var","name": e.name}

    if isinstance(e, A.Paren):
        return lower_expr(e.expr, ids)

    if isinstance(e, A.Unary):
        return {"kind":"unary","op": e.op, "expr": lower_expr(e.expr, ids)}

    if isinstance(e, A.Binary):
        return {"kind":"binary","op": e.op, "left": lower_expr(e.left, ids), "right": lower_expr(e.right, ids)}

    if isinstance(e, A.Call):
        return {"kind":"call","callee": e.callee, "args":[lower_expr(a, ids) for a in e.args]}

    # unknown expression kinds -> deterministic null literal
    return {"kind":"lit","value": None, "type":{"kind":"Null"}}

# ------------------------
# Stmt lowering
# ------------------------

def lower_stmt(s: A.Stmt, ids: _IdGen) -> Dict[str, Any]:
    nid=ids.next()

    if isinstance(s, A.AssignStmt):
        return {
            "kind":"assign",
            "name": s.name,
            "declared_type": lower_type(s.declared_type, ids) if s.declared_type else None,
            "value": lower_expr(s.value, ids),
            "origin": _mk_origin("👤","📝",nid,"assign"),
            "effects": [],
            "capabilities": []
        }

    if isinstance(s, A.ExprStmt):
        return {
            "kind":"expr",
            "value": lower_expr(s.expr, ids),
            "origin": _mk_origin("👤","🧩",nid,"expr"),
            "effects": [],
            "capabilities": []
        }

    if isinstance(s, A.ShowStmt):
        return {
            "kind":"show",
            "value": lower_expr(s.value, ids),
            "origin": _mk_origin("👤","📤",nid,"show"),
            "effects": ["io.show"],
            "capabilities": ["io"]
        }

    if isinstance(s, A.VerifyStmt):
        return {
            "kind":"verify",
            "value": lower_expr(s.expr, ids),
            "origin": _mk_origin("👤","🔍",nid,"verify"),
            "effects": ["contract.verify"],
            "capabilities": []
        }

    if isinstance(s, A.IfStmt):
        return {
            "kind":"if",
            "cond": lower_expr(s.cond, ids),
            "then": [lower_stmt(x, ids) for x in s.then_body],
            "else": [lower_stmt(x, ids) for x in (s.else_body or [])],
            "origin": _mk_origin("👤","🧭",nid,"if"),
            "effects": [],
            "capabilities": []
        }

    if isinstance(s, A.WhileStmt):
        return {
            "kind":"while",
            "cond": lower_expr(s.cond, ids),
            "body": [lower_stmt(x, ids) for x in s.body],
            "origin": _mk_origin("👤","🔁",nid,"while"),
            "effects": [],
            "capabilities": []
        }

    if isinstance(s, A.ReturnStmt):
        return {
            "kind":"return",
            "value": lower_expr(s.value, ids) if s.value is not None else None,
            "origin": _mk_origin("👤","↩️",nid,"return"),
            "effects": ["control.return"],
            "capabilities": []
        }

    # fallback
    return {
        "kind":"expr",
        "value": {"kind":"lit","value": None, "type":{"kind":"Null"}},
        "origin": _mk_origin("👤","❓",nid,"unknown"),
        "effects": [],
        "capabilities": []
    }

# ------------------------
# Program lowering (AST -> IR)
# ------------------------

def lower_function(fn: A.FuncDef, ids: _IdGen) -> Dict[str, Any]:
    nid=ids.next()
    body=[lower_stmt(s, ids) for s in fn.body]
    effects=[]
    caps=[]
    # simple effect/capability discovery
    def walk_stmt(st):
        nonlocal effects, caps
        effects += st.get("effects", [])
        caps += st.get("capabilities", [])
        if st["kind"]=="if":
            for x in st.get("then",[]): walk_stmt(x)
            for x in st.get("else",[]): walk_stmt(x)
        if st["kind"]=="while":
            for x in st.get("body",[]): walk_stmt(x)
    for st in body:
        walk_stmt(st)
    effects=sorted(set(effects))
    caps=sorted(set(caps))

    params=[]
    for p in fn.params:
        pid=ids.next()
        params.append({
            "name": p.name,
            "type": lower_type(p.type, ids) if p.type else None,
            "origin": _mk_origin("👤","🏷️",pid,f"param_{p.name}")
        })

    return {
        "name": fn.name,
        "params": params,
        "ret_type": lower_type(fn.return_type, ids) if fn.return_type else None,
        "body": body,
        "contracts": [],
        "effects": effects,
        "capabilities": caps,
        "origin": _mk_origin("👤","🛠",nid,f"fn_{fn.name}")
    }

def lower_program(program: A.Program, module_name: str="main", semver: str="0.1.0") -> Dict[str, Any]:
    ids=_IdGen()
    top=[]
    fns=[]
    caps=set()
    for item in program.items:
        if isinstance(item, A.Section):
            # metadata-only; lower body statements if present
            if item.body:
                for st in item.body:
                    irs=lower_stmt(st, ids)
                    top.append(irs)
                    for c in irs.get("capabilities",[]): caps.add(c)
            continue
        if isinstance(item, A.FuncDef):
            f=lower_function(item, ids)
            fns.append(f)
            for c in f.get("capabilities",[]): caps.add(c)
            continue
        # top-level stmt
        if isinstance(item, (A.IfStmt, A.WhileStmt, A.ReturnStmt, A.ShowStmt, A.AssignStmt, A.ExprStmt, A.VerifyStmt)):
            irs=lower_stmt(item, ids)
            top.append(irs)
            for c in irs.get("capabilities",[]): caps.add(c)

    return {
        "ir_version":"0.1.0",
        "origin": _mk_origin("🤖","🧬","IR0","module", origin="Lowering"),
        "module": {
            "name": module_name,
            "semver": semver,
            "functions": fns,
            "toplevel": top,
            "types": [],
            "capabilities": sorted(caps)
        }
    }
