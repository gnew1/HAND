#!/usr/bin/env python3
"""
HAND v0.1 MVP Compiler (handc)

Targets:
  - python  (supported)
  - html    (supported as "explainable UI stub")
  - sql     (supported as "DDL/DML stub" + passthrough for SQL blocks)
  - rust    (stub)
  - wasm    (stub)

Usage:
  python handc.py input.hand --target python --out dist/
  python handc.py input.hand --target python --emit-ir dist/program.ir.json

Design notes:
  - This is an MVP: tiny, pragmatic, and intentionally limited.
  - HAND here is treated as a *controlled, indentation-based* language.
  - Emojis are allowed anywhere as semantic markers but are ignored by the parser
    except for a few canonical ones (📤, 📥, 🔧, 🏁).
"""

from __future__ import annotations
import argparse, json, os, re, sys
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Tuple, Union

# ----------------------------
# Utilities
# ----------------------------

EMOJI_PREFIXES = {
    "📤": "show",
    "📥": "ask",
    "🔧": "function",
    "🏁": "return",
    "🐛": "error",
    "⚠️": "warn",
}

def strip_comment(line: str) -> str:
    # Allow // or # comments
    for sep in ("//", "#"):
        idx = line.find(sep)
        if idx != -1:
            return line[:idx]
    return line

def normalize_line(line: str) -> str:
    # Remove common leading emoji markers like "📤 " without losing the keyword
    s = line.strip()
    for em, kw in EMOJI_PREFIXES.items():
        if s.startswith(em):
            s = s[len(em):].lstrip()
            # If line becomes empty, keep empty
            break
    return s

def count_indent(raw: str) -> int:
    # 4 spaces = 1 indent level; tabs count as 4 spaces
    raw = raw.rstrip("\n")
    prefix = raw[: len(raw) - len(raw.lstrip(" \t"))]
    spaces = 0
    for ch in prefix:
        spaces += 4 if ch == "\t" else 1
    if spaces % 4 != 0:
        raise SyntaxError(f"Indentation must be multiple of 4 spaces (got {spaces}).")
    return spaces // 4

# ----------------------------
# AST nodes
# ----------------------------

@dataclass
class Node:
    kind: str
    loc: Tuple[int, str]  # (line_no, raw_line)
    children: List["Node"] = field(default_factory=list)
    value: Any = None

def n(kind: str, line_no: int, raw: str, value: Any = None, children: Optional[List[Node]] = None) -> Node:
    return Node(kind=kind, loc=(line_no, raw), value=value, children=children or [])

# ----------------------------
# Parser
# ----------------------------

HEADER_RE = re.compile(r'^(program|🎬\s*program)\s+"([^"]+)"\s*:?$', re.IGNORECASE)
FUNC_RE   = re.compile(r'^(function|🔧\s*function)\s+([A-Za-z_]\w*)\s*(\((.*)\))?\s*:?$', re.IGNORECASE)
IF_RE     = re.compile(r'^(if|🤔\s*if)\s+(.+?)\s*:?$', re.IGNORECASE)
ELSE_RE   = re.compile(r'^else\s*:?$', re.IGNORECASE)
LOOP_RE   = re.compile(r'^(loop|🔂\s*repeat)\s+(\d+)\s+(times)\s*:?$', re.IGNORECASE)
WHILE_RE  = re.compile(r'^(while|🔁\s*while)\s+(.+?)\s*:?$', re.IGNORECASE)
RETURN_RE = re.compile(r'^(return|🏁\s*return)\s*(.*)$', re.IGNORECASE)
SHOW_RE   = re.compile(r'^(show|print)\s+(.+)$', re.IGNORECASE)
ASK_RE    = re.compile(r'^(ask|input)\s+"([^"]*)"\s*->\s*([A-Za-z_]\w*)\s*$', re.IGNORECASE)
ASSIGN_RE = re.compile(r'^(set\s+)?([A-Za-z_]\w*)\s*=\s*(.+)$', re.IGNORECASE)
CALL_RE   = re.compile(r'^(call\s+)?([A-Za-z_]\w*)\s*\((.*)\)\s*$', re.IGNORECASE)
SQL_BLOCK_RE = re.compile(r'^(sql|🗃️\s*database)\s*:?$', re.IGNORECASE)
HTML_BLOCK_RE = re.compile(r'^(ui|🖥️\s*interface|html)\s*:?$', re.IGNORECASE)

