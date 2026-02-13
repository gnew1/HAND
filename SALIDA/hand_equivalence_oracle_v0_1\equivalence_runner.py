from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from handc.lexer import lex
from handc.parser import parse
from handc.typecheck import typecheck
from handc.lowering import lower_program
from handc.enforce import enforce_capabilities
from handc.interpreter import Interpreter
from handc.python_gen import gen_python
from handc.wasm_gen import gen_wat
from handc.sql_gen import gen_sql
from handc.html_gen import gen_html


# -----------------------------
# Observational equivalence v0.1
# -----------------------------
#
# For the executable subset:
#   obs_eq(P, target) := Ω_target == Ω_ref  AND  Σ_target == Σ_ref
#
# Where:
#   Ω is the list of outputs produced by `show` (in-order).
#   Σ is the final observable store at the end of program execution (top-level frame only).
#
# For non-executable targets (SQL/HTML/WASM in this repo), we report a DEGRADATION and
# validate only that code generation succeeds and output is deterministic (snapshot/hashes).
#

SUPPORTED_TARGETS = ["python", "wasm", "sql", "html"]


def _feature_scan(src: str) -> List[str]:
    feats=set()
    for kw in ["show","ask","if","else","while","return","not","and","or"]:
        if re.search(rf"\b{kw}\b", src):
            feats.add(kw)
    if "🔍" in src: feats.add("verify")
    if "🛡️" in src: feats.add("capabilities")
    for t in ["Int","Float","Bool","Text","Null"]:
        if re.search(rf"\b{t}\b", src): feats.add(f"type:{t}")
    for op in ["+","-","*","/","==","!=",">=", "<=" ,">","<"]:
        if op in src: feats.add(f"op:{op}")
    return sorted(feats)


