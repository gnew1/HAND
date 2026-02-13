from __future__ import annotations
import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .lexer import lex
from .parser import parse
from .typecheck import typecheck
from .lowering import lower_program
from .enforce import enforce_capabilities
from .enforce import CapabilityError

from .python_gen import gen_python
from .wasm_gen import gen_wat, WasmGenError
from .sql_gen import gen_sql, SqlGenError
from .html_gen import gen_html, HtmlGenError

# ----------------------------
# build_report.json (standard)
# ----------------------------
# This file is written to <out>/build_report.json for every build.
#
# Minimal stability contract:
# - schema_version: "0.1"
# - status: "ok" | "error"
# - diagnostics: list[DiagnosticLike]
# - degradations: list[NoteLike] (unsupported / downgraded features)
# - capabilities: {declared, required, missing, approvals_needed, supervision_level}
# - artifacts: {target, out_dir, outputs[], emitted_ir?, emitted_ast?}

SCHEMA_VERSION = "0.1"

def _json_default(obj: Any):
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "to_json"):
        return obj.to_json()
    return str(obj)

def _diag_to_dict(d: Any) -> Dict[str, Any]:
    # lexer/parser/typechecker diagnostics share fields: severity, message, idref?, span?
    out: Dict[str, Any] = {}
    for k in ("severity","message","idref","code","hint"):
        if hasattr(d, k):
            v = getattr(d, k)
            if v is not None:
                out[k] = v
    # span/location
    if hasattr(d, "span") and getattr(d, "span") is not None:
        sp = getattr(d, "span")
        out["span"] = {k:getattr(sp,k) for k in ("filename","start_line","start_col","end_line","end_col") if hasattr(sp,k)}
    return out if out else {"message": str(d)}

def _note_to_dict(n: Any) -> Dict[str, Any]:
    if isinstance(n, dict):
        return n
    out: Dict[str, Any] = {}
    for k in ("kind","code","message","origin_ref"):
        if hasattr(n, k):
            v = getattr(n, k)
            if v is not None:
                out[k] = v
    return out if out else {"message": str(n)}

def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")

def _expand_shorthand_caps(caps: List[str]) -> List[str]:
    # Backward-compat: early lowering may emit non-canonical shorthands ("io", "fs").
    expanded: List[str] = []
    for c in caps:
        if c == "io":
            expanded.extend(["io.read", "io.write"])
        elif c == "fs":
            expanded.extend(["fs.read", "fs.write"])
        else:
            expanded.append(c)
    # stable order, unique
    seen=set()
    out=[]
    for c in expanded:
        if c not in seen:
            out.append(c); seen.add(c)
    return out

def _target_outfile(target: str) -> str:
    return {
        "python": "main.py",
        "wasm": "main.wat",
        "sql": "main.sql",
        "html": "index.html",
    }[target]

