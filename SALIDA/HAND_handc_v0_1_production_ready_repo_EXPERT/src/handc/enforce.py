from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .capabilities import CANON_CAPS, POLICY, caps_required_for_effects, normalize_caps

@dataclass(frozen=True)
class CapDiagnostic:
    idref: str
    code: str
    severity: str
    message_human: str
    remediation: str
    origin_ref: Optional[str]=None

class CapabilityError(Exception):
    def __init__(self, diag: CapDiagnostic):
        super().__init__(diag.message_human)
        self.diag=diag

class _ErrIds:
    def __init__(self): self.n=0
    def next(self)->str:
        self.n += 1
        return f"6🐛{self.n}"

def _origin_ref(node: Dict[str, Any]) -> Optional[str]:
    try:
        return node.get("origin", {}).get("ref")
    except Exception:
        return None

def _collect_required_caps_from_expr(expr: Optional[Dict[str, Any]]) -> Set[str]:
    if not expr or not isinstance(expr, dict):
        return {"compute"}
    k=expr.get("kind")
    req={"compute"}
    if k=="call":
        if expr.get("callee")=="ask":
            req.add("io.read")
        for a in expr.get("args",[]) or []:
            req |= _collect_required_caps_from_expr(a)
    elif k=="unary":
        req |= _collect_required_caps_from_expr(expr.get("expr"))
    elif k=="binary":
        req |= _collect_required_caps_from_expr(expr.get("left"))
        req |= _collect_required_caps_from_expr(expr.get("right"))
    return req

def _collect_required_caps_from_stmt(stmt: Dict[str, Any]) -> Set[str]:
    req={"compute"}
    req |= caps_required_for_effects(stmt.get("effects",[]) or [])
    req |= _collect_required_caps_from_expr(stmt.get("value"))
    req |= _collect_required_caps_from_expr(stmt.get("cond"))
    for x in stmt.get("then",[]) or []:
        req |= _collect_required_caps_from_stmt(x)
    for x in stmt.get("else",[]) or []:
        req |= _collect_required_caps_from_stmt(x)
    for x in stmt.get("body",[]) or []:
        req |= _collect_required_caps_from_stmt(x)
    return req

def required_caps_for_function(fn: Dict[str, Any]) -> Set[str]:
    req={"compute"}
    for st in fn.get("body",[]) or []:
        req |= _collect_required_caps_from_stmt(st)
    req |= caps_required_for_effects(fn.get("effects",[]) or [])
    return req

def required_caps_for_module(ir: Dict[str, Any]) -> Set[str]:
    req={"compute"}
    mod=ir["module"]
    for st in mod.get("toplevel",[]) or []:
        req |= _collect_required_caps_from_stmt(st)
    for fn in mod.get("functions",[]) or []:
        req |= required_caps_for_function(fn)
    return req

def enforce_capabilities(
    ir: Dict[str, Any],
    *,
    supervision_level: int,
    approvals: Optional[Set[str]]=None,
    scope: str="module",
) -> Tuple[Dict[str, Any], List[CapDiagnostic]]:
    if supervision_level not in POLICY:
        raise ValueError("supervision_level must be 1..4")
    approvals=set(approvals or set())
    pol=POLICY[supervision_level]
    ids=_ErrIds()
    diags: List[CapDiagnostic]=[]

    mod=ir.get("module",{})
    declared_mod=set(normalize_caps(mod.get("capabilities")))
    declared_mod.add("compute")

    def fail(code: str, msg: str, remediation: str, origin: Optional[str]):
        raise CapabilityError(CapDiagnostic(
            idref=ids.next(), code=code, severity="fatal",
            message_human=msg, remediation=remediation, origin_ref=origin
        ))

    for c in list(declared_mod):
        if c not in CANON_CAPS:
            fail(
                "HND-CAP-0001",
                f"Unknown capability '{c}' (no synonyms allowed).",
                f"Replace '{c}' with a canonical capability: {sorted(CANON_CAPS)}.",
                _origin_ref(mod) or _origin_ref(ir),
            )

    required_all=required_caps_for_module(ir)

    missing=sorted(required_all - declared_mod)
    if missing:
        fail(
            "HND-CAP-0201",
            f"Missing declared capabilities {missing}. Program requires them but module.capabilities does not permit them.",
            "Add the missing capabilities to module.capabilities (or remove the operations requiring them).",
            _origin_ref(mod) or _origin_ref(ir),
        )

    def check_cap(cap: str, origin: Optional[str]):
        if cap in pol.denied:
            fail(
                "HND-CAP-0101",
                f"Capability '{cap}' is denied at supervision level {supervision_level}.",
                "Increase supervision level or remove the operation requiring this capability.",
                origin,
            )
        if cap in pol.allowed_with_approval and cap not in approvals:
            fail(
                "HND-CAP-0102",
                f"Capability '{cap}' requires explicit human approval (🔴) at supervision level {supervision_level}.",
                f"Provide approval for '{cap}', or refactor to avoid requiring it.",
                origin,
            )

    for cap in sorted(required_all):
        check_cap(cap, _origin_ref(mod) or _origin_ref(ir))

    if scope == "function":
        for fn in mod.get("functions",[]) or []:
            declared_fn=set(normalize_caps(fn.get("capabilities")))
            declared_fn.add("compute")
            for c in list(declared_fn):
                if c not in CANON_CAPS:
                    fail(
                        "HND-CAP-0001",
                        f"Unknown capability '{c}' (no synonyms allowed).",
                        f"Replace '{c}' with a canonical capability: {sorted(CANON_CAPS)}.",
                        _origin_ref(fn),
                    )

            required_fn=required_caps_for_function(fn)
            missing_fn=sorted(required_fn - declared_fn)
            if missing_fn:
                fail(
                    "HND-CAP-0202",
                    f"Function '{fn.get('name')}' is missing declared capabilities {missing_fn}.",
                    "Add missing caps to function.capabilities or remove the operations requiring them.",
                    _origin_ref(fn),
                )
            for cap in sorted(required_fn):
                check_cap(cap, _origin_ref(fn))

    return ir, diags