class HandParser:
    def __init__(self, src: str):
        self.lines_raw = src.splitlines()

    def parse(self) -> Node:
        root = n("module", 0, "<module>")
        stack: List[Tuple[int, Node]] = [(0, root)]  # (indent, node)
        current_program: Optional[Node] = None

        for i, raw in enumerate(self.lines_raw, start=1):
            stripped = strip_comment(raw).rstrip()
            if not stripped.strip():
                continue

            indent = count_indent(raw)
            text = normalize_line(stripped)

            # Enforce max 4 indent levels for MVP (spec suggestion)
            if indent > 4:
                raise SyntaxError(f"Max indent level is 4 in MVP (line {i}).")

            # Adjust stack to current indent
            while stack and indent < stack[-1][0]:
                stack.pop()
            if not stack:
                raise SyntaxError(f"Indentation error at line {i}.")

            if indent > stack[-1][0]:
                # Must be exactly one deeper than last indent
                if indent != stack[-1][0] + 1:
                    raise SyntaxError(f"Indentation must increase by 1 level (line {i}).")

            parent = stack[-1][1]

            node = self._parse_line(i, raw, text)
            parent.children.append(node)

            # Push block headers
            if node.kind in ("program", "function", "if", "else", "loop", "while", "sql_block", "html_block"):
                stack.append((indent + 1, node))

        return root

    def _parse_line(self, line_no: int, raw: str, text: str) -> Node:
        m = HEADER_RE.match(text)
        if m:
            return n("program", line_no, raw, {"name": m.group(2)})

        m = FUNC_RE.match(text)
        if m:
            args = []
            if m.group(4) is not None and m.group(4).strip():
                args = [a.strip() for a in m.group(4).split(",") if a.strip()]
            return n("function", line_no, raw, {"name": m.group(2), "args": args})

        m = IF_RE.match(text)
        if m:
            return n("if", line_no, raw, {"cond": m.group(2).strip()})

        if ELSE_RE.match(text):
            return n("else", line_no, raw)

        m = LOOP_RE.match(text)
        if m:
            return n("loop", line_no, raw, {"count": int(m.group(2))})

        m = WHILE_RE.match(text)
        if m:
            return n("while", line_no, raw, {"cond": m.group(2).strip()})

        m = RETURN_RE.match(text)
        if m:
            return n("return", line_no, raw, {"expr": m.group(2).strip()})

        m = ASK_RE.match(text)
        if m:
            return n("ask", line_no, raw, {"prompt": m.group(2), "var": m.group(3)})

        m = SHOW_RE.match(text)
        if m:
            return n("show", line_no, raw, {"expr": m.group(2).strip()})

        m = ASSIGN_RE.match(text)
        if m:
            return n("assign", line_no, raw, {"var": m.group(2), "expr": m.group(3).strip()})

        m = SQL_BLOCK_RE.match(text)
        if m:
            return n("sql_block", line_no, raw)

        m = HTML_BLOCK_RE.match(text)
        if m:
            return n("html_block", line_no, raw)

        m = CALL_RE.match(text)
        if m:
            return n("call", line_no, raw, {"name": m.group(2), "args": m.group(3).strip()})

        # Fallback: raw statement (kept for HTML/SQL explanation)
        return n("stmt", line_no, raw, {"text": text.strip()})

# ----------------------------
# IR lowering
# ----------------------------

def to_ir(ast: Node) -> Dict[str, Any]:
    def conv(node: Node) -> Dict[str, Any]:
        return {
            "kind": node.kind,
            "loc": {"line": node.loc[0], "raw": node.loc[1]},
            "value": node.value,
            "children": [conv(c) for c in node.children],
        }
    return conv(ast)

