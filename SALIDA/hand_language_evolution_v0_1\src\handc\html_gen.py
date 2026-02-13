from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import ast as _py_ast
import html as _html

# HAND-IR v0.1 -> HTML v0.1 (UI declarativa + bindings mínimos)
#
# Enfoque v0.1:
# - HTML estático + JS mínimo (sin frameworks).
# - Genera:
#   (A) Forms desde module.types (Record): Text/Int/Bool (+ Optional) -> <input> / <checkbox>.
#       - Al "Preview", renderiza JSON en <pre>.
#   (B) "Programa interactivo" muy simple para toplevel:
#       - Soporta assign x = ask("...")  => input field para x
#       - Soporta show <expr>            => render en lista de outputs
#       - Soporta expr(call show(..)) también
#   (C) "ask→show" demo: botón Run que lee inputs y evalúa secuencia determinista.
#
# Sin JS:
# - No es viable para ask/show interactivo en navegador sin servidor.
# - Por tanto: v0.1 usa JS mínimo (declarado explícitamente).
#
# Degradaciones ("declared but not compiled" / hard errors):
# - Control de flujo (if/while), funciones, IO más allá de ask/show, efectos net/fs/env/crypto,
#   tipos complejos (List/Map/Record runtime), y expresiones no soportadas.

@dataclass(frozen=True)
class HtmlNote:
    kind: str   # ERROR|WARN|INFO
    code: str
    message: str
    origin_ref: Optional[str]=None

class HtmlGenError(Exception):
    def __init__(self, note: HtmlNote):
        super().__init__(note.message)
        self.note = note

def _origin_ref(node: Dict[str, Any]) -> Optional[str]:
    try:
        return node.get("origin", {}).get("ref")
    except Exception:
        return None

def _decode_text_literal(token_text: str) -> str:
    try:
        v = _py_ast.literal_eval(token_text)
        return v if isinstance(v, str) else str(v)
    except Exception:
        if len(token_text) >= 2 and token_text[0] == token_text[-1] == '"':
            return token_text[1:-1]
        return token_text

def _type_kind(t: Dict[str, Any]) -> str:
    return t.get("kind")

