from __future__ import annotations
from pathlib import Path
import json

from conformance.runner import run_all, semantic_coverage_report

REPO_ROOT = Path(__file__).resolve().parents[1]
CONF = REPO_ROOT / "conformance"

def test_conformance_all_cases():
    results = run_all(CONF)
    fails = [r for r in results if r.status != "pass"]
    assert not fails, "Conformance failures:\n" + "\n".join([f"{r.case_id}: {r.details}" for r in fails])

def test_semantic_coverage_report():
    manifest = json.loads((CONF/"manifest.json").read_text(encoding="utf-8"))
    rep = semantic_coverage_report(manifest)
    feats = rep["feature_counts"]
    # Core v0.1 (as implemented in this repo): show, if/else, while, verify, and basic types
    for f in ["show", "if", "while", "verify", "type:Int"]:
        assert f in feats, f"missing feature in coverage: {f}"