def build(
    *,
    input_path: Path,
    out_dir: Path,
    target: str,
    supervision_level: int,
    emit_ir: bool,
    emit_ast: bool,
) -> Tuple[int, Dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "input": {"path": str(input_path)},
        "artifacts": {
            "target": target,
            "out_dir": str(out_dir),
            "outputs": [],
            "emitted_ir": None,
            "emitted_ast": None,
        },
        "capabilities": {
            "supervision_level": supervision_level,
            "declared": [],
            "required": [],
            "missing": [],
            "approvals_needed": [],
        },
        "diagnostics": [],
        "degradations": [],
    }

    # 1) read
    text = input_path.read_text(encoding="utf-8")

    # 2) lex
    tokens, ldiags = lex(text, str(input_path))
    report["diagnostics"].extend([_diag_to_dict(d) for d in ldiags])
    if ldiags:
        return 2, report

    # 3) parse
    pres = parse(tokens, str(input_path))
    report["diagnostics"].extend([_diag_to_dict(d) for d in pres.diagnostics])
    if pres.diagnostics:
        return 2, report

    program = pres.program

    # emit AST (canonical, JSON-ish)
    if emit_ast:
        ast_path = out_dir / "ast.json"
        # Program nodes are dataclasses; use json default
        _write_json(ast_path, program)
        report["artifacts"]["emitted_ast"] = str(ast_path)

    # 4) validate+typecheck (normative)
    tdiags = typecheck(program, str(input_path))
    report["diagnostics"].extend([_diag_to_dict(d) for d in tdiags])
    if tdiags:
        return 2, report

    # 5) IR
    ir = lower_program(program, module_name=input_path.stem, semver="0.1.0")
    # Normalize/expand capability shorthands to canonical form before enforcement.
    if "module" in ir and isinstance(ir["module"], dict):
        ir["module"]["capabilities"] = _expand_shorthand_caps(list(ir["module"].get("capabilities") or []))
    for st in ir.get("module", {}).get("toplevel", []) or []:
        if isinstance(st, dict) and "capabilities" in st:
            st["capabilities"] = _expand_shorthand_caps(list(st.get("capabilities") or []))
    report["capabilities"]["declared"] = list(ir.get("module", {}).get("capabilities") or [])

    if emit_ir:
        ir_path = out_dir / "ir.json"
        _write_json(ir_path, ir)
        report["artifacts"]["emitted_ir"] = str(ir_path)

    # 6) enforce capabilities (security)
    try:
        ir2, cap_diags = enforce_capabilities(
            ir,
            supervision_level=supervision_level,
            approvals=None,
            scope="module",
        )
    except CapabilityError as e:
        # Convert to deterministic diagnostics and stop; still produce report.
        report["diagnostics"].append({"severity": "error", "message": str(e)})
        return 2, report

    # cap_diags are not the same diagnostic type; still render
    report["diagnostics"].extend([_note_to_dict(d) for d in cap_diags])

    # compute required/missing/approvals from enforce module output (if present)
    mod = ir2.get("module", {})
    report["capabilities"]["declared"] = list(mod.get("capabilities") or [])

    req = mod.get("required_capabilities") or []
    if req:
        report["capabilities"]["required"] = list(req)

    miss = mod.get("missing_capabilities") or []
    if miss:
        report["capabilities"]["missing"] = list(miss)

    appr = mod.get("approvals_needed") or []
    if appr:
        report["capabilities"]["approvals_needed"] = list(appr)

    # If enforcement produced any fatal diag, stop.
    fatal = [d for d in cap_diags if getattr(d, "kind", "") == "ERROR"]
    if fatal:
        return 2, report
    # 7) codegen per target
    out_file = out_dir / _target_outfile(target)

    try:
        if target == "python":
            code = gen_python(ir2, module_name=input_path.stem)
            out_file.write_text(code, encoding="utf-8")
        elif target == "wasm":
            wat, notes = gen_wat(ir2)
            report["degradations"].extend([_note_to_dict(n) for n in notes])
            out_file.write_text(wat, encoding="utf-8")
        elif target == "sql":
            sql, notes = gen_sql(ir2)
            report["degradations"].extend([_note_to_dict(n) for n in notes])
            out_file.write_text(sql, encoding="utf-8")
        elif target == "html":
            html, notes = gen_html(ir2)
            report["degradations"].extend([_note_to_dict(n) for n in notes])
            out_file.write_text(html, encoding="utf-8")
        else:
            raise ValueError("Unknown target")
    except (WasmGenError, SqlGenError, HtmlGenError) as e:
        # compile-time unsupported -> degradation+error
        note = getattr(e, "note", None)
        if note is not None:
            report["degradations"].append(_note_to_dict(note))
        report["diagnostics"].append({"severity":"error","message":str(e)})
        return 3, report

    report["artifacts"]["outputs"].append(str(out_file))
    report["status"] = "ok"
    return 0, report

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="handc", description="HAND compiler toolchain (v0.1)")
    ap.add_argument("input", help="input .hand file")
    ap.add_argument("--target", choices=["python","wasm","sql","html"], required=True)
    ap.add_argument("--out", default="dist", help="output directory")
    ap.add_argument("--level", type=int, default=2, choices=[1,2,3,4], help="supervision level 1-4")
    ap.add_argument("--emit-ir", action="store_true")
    ap.add_argument("--emit-ast", action="store_true")
    ap.add_argument("--json-diagnostics", action="store_true", help="print diagnostics JSON to stdout")

    args = ap.parse_args(argv)

    try:
        rc, report = build(
            input_path=Path(args.input),
            out_dir=Path(args.out),
            target=args.target,
            supervision_level=args.level,
            emit_ir=args.emit_ir,
            emit_ast=args.emit_ast,
        )
    except Exception as e:  # last-resort: never lose a report
        Path(args.out).mkdir(parents=True, exist_ok=True)
        rc = 99
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "input": {"path": str(args.input)},
            "artifacts": {
                "target": args.target,
                "out_dir": str(args.out),
                "outputs": [],
                "emitted_ir": None,
                "emitted_ast": None,
            },
            "capabilities": {
                "supervision_level": args.level,
                "declared": [],
                "required": [],
                "missing": [],
                "approvals_needed": [],
            },
            "diagnostics": [{"severity": "error", "message": f"Internal compiler error: {e}"}],
            "degradations": [],
        }

    # write report
    rep_path = Path(args.out) / "build_report.json"
    _write_json(rep_path, report)

    if args.json_diagnostics:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "diagnostics": report["diagnostics"],
                    "degradations": report["degradations"],
                    "capabilities": report["capabilities"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return rc