# ----------------------------
# Code generation: Python
# ----------------------------

def _py_expr(expr: str) -> str:
    # MVP: passthrough expression (assumes controlled input)
    return expr

def gen_python(ast: Node) -> str:
    out: List[str] = []
    out.append("# Generated by handc (HAND v0.1 MVP) -> Python")
    out.append("from __future__ import annotations")
    out.append("")
    out.append("def __hand_main__():")
    body: List[str] = []
    indent = "    "

    def emit(line: str, level: int = 1):
        body.append((indent * level) + line)

    def gen_block(nodes: List[Node], level: int):
        has_any = False
        for node in nodes:
            has_any = True
            k = node.kind
            v = node.value or {}
            if k == "program":
                # program header: just comment and recurse
                emit(f"# 🎬 PROGRAM: {v.get('name','')}", level)
                gen_block(node.children, level)
            elif k == "function":
                name = v["name"]
                args = v.get("args") or []
                emit(f"def {name}({', '.join(args)}):", level)
                if node.children:
                    gen_block(node.children, level + 1)
                else:
                    emit("pass", level + 1)
            elif k == "assign":
                emit(f"{v['var']} = {_py_expr(v['expr'])}", level)
            elif k == "ask":
                prompt = v["prompt"].replace('"', '\\"')
                emit(f"{v['var']} = input(\"{prompt}\")", level)
            elif k == "show":
                emit(f"print({_py_expr(v['expr'])})", level)
            elif k == "call":
                emit(f"{v['name']}({_py_expr(v.get('args',''))})", level)
            elif k == "return":
                expr = v.get("expr","").strip()
                if expr:
                    emit(f"return {_py_expr(expr)}", level)
                else:
                    emit("return", level)
            elif k == "if":
                emit(f"if {_py_expr(v['cond'])}:", level)
                gen_block(node.children, level + 1)
            elif k == "else":
                emit("else:", level)
                gen_block(node.children, level + 1)
            elif k == "loop":
                emit(f"for __i in range({v['count']}):", level)
                gen_block(node.children, level + 1)
            elif k == "while":
                emit(f"while {_py_expr(v['cond'])}:", level)
                gen_block(node.children, level + 1)
            elif k in ("sql_block", "html_block"):
                # Ignore in python output, but keep as comment
                emit(f"# [{k}] (ignored in python target)", level)
            else:
                emit(f"# [unparsed] {node.value.get('text') if node.value else node.loc[1].strip()}", level)

        if not has_any:
            emit("pass", level)

    gen_block(ast.children, 1)
    out.extend(body)
    out.append("")
    out.append("if __name__ == '__main__':")
    out.append("    __hand_main__()")
    return "\n".join(out)

# ----------------------------
# Code generation: HTML (explainable stub)
# ----------------------------

