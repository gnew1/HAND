from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

@dataclass(frozen=True)
class WasmNote:
    kind: str   # "ERROR" | "WARN" | "INFO"
    code: str
    message: str
    origin_ref: Optional[str]=None

class WasmGenError(Exception):
    def __init__(self, note: WasmNote):
        super().__init__(note.message)
        self.note = note

def _origin_ref(node: Dict[str, Any]) -> Optional[str]:
    try:
        return node.get("origin", {}).get("ref")
    except Exception:
        return None

def _ir_type_kind(t: Optional[Dict[str, Any]]) -> Optional[str]:
    if not t:
        return None
    return t.get("kind")

def _ensure_i32_type(t: Optional[Dict[str, Any]], *, origin: Optional[str]) -> None:
    k = _ir_type_kind(t)
    if k in (None, "Int", "Bool"):
        return
    raise WasmGenError(WasmNote(
        kind="ERROR", code="WASM-0300",
        message=f"WASM v0.1 supports only Int/Bool (i32). Got type: {k}",
        origin_ref=origin,
    ))

def _require_pure_subset(ir: Dict[str, Any]) -> None:
    mod = ir["module"]
    if (mod.get("toplevel") or []):
        raise WasmGenError(WasmNote(
            kind="ERROR", code="WASM-0100",
            message="WASM v0.1 supports only functions (no top-level statements).",
            origin_ref=_origin_ref((mod.get('toplevel') or [])[0]),
        ))
    for fn in (mod.get("functions") or []):
        for st in (fn.get("body") or []):
            eff = st.get("effects") or []
            # For v0.1: strictly forbid io.* and anything beyond compute
            for e in eff:
                if e not in ("contract.verify", "control.return"):
                    raise WasmGenError(WasmNote(
                        kind="ERROR", code="WASM-0200",
                        message=f"WASM v0.1 forbids effect '{e}' (pure subset).",
                        origin_ref=_origin_ref(st),
                    ))
            if st.get("kind") in ("show", "verify"):
                raise WasmGenError(WasmNote(
                    kind="ERROR", code="WASM-0201",
                    message="WASM v0.1 forbids IO/VERIFY in pure subset (no host bindings in this backend).",
                    origin_ref=_origin_ref(st),
                ))

class _FnCtx:
    def __init__(self, params: List[str]):
        self.locals: List[str] = []
        self.var_to_local: Dict[str, str] = {}
        for p in params:
            self.var_to_local[p] = f"${p}"

    def ensure_local(self, name: str) -> str:
        if name in self.var_to_local:
            return self.var_to_local[name]
        sym = f"${name}"
        self.locals.append(sym)
        self.var_to_local[name] = sym
        return sym

