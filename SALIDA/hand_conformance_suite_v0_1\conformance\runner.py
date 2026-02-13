from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from handc.lexer import lex
from handc.parser import parse
from handc.typecheck import typecheck
from handc.lowering import lower_program
from handc.interpreter import Interpreter, HandRuntimeError
from handc.python_gen import gen_python


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: str
    details: Dict[str, Any]


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tokens_to_json(tokens) -> List[Dict[str, Any]]:
    out=[]
    for t in tokens:
        sp=t.span
        out.append({"kind": t.kind, "value": t.value, "span": {"file": sp.file, "line": sp.line, "col": sp.col, "end_col": sp.end_col}})
    return out


def _diags_to_json(diags) -> List[Dict[str, Any]]:
    out=[]
    for d in diags:
        dd={}
        for k in ("severity","message","idref","code","hint"):
            if hasattr(d,k) and getattr(d,k) is not None:
                dd[k]=getattr(d,k)
        if hasattr(d,"span") and getattr(d,"span") is not None:
            sp=getattr(d,"span")
            if hasattr(sp,"line"):
                dd["span"]={"file":sp.file,"line":sp.line,"col":sp.col,"end_col":sp.end_col}
        out.append(dd if dd else {"message":str(d)})
    return out


def run_case(case_dir: Path) -> CaseResult:
    src = (case_dir / "program.hand").read_text(encoding="utf-8")
    meta = _read_json(case_dir.parent.parent / "manifest.json")
    case_id = case_dir.name
    m = next((x for x in meta if x["case_id"] == case_id), None)
    if not m:
        return CaseResult(case_id, "error", {"message": "missing manifest entry"})
    inputs = m.get("inputs") or []

    # ---- lexer
    toks, ldiags = lex(src, f"{case_id}.hand")
    got_tokens = _tokens_to_json(toks)
    exp_tokens = _read_json(case_dir / "expected.tokens.json")
    if got_tokens != exp_tokens:
        return CaseResult(case_id, "fail", {"stage": "lexer", "diff": "tokens"})
    got_lex_diags = _diags_to_json(ldiags)
    exp_lex_diags = _read_json(case_dir / "expected.lex_diags.json")
    if got_lex_diags != exp_lex_diags:
        return CaseResult(case_id, "fail", {"stage": "lexer", "diff": "diagnostics"})

    if ldiags:
        return CaseResult(case_id, "pass", {"status": "lex_error"})

    # ---- parser
    pres = parse(toks, f"{case_id}.hand")
    got_parse_diags = _diags_to_json(pres.diagnostics)
    exp_parse_diags = _read_json(case_dir / "expected.parse_diags.json")
    if got_parse_diags != exp_parse_diags:
        return CaseResult(case_id, "fail", {"stage": "parser", "diff": "diagnostics"})
    if pres.diagnostics:
        return CaseResult(case_id, "pass", {"status": "parse_error"})

    got_ast = json.loads(json.dumps(pres.program, default=lambda o: o.__dict__, ensure_ascii=False))
    exp_ast = _read_json(case_dir / "expected.ast.json")
    if got_ast != exp_ast:
        return CaseResult(case_id, "fail", {"stage": "parser", "diff": "ast"})

    # ---- typecheck
    tdiags = typecheck(pres.program, f"{case_id}.hand")
    got_type_diags = _diags_to_json(tdiags)
    exp_type_diags = _read_json(case_dir / "expected.type_diags.json")
    if got_type_diags != exp_type_diags:
        return CaseResult(case_id, "fail", {"stage": "typecheck", "diff": "diagnostics"})
    if tdiags:
        return CaseResult(case_id, "pass", {"status": "type_error"})

    # ---- IR
    ir = lower_program(pres.program, module_name=m["name"], semver="0.1.0")
    exp_ir = _read_json(case_dir / "expected.ir.json")
    if ir != exp_ir:
        return CaseResult(case_id, "fail", {"stage": "lowering", "diff": "ir"})

    # ---- interpreter trace
    it = Interpreter(inputs=inputs)
    runtime_error=None
    try:
        rr = it.run(pres.program)
    except HandRuntimeError as e:
        runtime_error={"code": e.code, "message": e.message}
        rr = it._finalize()
    got_trace = {"outputs": rr.outputs, "events": [e.__dict__ for e in rr.trace], "runtime_error": runtime_error}
    exp_trace = _read_json(case_dir / "expected.trace.json")
    if got_trace != exp_trace:
        return CaseResult(case_id, "fail", {"stage": "interpreter", "diff": "trace"})

    # ---- python codegen equivalence
    py = gen_python(ir, module_name=m["name"])
    # Run generated python deterministically (same convention as generator uses)
    import subprocess, sys as _sys
    tmp = case_dir / "_gen_run.py"
    tmp.write_text(py, encoding="utf-8")
    arg = json.dumps(inputs, ensure_ascii=False)
    p = subprocess.run([_sys.executable, str(tmp), arg], capture_output=True, text=True)
    exp_py_run = _read_json(case_dir / "expected.python_run.json")
    if p.returncode != 0:
        got_py_run = {"rc": p.returncode, "stderr": p.stderr.strip(), "stdout": p.stdout.strip()}
    else:
        try:
            got_py_run = {"outputs": json.loads(p.stdout.strip())["outputs"]}
        except Exception:
            got_py_run = {"rc": p.returncode, "stdout": p.stdout[:200], "stderr": p.stderr[:200], "error": "bad_json"}

    if got_py_run != exp_py_run:
        return CaseResult(case_id, "fail", {"stage": "python_codegen", "diff": "python_run"})

    # Strong equivalence: outputs must match interpreter outputs for ok runs.
    if runtime_error is None:
        if got_py_run.get("outputs") != rr.outputs:
            return CaseResult(case_id, "fail", {"stage": "python_codegen", "diff": "outputs_mismatch"})

    return CaseResult(case_id, "pass", {"status": "ok" if runtime_error is None else "runtime_error"})


def run_all(conformance_dir: Path) -> List[CaseResult]:
    cases_dir = conformance_dir / "cases"
    results=[]
    for case_dir in sorted(cases_dir.iterdir()):
        if case_dir.is_dir():
            results.append(run_case(case_dir))
    return results


def semantic_coverage_report(manifest: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Count features only for cases that reach 'ok' or 'runtime_error' (i.e. typed successfully)
    cov={}
    typed=0
    for m in manifest:
        if m.get("status") in ("ok","runtime_error"):
            typed += 1
            for f in m.get("features") or []:
                cov[f]=cov.get(f,0)+1
    return {"typed_cases": typed, "feature_counts": dict(sorted(cov.items(), key=lambda x: (-x[1], x[0])))}