def _unwrap_optional(t: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    if t.get("kind") == "Optional":
        inner = (t.get("args") or [None])[0]
        if not inner:
            return {"kind":"Text"}, True
        return inner, True
    return t, False

def _html_input_for_type(name: str, t: Dict[str, Any]) -> str:
    inner, opt = _unwrap_optional(t)
    k = _type_kind(inner)
    req = "" if opt else " required"
    if k == "Text":
        return f'<input id="{_html.escape(name)}" name="{_html.escape(name)}" type="text"{req} />'
    if k == "Int":
        return f'<input id="{_html.escape(name)}" name="{_html.escape(name)}" type="number" step="1"{req} />'
    if k == "Float":
        return f'<input id="{_html.escape(name)}" name="{_html.escape(name)}" type="number" step="any"{req} />'
    if k == "Bool":
        return f'<input id="{_html.escape(name)}" name="{_html.escape(name)}" type="checkbox" />'
    raise HtmlGenError(HtmlNote("ERROR","HTML-0300",f"Form field type not supported: {k}", None))

def _js_expr(expr: Dict[str, Any]) -> str:
    k = expr.get("kind")
    if k == "lit":
        ty = (expr.get("type") or {}).get("kind")
        v = expr.get("value")
        if ty == "Text" and isinstance(v, str):
            s = _decode_text_literal(v)
            return json_string(s)
        if ty == "Bool":
            if isinstance(v, str):
                vv = v.strip().lower()
                return "true" if vv == "true" else "false"
            return "true" if bool(v) else "false"
        if ty == "Null" or v is None or (isinstance(v, str) and v.strip().lower()=="null"):
            return "null"
        return str(v)
    if k == "var":
        return f'env[{json_string(expr["name"])}]'
    if k == "binary":
        op = expr["op"]
        l = _js_expr(expr["left"])
        r = _js_expr(expr["right"])
        if op == "+":
            return f'({l} + {r})'
        if op in ("-","*","/","==","!=","<","<=",">",">="):
            return f'({l} {op} {r})'
        if op == "and":
            return f'({l} && {r})'
        if op == "or":
            return f'({l} || {r})'
        raise HtmlGenError(HtmlNote("ERROR","HTML-0501",f"Unsupported binary op: {op}", _origin_ref(expr)))
    if k == "unary":
        op = expr["op"]
        inner = _js_expr(expr["expr"])
        if op == "-":
            return f'(-({inner}))'
        if op == "not":
            return f'(!({inner}))'
        raise HtmlGenError(HtmlNote("ERROR","HTML-0502",f"Unsupported unary op: {op}", _origin_ref(expr)))
    if k == "call":
        cal = expr["callee"]
        args = expr.get("args") or []
        if cal == "ask":
            # handled at stmt-level; expression-level fallback reads input by variable name not known -> error
            raise HtmlGenError(HtmlNote("ERROR","HTML-0600","ask() must appear only as RHS of assignment in HTML v0.1.", _origin_ref(expr)))
        if cal == "show":
            # expression form: show(x) -> null
            return "null"
        raise HtmlGenError(HtmlNote("ERROR","HTML-0601",f"Unsupported call: {cal}", _origin_ref(expr)))
    raise HtmlGenError(HtmlNote("ERROR","HTML-0999",f"Unsupported expr kind: {k}", _origin_ref(expr)))

def json_string(s: str) -> str:
    # safe JS string literal
    import json
    return json.dumps(s, ensure_ascii=False)

def gen_html(ir: Dict[str, Any]) -> Tuple[str, List[HtmlNote]]:
    if ir.get("ir_version") != "0.1.0":
        raise ValueError("Unsupported IR version")
    mod = ir["module"]
    notes: List[HtmlNote] = []

    if (mod.get("functions") or []):
        raise HtmlGenError(HtmlNote("ERROR","HTML-0001","HTML v0.1 does not compile HAND functions (only types + top-level ask/show demo).", _origin_ref((mod.get("functions") or [])[0])))

    # Collect ask variables from top-level assignments: x = ask(...)
    ask_vars: List[Tuple[str, str]] = []  # (name, prompt)
    show_exprs: List[Dict[str, Any]] = []

    for st in (mod.get("toplevel") or []):
        k = st.get("kind")
        if k == "assign":
            rhs = st.get("value") or {}
            if rhs.get("kind") == "call" and rhs.get("callee") == "ask":
                args = rhs.get("args") or []
                prompt = ""
                if args:
                    if args[0].get("kind") == "lit":
                        pv = args[0].get("value")
                        prompt = _decode_text_literal(pv) if isinstance(pv, str) else str(pv)
                ask_vars.append((st["name"], prompt))
            else:
                # allow compute assigns only if pure literals/vars/binary
                pass
        elif k == "show":
            show_exprs.append(st["value"])
        elif k == "expr":
            v = st.get("value") or {}
            if v.get("kind") == "call" and v.get("callee") == "show":
                args = v.get("args") or []
                if args:
                    show_exprs.append(args[0])
                else:
                    show_exprs.append({"kind":"lit","value":None,"type":{"kind":"Null"}})
            else:
                raise HtmlGenError(HtmlNote("ERROR","HTML-0002","Only assign/ show / expr(show) supported at top-level for HTML v0.1.", _origin_ref(st)))
        else:
            raise HtmlGenError(HtmlNote("ERROR","HTML-0002",f"Top-level stmt kind '{k}' unsupported for HTML v0.1.", _origin_ref(st)))

    # Forms from records
    record_forms: List[str] = []
    for td in (mod.get("types") or []):
        if td.get("kind") != "record":
            raise HtmlGenError(HtmlNote("ERROR","HTML-0301",f"Unsupported type_decl kind: {td.get('kind')}", _origin_ref(td)))
        tname = td["name"]
        fields = td.get("fields") or []
        parts: List[str] = []
        parts.append(f'<section class="card">')
        parts.append(f'  <h2>Form: { _html.escape(tname) }</h2>')
        parts.append(f'  <form id="form_{_html.escape(tname)}" onsubmit="return false;">')
        for f in fields:
            fname = f["name"]
            t = f["type"]
            inp = _html_input_for_type(f"{tname}.{fname}", t)
            parts.append('    <div class="row">')
            parts.append(f'      <label for="{_html.escape(tname+"."+fname)}">{_html.escape(fname)}</label>')
            parts.append(f'      {inp}')
            parts.append('    </div>')
        parts.append(f'    <button type="button" onclick="previewRecord({json_string(tname)})">Preview JSON</button>')
        parts.append('  </form>')
        parts.append(f'  <pre id="preview_{_html.escape(tname)}" class="preview"></pre>')
        parts.append('</section>')
        record_forms.append("\n".join(parts))

    # Build JS program runner for ask/show
    ask_inputs_html = []
    if ask_vars:
        ask_inputs_html.append('<section class="card">')
        ask_inputs_html.append('  <h2>Program Inputs (ask)</h2>')
        ask_inputs_html.append('  <form id="hand_inputs" onsubmit="return false;">')
        for var, prompt in ask_vars:
            label = prompt or var
            ask_inputs_html.append('    <div class="row">')
            ask_inputs_html.append(f'      <label for="{_html.escape(var)}">{_html.escape(label)}</label>')
            ask_inputs_html.append(f'      <input id="{_html.escape(var)}" name="{_html.escape(var)}" type="text" />')
            ask_inputs_html.append('    </div>')
        ask_inputs_html.append('    <button type="button" onclick="runProgram()">Run</button>')
        ask_inputs_html.append('  </form>')
        ask_inputs_html.append('  <div id="hand_outputs" class="outputs"></div>')
        ask_inputs_html.append('</section>')
    elif show_exprs:
        ask_inputs_html.append('<section class="card">')
        ask_inputs_html.append('  <h2>Program Output</h2>')
        ask_inputs_html.append('  <button type="button" onclick="runProgram()">Run</button>')
        ask_inputs_html.append('  <div id="hand_outputs" class="outputs"></div>')
        ask_inputs_html.append('</section>')

    # JS: previewRecord + runProgram
    # For records, parse values based on input types by simple heuristic from HTML input attrs.
    js_lines: List[str] = []
    js_lines.append("function _getInputValue(id) {")
    js_lines.append("  const el = document.getElementById(id);")
    js_lines.append("  if (!el) return null;")
    js_lines.append("  if (el.type === 'checkbox') return !!el.checked;")
    js_lines.append("  if (el.type === 'number') {")
    js_lines.append("    if (el.value === '') return null;")
    js_lines.append("    const n = Number(el.value);")
    js_lines.append("    return Number.isNaN(n) ? null : n;")
    js_lines.append("  }")
    js_lines.append("  return el.value;")
    js_lines.append("}")
    js_lines.append("")
    js_lines.append("function previewRecord(tname) {")
    js_lines.append("  const pre = document.getElementById('preview_' + tname);")
    js_lines.append("  const obj = {};")
    # generate per record field ids
    for td in (mod.get("types") or []):
        tname = td["name"]
        for f in (td.get("fields") or []):
            fid = f"{tname}.{f['name']}"
            js_lines.append(f"  if (tname === {json_string(tname)}) obj[{json_string(f['name'])}] = _getInputValue({json_string(fid)});")
    js_lines.append("  if (pre) pre.textContent = JSON.stringify(obj, null, 2);")
    js_lines.append("}")
    js_lines.append("")
    js_lines.append("function runProgram() {")
    js_lines.append("  const out = document.getElementById('hand_outputs');")
    js_lines.append("  if (out) out.innerHTML = '';")
    js_lines.append("  const env = {};")
    # assign ask vars from inputs
    for var, _prompt in ask_vars:
        js_lines.append(f"  env[{json_string(var)}] = _getInputValue({json_string(var)});")
    # TODO: support non-ask assignments later
    # show expressions
    for expr in show_exprs:
        js_expr = _js_expr(expr)
        js_lines.append("  {")
        js_lines.append(f"    const v = {js_expr};")
        js_lines.append("    const line = document.createElement('div');")
        js_lines.append("    line.className = 'line';")
        js_lines.append("    line.textContent = String(v === null ? 'null' : v);")
        js_lines.append("    if (out) out.appendChild(line);")
        js_lines.append("  }")
    js_lines.append("}")
    js = "\n".join(js_lines)

    records_html = "\n".join(record_forms)
    prog_html = "\n".join(ask_inputs_html)

    html_doc = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>HAND HTML v0.1</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; max-width: 900px; }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; }}
    .row {{ display: grid; grid-template-columns: 160px 1fr; gap: 12px; align-items: center; margin: 8px 0; }}
    label {{ font-weight: 600; }}
    input[type="text"], input[type="number"] {{ padding: 8px; border: 1px solid #ccc; border-radius: 8px; }}
    button {{ padding: 8px 12px; border: 1px solid #999; border-radius: 10px; background: white; cursor: pointer; }}
    .outputs {{ margin-top: 12px; border-top: 1px dashed #ccc; padding-top: 12px; }}
    .line {{ padding: 4px 0; }}
    .preview {{ background: #fafafa; padding: 12px; border-radius: 10px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>HAND HTML v0.1</h1>
  <p>This output uses <b>minimal JavaScript</b> for bindings (ask/show + form preview). No frameworks.</p>
  <div class="grid">
    {records_html}
    {prog_html}
  </div>
  <script>
{js}
  </script>
</body>
</html>
""".format(records_html=records_html, prog_html=prog_html, js=js)

    return html_doc, notes