def gen_wat(ir: Dict[str, Any]) -> Tuple[str, List[WasmNote]]:
    """Generate WAT for WASM v0.1 (pure subset).
    Returns: (wat_text, notes). If a hard limitation is hit, raises WasmGenError.
    """
    if ir.get("ir_version") != "0.1.0":
        raise ValueError("Unsupported IR version")
    _require_pure_subset(ir)

    notes: List[WasmNote] = []
    mod = ir["module"]
    fn_names = [fn["name"] for fn in (mod.get("functions") or [])]

    lines: List[str] = []
    emit = lines.append
    emit("(module")
    emit('  (memory (export "memory") 1) ;; reserved (unused in pure subset)')
    emit("")

    def emit_expr(ctx: _FnCtx, expr: Dict[str, Any]) -> List[str]:
        k = expr["kind"]
        out: List[str] = []
        if k == "lit":
            ty = expr.get("type") or {}
            _ensure_i32_type(ty, origin=_origin_ref(expr))
            v = expr.get("value")
            if isinstance(v, str):
                s = v.strip().lower()
                if s == "true":
                    v = 1
                elif s == "false":
                    v = 0
                else:
                    v = int(s, 10)
            if v is None:
                raise WasmGenError(WasmNote("ERROR","WASM-0301","Null literal not supported.", _origin_ref(expr)))
            out.append(f"i32.const {int(v)}")
            return out
        if k == "var":
            sym = ctx.ensure_local(expr["name"])
            out.append(f"local.get {sym}")
            return out
        if k == "unary":
            op = expr["op"]
            if op == "-":
                out.append("i32.const 0")
                out.extend(emit_expr(ctx, expr["expr"]))
                out.append("i32.sub")
                return out
            if op == "not":
                out.extend(emit_expr(ctx, expr["expr"]))
                out.append("i32.eqz")
                return out
            raise WasmGenError(WasmNote("ERROR","WASM-0400",f"Unsupported unary op: {op}", _origin_ref(expr)))
        if k == "binary":
            op = expr["op"]
            out.extend(emit_expr(ctx, expr["left"]))
            out.extend(emit_expr(ctx, expr["right"]))
            opmap = {
                "+":"i32.add","-":"i32.sub","*":"i32.mul","/":"i32.div_s",
                "==":"i32.eq","!=":"i32.ne","<":"i32.lt_s","<=":"i32.le_s",
                ">":"i32.gt_s",">=":"i32.ge_s","and":"i32.and","or":"i32.or",
            }
            inst = opmap.get(op)
            if not inst:
                raise WasmGenError(WasmNote("ERROR","WASM-0401",f"Unsupported binary op: {op}", _origin_ref(expr)))
            out.append(inst)
            return out
        if k == "call":
            cal = expr["callee"]
            if cal not in fn_names:
                raise WasmGenError(WasmNote("ERROR","WASM-0500",f"Unsupported call target: {cal}", _origin_ref(expr)))
            for a in (expr.get("args") or []):
                out.extend(emit_expr(ctx, a))
            out.append(f"call ${cal}")
            return out
        raise WasmGenError(WasmNote("ERROR","WASM-0999",f"Unknown expr kind: {k}", _origin_ref(expr)))

    def emit_stmt(ctx: _FnCtx, st: Dict[str, Any]) -> List[str]:
        k = st["kind"]
        out: List[str] = []
        if k == "assign":
            sym = ctx.ensure_local(st["name"])
            out.extend(emit_expr(ctx, st["value"]))
            out.append(f"local.set {sym}")
            return out
        if k == "expr":
            out.extend(emit_expr(ctx, st["value"]))
            out.append("drop")
            return out
        if k == "return":
            if st.get("value") is None:
                out.append("i32.const 0")
            else:
                out.extend(emit_expr(ctx, st["value"]))
            out.append("return")
            return out
        if k == "if":
            out.extend(emit_expr(ctx, st["cond"]))
            out.append("if")
            for x in (st.get("then") or []):
                out.extend(["  " + i for i in emit_stmt(ctx, x)])
            els = st.get("else") or []
            if els:
                out.append("else")
                for x in els:
                    out.extend(["  " + i for i in emit_stmt(ctx, x)])
            out.append("end")
            return out
        if k == "while":
            out.append("block $exit")
            out.append("  loop $loop")
            out.extend(["    " + i for i in emit_expr(ctx, st["cond"])])
            out.append("    i32.eqz")
            out.append("    br_if $exit")
            for x in (st.get("body") or []):
                out.extend(["    " + i for i in emit_stmt(ctx, x)])
            out.append("    br $loop")
            out.append("  end")
            out.append("end")
            return out
        raise WasmGenError(WasmNote("ERROR","WASM-0600",f"Unsupported statement kind: {k}", _origin_ref(st)))

    for fn in (mod.get("functions") or []):
        name = fn["name"]
        params = [p["name"] for p in (fn.get("params") or [])]
        for p in (fn.get("params") or []):
            _ensure_i32_type(p.get("type"), origin=_origin_ref(p))
        _ensure_i32_type(fn.get("ret_type"), origin=_origin_ref(fn))

        ctx = _FnCtx(params)

        def scan(sts: List[Dict[str, Any]]):
            for st in sts:
                if st["kind"] == "assign":
                    ctx.ensure_local(st["name"])
                if st["kind"] == "if":
                    scan(st.get("then") or [])
                    scan(st.get("else") or [])
                if st["kind"] == "while":
                    scan(st.get("body") or [])
        scan(fn.get("body") or [])

        header = f'  (func ${name} ' + " ".join(f"(param ${p} i32)" for p in params) + " (result i32)"
        emit(header)
        for loc in ctx.locals:
            emit(f"    (local {loc} i32)")
        body = fn.get("body") or []
        if not body:
            emit("    i32.const 0")
            emit("    return")
        else:
            for st in body:
                for inst in emit_stmt(ctx, st):
                    emit("    " + inst)
            emit("    i32.const 0")
            emit("    return")
        emit("  )")
        emit(f'  (export "{name}" (func ${name}))')
        emit("")

    emit(")")
    return "\n".join(lines) + "\n", notes
