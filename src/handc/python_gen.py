from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import ast as _py_ast

# HAND-IR v0.1 -> Python (conformant backend)
# Target: preserve Ω (output trace / outputs) exactly vs interpreter_ref.

def _decode_text_literal(token_text: str) -> str:
    """IR stores Text literals as their source token, e.g. \"\"hi\"\".
    We decode it to the runtime string value (without quotes, with escapes)."""
    try:
        v = _py_ast.literal_eval(token_text)
        if not isinstance(v, str):
            return str(v)
        return v
    except Exception:
        # fallback: strip outer quotes if present
        if len(token_text) >= 2 and token_text[0] == token_text[-1] == '"':
            return token_text[1:-1]
        return token_text

def _decode_bool_literal(token_text: Any) -> bool:
    if token_text is True or token_text is False:
        return bool(token_text)
    if isinstance(token_text, str):
        t = token_text.strip().lower()
        if t == "true":
            return True
        if t == "false":
            return False
    return bool(token_text)

def gen_python(ir: Dict[str, Any], *, module_name: str = "main") -> str:
    if ir.get("ir_version") != "0.1.0":
        raise ValueError("Unsupported IR version")

    mod = ir["module"]

    out: List[str] = []
    emit = out.append

    emit("from __future__ import annotations")
    emit("from dataclasses import dataclass")
    emit("from typing import Any, Dict, List")
    emit("")
    emit("# --- Runtime (matches interpreter_ref repr rules) ---")
    emit("@dataclass")
    emit("class Store:")
    emit("    frames: List[Dict[str, Any]]")
    emit("    def get(self, name: str) -> Any:")
    emit("        for fr in reversed(self.frames):")
    emit("            if name in fr:")
    emit("                return fr[name]")
    emit("        raise RuntimeError(f\"HND-RT-0001 Undefined variable '{name}'.\")")
    emit("    def set(self, name: str, value: Any) -> None:")
    emit("        for fr in reversed(self.frames):")
    emit("            if name in fr:")
    emit("                fr[name] = value")
    emit("                return")
    emit("        self.frames[-1][name] = value")
    emit("    def declare(self, name: str, value: Any) -> None:")
    emit("        self.frames[-1][name] = value")
    emit("    def push(self) -> None:")
    emit("        self.frames.append({})")
    emit("    def pop(self) -> None:")
    emit("        self.frames.pop()")
    emit("")
    emit("@dataclass")
    emit("class Runtime:")
    emit("    inputs: List[str]")
    emit("    outputs: List[str]")
    emit("    ip: int = 0")
    emit("    def _repr(self, v: Any) -> str:")
    emit("        if v is None:")
    emit("            return 'null'")
    emit("        if isinstance(v, bool):")
    emit("            return 'true' if v else 'false'")
    emit("        if isinstance(v, float):")
    emit("            return format(v, '.15g')")
    emit("        if isinstance(v, (int, str)):")
    emit("            return str(v)")
    emit("        if isinstance(v, list):")
    emit("            return '[' + ', '.join(self._repr(x) for x in v) + ']'")
    emit("        if isinstance(v, dict):")
    emit("            items = ', '.join(f\"{self._repr(k)}: {self._repr(val)}\" for k, val in v.items())")
    emit("            return '{' + items + '}'")
    emit("        return str(v)")
    emit("    def show(self, v: Any) -> None:")
    emit("        self.outputs.append(self._repr(v))")
    emit("    def ask(self, prompt: Any) -> str:")
    emit("        if self.ip >= len(self.inputs):")
    emit("            raise RuntimeError('HND-RT-0101 ask() requested input but no more mocked inputs were provided.')")
    emit("        v = self.inputs[self.ip]")
    emit("        self.ip += 1")
    emit("        return v")
    emit("")
    emit("class _ReturnSignal(Exception):")
    emit("    def __init__(self, value: Any):")
    emit("        self.value = value")
    emit("")
    emit("def _truthy(v: Any) -> bool:")
    emit("    return bool(v)")
    emit("")

    # --- codegen helpers ---
    def emit_expr(expr: Dict[str, Any]) -> str:
        k = expr["kind"]
        if k == "lit":
            ty = (expr.get("type") or {}).get("kind")
            v = expr.get("value")
            if ty == "Text" and isinstance(v, str):
                return repr(_decode_text_literal(v))
            if ty == "Bool":
                return "True" if _decode_bool_literal(v) else "False"
            if ty == "Null" or v is None or (isinstance(v, str) and v.lower() == "null"):
                return "None"
            return repr(v)
        if k == "var":
            return f"store.get({expr['name']!r})"
        if k == "unary":
            op = expr["op"]
            inner = emit_expr(expr["expr"])
            if op == "-":
                return f"(-({inner}))"
            if op == "not":
                return f"(not _truthy({inner}))"
            raise ValueError(f"Unsupported unary op: {op}")
        if k == "binary":
            op = expr["op"]
            l = emit_expr(expr["left"])
            r = emit_expr(expr["right"])
            opmap = {"==":"==","!=":"!=","<":"<",">":">","<=":"<=",">=":">=","+":"+","-":"-","*":"*","/":"/"}
            pyop = opmap.get(op)
            if pyop is None:
                raise ValueError(f"Unsupported binary op: {op}")
            return f"({l} {pyop} {r})"
        if k == "call":
            cal = expr["callee"]
            args = [emit_expr(a) for a in (expr.get("args") or [])]
            if cal == "ask":
                return f"rt.ask({args[0] if args else repr('')})"
            if cal == "show":
                return f"(rt.show({args[0] if args else 'None'}), None)[1]"
            # user function
            return f"{cal}(store, rt{', ' if args else ''}{', '.join(args)})"
        raise ValueError(f"Unknown expr kind: {k}")

    def emit_stmt(stmt: Dict[str, Any], indent: int) -> List[str]:
        ref = (stmt.get('origin') or {}).get('ref') or ''
        def OC(line: str) -> str:
            return (line + ('  # ' + ref if ref else ''))

        pad = " " * indent
        k = stmt["kind"]
        out_lines: List[str] = []
        if k == "assign":
            out_lines.append(OC(pad + f"store.set({stmt['name']!r}, {emit_expr(stmt['value'])})"))
            return out_lines
        if k == "expr":
            out_lines.append(OC(pad + emit_expr(stmt["value"])))
            return out_lines
        if k == "show":
            out_lines.append(OC(pad + f"rt.show({emit_expr(stmt['value'])})"))
            return out_lines
        if k == "verify":
            out_lines.append(OC(pad + f"if not _truthy({emit_expr(stmt['value'])}):"))
            out_lines.append(OC(pad + "    raise RuntimeError('HND-VERIFY-0001 VERIFY failed')"))
            return out_lines
        if k == "return":
            if stmt.get("value") is None:
                out_lines.append(OC(pad + "raise _ReturnSignal(None)"))
            else:
                out_lines.append(OC(pad + f"raise _ReturnSignal({emit_expr(stmt['value'])})"))
            return out_lines
        if k == "if":
            out_lines.append(OC(pad + f"if _truthy({emit_expr(stmt['cond'])}):"))
            then = stmt.get("then") or []
            if not then:
                out_lines.append(OC(pad + "    pass"))
            else:
                for st in then:
                    out_lines.extend(emit_stmt(st, indent + 4))
            els = stmt.get("else") or []
            if els:
                out_lines.append(OC(pad + "else:"))
                for st in els:
                    out_lines.extend(emit_stmt(st, indent + 4))
            return out_lines
        if k == "while":
            out_lines.append(OC(pad + f"while _truthy({emit_expr(stmt['cond'])}):"))
            body = stmt.get("body") or []
            if not body:
                out_lines.append(OC(pad + "    break"))
            else:
                for st in body:
                    out_lines.extend(emit_stmt(st, indent + 4))
            return out_lines
        raise ValueError(f"Unknown stmt kind: {k}")

    # functions
    emit("# --- User functions ---")
    for fn in mod.get("functions", []) or []:
        name = fn["name"]
        params = [p["name"] for p in (fn.get("params") or [])]
        emit(f"def {name}(store: Store, rt: Runtime{', ' if params else ''}{', '.join(params)}):")
        emit("    store.push()")
        for p in params:
            emit(f"    store.declare({p!r}, {p})")
        emit("    try:")
        body = fn.get("body") or []
        if not body:
            emit("        pass")
        else:
            for st in body:
                for ln in emit_stmt(st, 8):
                    emit(ln)
        emit("        return None")
        emit("    except _ReturnSignal as r:")
        emit("        return r.value")
        emit("    finally:")
        emit("        store.pop()")
        emit("")

    emit("# --- Top-level ---")
    emit("def __hand_main(inputs: List[str]) -> List[str]:")
    emit("    store = Store(frames=[{}])")
    emit("    rt = Runtime(inputs=list(inputs), outputs=[])")
    for st in mod.get("toplevel", []) or []:
        for ln in emit_stmt(st, 4):
            emit(ln)
    emit("    return rt.outputs")
    emit("")
    emit("def __hand_run_and_print_json(inputs: List[str]) -> None:")
    emit("    import json")
    emit("    out = __hand_main(inputs)")
    emit("    print(json.dumps({'outputs': out}, ensure_ascii=False))")
    emit("")
    emit("if __name__ == '__main__':")
    emit("    import json, sys")
    emit("    inputs = []")
    emit("    if len(sys.argv) > 1:")
    emit("        inputs = json.loads(sys.argv[1])")
    emit("    __hand_run_and_print_json(inputs)")
    emit("")
    return "\n".join(out) + "\n"