def gen_html(ast: Node) -> str:
    # MVP: render the HAND program as an interactive "readable spec" with minimal widgets
    # If we detect ask/show patterns, we generate a tiny JS runner for a subset:
    #   - assigns, show strings/identifiers, ask -> variables, if (only ==, !=, <, > with literals)
    #   - loops not executed (shown as narrative)
    # Goal: be honest, but useful.
    hand_lines = []
    def collect(node: Node, depth: int=0):
        if node.loc[0] == 0:
            for c in node.children: collect(c, 0)
            return
        raw = node.loc[1].rstrip("\n")
        hand_lines.append(raw)
        for c in node.children:
            collect(c, depth+1)
    collect(ast)

    escaped = []
    for ln in hand_lines:
        ln = ln.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        escaped.append(ln)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HAND v0.1 MVP - HTML View</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    pre {{ background: #f7f7f7; padding: 12px; border-radius: 10px; overflow:auto; }}
    .muted {{ color: #666; font-size: 14px; }}
  </style>
</head>
<body>
  <h1>HAND → HTML (MVP)</h1>
  <p class="muted">Esta salida es una vista explicable del programa HAND. En v0.1 no ejecuta toda la lógica; sirve como “interfaz visible” y documentación.</p>

  <div class="card">
    <h2>Código HAND</h2>
    <pre>{chr(10).join(escaped)}</pre>
  </div>

  <div class="card">
    <h2>Notas</h2>
    <ul>
      <li>El target HTML en este MVP es una representación documental/UX (no un runtime completo).</li>
      <li>Para ejecutar la lógica, compila a <b>Python</b> y ejecútalo.</li>
      <li>En versiones posteriores: UI declarativa real + bindings.</li>
    </ul>
  </div>
</body>
</html>
"""
    return html

# ----------------------------
# Code generation: SQL (DDL/DML stub)
# ----------------------------

def gen_sql(ast: Node) -> str:
    # MVP: If there's an explicit sql_block, emit its raw lines (children as raw text)
    # Otherwise, provide a comment-only file.
    lines: List[str] = []
    lines.append("-- Generated by handc (HAND v0.1 MVP) -> SQL")
    lines.append("-- Note: Only explicit SQL blocks are emitted in v0.1.")
    lines.append("")
    def walk(node: Node, in_sql: bool=False):
        nonlocal lines
        if node.kind == "sql_block":
            lines.append(f"-- SQL BLOCK (line {node.loc[0]})")
            for c in node.children:
                raw = strip_sql_comment(c.loc[1]).rstrip()
                if raw.strip():
                    lines.append(raw.strip())
            lines.append("")
            return
        for c in node.children:
            walk(c, in_sql)
    def strip_sql_comment(s: str) -> str:
        return s
    walk(ast)
    if len(lines) <= 3:
        lines.append("-- (no SQL blocks found)")
    return "\n".join(lines)

# ----------------------------
# Targets: Rust/WASM stubs
# ----------------------------

def gen_rust_stub(ast: Node) -> str:
    return """// Generated by handc (HAND v0.1 MVP) -> Rust (STUB)
// v0.1 does not yet lower HAND-IR to Rust. This file is a placeholder.
//
// Next steps:
//  - Define strict typing + ownership-friendly lowering.
//  - Map HAND effects (IO, DB, network) to explicit traits.
//  - Provide a runtime crate `hand_runtime`.
fn main() {
    println!(\"HAND Rust target not implemented in MVP.\");
}
"""

def gen_wasm_stub(ast: Node) -> str:
    return """;; Generated by handc (HAND v0.1 MVP) -> WASM (STUB)
;; v0.1 does not yet emit WebAssembly. Placeholder only.
;; Next steps:
;;  - Choose WASI + host bindings
;;  - Lower arithmetic + control flow to wasm instructions
;;  - Define imports for IO
(module
  (func (export "main")
    ;; no-op
  )
)
"""

# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser(prog="handc", description="HAND v0.1 MVP compiler")
    ap.add_argument("input", help="Path to .hand file")
    ap.add_argument("--target", required=True, choices=["python","html","sql","rust","wasm"], help="Target language")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--emit-ir", default=None, help="Optional path to write HAND-IR JSON")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        src = f.read()

    parser = HandParser(src)
    ast = parser.parse()
    ir = to_ir(ast)

    os.makedirs(args.out, exist_ok=True)

    if args.emit_ir:
        with open(args.emit_ir, "w", encoding="utf-8") as f:
            json.dump(ir, f, ensure_ascii=False, indent=2)

    if args.target == "python":
        code = gen_python(ast)
        out_path = os.path.join(args.out, "program.py")
    elif args.target == "html":
        code = gen_html(ast)
        out_path = os.path.join(args.out, "program.html")
    elif args.target == "sql":
        code = gen_sql(ast)
        out_path = os.path.join(args.out, "program.sql")
    elif args.target == "rust":
        code = gen_rust_stub(ast)
        out_path = os.path.join(args.out, "main.rs")
    elif args.target == "wasm":
        code = gen_wasm_stub(ast)
        out_path = os.path.join(args.out, "module.wat")
    else:
        raise ValueError("Unknown target")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"OK: wrote {out_path}")
    if args.emit_ir:
        print(f"OK: wrote IR {args.emit_ir}")

if __name__ == "__main__":
    main()
