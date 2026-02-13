from __future__ import annotations
from pathlib import Path
import subprocess, sys, os

REPO = Path(__file__).resolve().parents[1]

def run(cmd):
    env={**os.environ, "PYTHONPATH": str(REPO/"src")}
    return subprocess.run([sys.executable]+cmd, cwd=REPO, capture_output=True, text=True, env=env)

def test_handfmt_check_pass(tmp_path: Path):
    p = tmp_path/"a.hand"
    p.write_text('x: Int = 1\nshow x\n', encoding="utf-8")
    r = run(["tools/handfmt.py", str(p), "--check"])
    assert r.returncode == 0

def test_handfmt_check_detects_change(tmp_path: Path):
    p = tmp_path/"a.hand"
    p.write_text('x:Int=1\nshow    x\n', encoding="utf-8")
    r = run(["tools/handfmt.py", str(p), "--check"])
    assert r.returncode != 0