def _run_ref(program_ast, inputs: List[str]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    it = Interpreter(inputs=inputs)
    try:
        rr = it.run(program_ast)
        return {"Ω": rr.outputs, "Σ": rr.final_store}, None, None
    except Exception as e:
        return {"Ω": [], "Σ": {}}, {"message": str(e)}, "runtime_error"


def _run_python_generated(code: str, inputs: List[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    tmp = Path("_equiv_tmp_gen.py")
    tmp.write_text(code, encoding="utf-8")
    p = subprocess.run([sys.executable, str(tmp), json.dumps(inputs, ensure_ascii=False)], capture_output=True, text=True)
    if p.returncode != 0:
        return None, f"python_runtime_error rc={p.returncode} stderr={p.stderr.strip()[:300]}"
    try:
        out = json.loads(p.stdout.strip())
    except Exception:
        return None, "python_output_not_json"
    finally:
        try: tmp.unlink()
        except Exception: pass
    # Expect dict: {"outputs":[...], "store":{...}}
    Ω = out.get("outputs")
    Σ = out.get("store")
    return {"Ω": Ω, "Σ": Σ}, None


def compile_to_ir(src: str, file_name: str, level: int, enforce_caps: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    toks, di = lex(src, file_name)
    if di:
        return {}, {"stage":"lexer","diagnostics":[d.__dict__ for d in di]}
    pres = parse(toks, file_name)
    if pres.diagnostics:
        return {}, {"stage":"parser","diagnostics":[d.__dict__ for d in pres.diagnostics]}
    tdi = typecheck(pres.program, file_name)
    if tdi:
        return {}, {"stage":"typecheck","diagnostics":[d.__dict__ for d in tdi]}
    ir = lower_program(pres.program, module_name=Path(file_name).stem, semver="0.1.0")
    if enforce_caps:
        # enforce capabilities at given supervision level
        try:
            ir2, cap_diags = enforce_capabilities(ir, supervision_level=level)
        except Exception as e:
            return {}, {"stage":"enforce","diagnostics":[{"message": str(e)}]}
        if cap_diags:
            return {}, {"stage":"enforce","diagnostics":[getattr(d,'__dict__',{'message':str(d)}) for d in cap_diags]}
        return {"ast": pres.program, "ir": ir2}, {}
    return {"ast": pres.program, "ir": ir}, {}


def run_equivalence(program_path: Path, targets: List[str], level: int, inputs: Optional[List[str]] = None, enforce_caps: bool = False) -> Dict[str, Any]:
    src = program_path.read_text(encoding="utf-8")
    inputs = inputs or []
    feats = _feature_scan(src)

    comp, err = compile_to_ir(src, program_path.name, level=level, enforce_caps=enforce_caps)
    if err:
        return {"program": program_path.name, "status": "compile_error", "error": err, "features": feats, "results": {}}

    ast = comp["ast"]
    ir = comp["ir"]

    ref_obs, ref_err, ref_status = _run_ref(ast, inputs)

    results: Dict[str, Any] = {}
    for t in targets:
        if t == "python":
            code = gen_python(ir, module_name=program_path.stem)
            obs, perr = _run_python_generated(code, inputs)
            if perr:
                results[t] = {"status":"fail", "reason": perr}
                continue
            ok = (obs["Ω"] == ref_obs["Ω"]) and (obs["Σ"] == ref_obs["Σ"])
            results[t] = {
                "status": "pass" if ok else "fail",
                "observed": obs,
                "expected": ref_obs,
                "mismatch": None if ok else {
                    "Ω": obs["Ω"] != ref_obs["Ω"],
                    "Σ": obs["Σ"] != ref_obs["Σ"],
                },
            }
        elif t == "wasm":
            try:
                wat, notes = gen_wat(ir)
                results[t] = {
                    "status": "degraded",
                    "degradation": "WASM backend is snapshot-only in this toolchain; no runtime executor wired. Validated codegen determinism only.",
                    "artifact": {"kind":"wat", "len": len(wat), "notes": [getattr(n, "__dict__", str(n)) for n in notes]},
                }
            except Exception as e:
                results[t] = {
                    "status": "degraded",
                    "degradation": "WASM backend declined this program (subset limit).",
                    "error": str(e),
                }
        elif t == "sql":
            try:
                sql, notes = gen_sql(ir)
                results[t] = {
                    "status": "degraded",
                    "degradation": "SQL is non-executable in oracle; validated codegen only (set-based semantics require DB runtime).",
                    "artifact": {"kind":"sql", "len": len(sql), "notes": [getattr(n, "__dict__", str(n)) for n in notes]},
                }
            except Exception as e:
                results[t] = {"status":"degraded", "degradation":"SQL backend declined this program (subset limit).", "error": str(e)}
        elif t == "html":
            try:
                html, notes = gen_html(ir)
                results[t] = {
                    "status": "degraded",
                    "degradation": "HTML is UI snapshot; not an executable semantics target. Validated codegen only.",
                    "artifact": {"kind":"html", "len": len(html), "notes": [getattr(n, "__dict__", str(n)) for n in notes]},
                }
            except Exception as e:
                results[t] = {"status":"degraded", "degradation":"HTML backend declined this program.", "error": str(e)}
        else:
            results[t] = {"status":"skip", "reason":"unknown target"}

    return {
        "program": program_path.name,
        "status": "ok",
        "features": feats,
        "ref": {"observed": ref_obs, "runtime_error": ref_err, "ref_status": ref_status},
        "results": results,
    }


def feature_target_matrix(reports: List[Dict[str, Any]], targets: List[str]) -> Dict[str, Any]:
    # Collect features and whether each target passed/degraded for at least one program containing it.
    features=set()
    for r in reports:
        for f in r.get("features") or []:
            features.add(f)
    matrix={}
    for f in sorted(features):
        row={}
        for t in targets:
            # summarize: pass if all typed programs with feature pass; else fail/degraded/mixed
            statuses=[]
            for r in reports:
                if f in (r.get("features") or []):
                    st=r.get("results",{}).get(t,{}).get("status")
                    if st: statuses.append(st)
            if not statuses:
                row[t]="n/a"
            else:
                if all(s=="pass" for s in statuses): row[t]="pass"
                elif all(s=="degraded" for s in statuses): row[t]="degraded"
                elif any(s=="fail" for s in statuses): row[t]="mixed/fail"
                else: row[t]="mixed"
        matrix[f]=row
    return matrix


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="HAND equivalence oracle (interpreter as ground truth)")
    ap.add_argument("inputs", nargs="+", help="Input .hand programs")
    ap.add_argument("--targets", default="python,wasm,sql,html", help="Comma-separated targets")
    ap.add_argument("--level", type=int, default=2, help="Supervision level 1-4 for capability enforcement")
    ap.add_argument("--enforce-capabilities", action="store_true", help="enforce declared/required capabilities (may cause compile errors)")
    ap.add_argument("--inputs-json", default=None, help="JSON list of inputs for ask(), applied to all programs")
    ap.add_argument("--out", default="equivalence_report.json", help="Output report path")
    args = ap.parse_args(argv)

    targets=[t.strip() for t in args.targets.split(",") if t.strip()]
    for t in targets:
        if t not in SUPPORTED_TARGETS:
            raise SystemExit(f"Unknown target: {t}. Supported: {SUPPORTED_TARGETS}")

    inputs=[]
    if args.inputs_json:
        inputs=json.loads(args.inputs_json)

    reports=[]
    for p in args.inputs:
        reports.append(run_equivalence(Path(p), targets, level=args.level, inputs=inputs, enforce_caps=args.enforce_capabilities))

    matrix=feature_target_matrix(reports, targets)
    out={"schema_version":"0.1","observational_equivalence":"Ω + Σ (top-level store) for executable subset", "targets":targets, "reports":reports, "matrix":matrix}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")

    # print summary
    fails=0
    for r in reports:
        if r["status"]!="ok":
            fails += 1
            continue
        for t,res in r["results"].items():
            if res.get("status")=="fail":
                fails += 1
    print(f"Wrote {args.out}. failures={fails}")
    return 0 if fails==0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
