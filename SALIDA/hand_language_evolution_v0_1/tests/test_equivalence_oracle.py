from __future__ import annotations
from pathlib import Path
import json
import subprocess, sys, os

REPO = Path(__file__).resolve().parents[1]

def run(cmd):
    env={**os.environ, "PYTHONPATH": str(REPO/"src")}
    p=subprocess.run([sys.executable]+cmd, cwd=REPO, capture_output=True, text=True, env=env)
    assert p.returncode in (0,2)
    return p

def test_equivalence_python_pass(tmp_path: Path):
    out = tmp_path/"rep.json"
    p = run(["equivalence_runner.py", "examples/equiv_simple.hand", "--targets", "python", "--out", str(out)])
    rep=json.loads(out.read_text(encoding="utf-8"))
    r=rep["reports"][0]
    assert r["status"]=="ok"
    assert r["results"]["python"]["status"]=="pass"
