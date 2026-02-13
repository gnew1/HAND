from __future__ import annotations
from pathlib import Path
import json
import subprocess
import sys
import os

REPO_ROOT = Path(__file__).resolve().parents[1]
PROG_DIR = REPO_ROOT / "tests" / "programs"

def run_handc(args, out_dir: Path):
    cmd = [sys.executable, "-m", "handc"] + args
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    p = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    rep_path = out_dir / "build_report.json"
    assert rep_path.exists(), f"build_report.json missing. rc={p.returncode}\nSTDERR:\n{p.stderr}"
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    return p.returncode, p.stdout, p.stderr, rep

def test_cli_python_ok(tmp_path: Path):
    out = tmp_path / "dist"
    rc, _o, _e, rep = run_handc(
        [str(PROG_DIR/"p02_assign_show.hand"), "--target", "python", "--out", str(out), "--emit-ir", "--emit-ast", "--json-diagnostics"],
        out,
    )
    assert rc == 0
    assert rep["status"] == "ok"
    assert (out/"main.py").exists()
    assert (out/"ir.json").exists()
    assert (out/"ast.json").exists()

def test_cli_wasm_pure_ok(tmp_path: Path):
    out = tmp_path / "dist"
    rc, _o, _e, rep = run_handc(
        [str(REPO_ROOT/"tests/programs_wasm/p01_add.hand"), "--target", "wasm", "--out", str(out)],
        out,
    )
    assert rc == 0
    assert rep["status"] == "ok"
    assert (out/"main.wat").exists()

def test_cli_sql_ok(tmp_path: Path):
    out = tmp_path / "dist"
    out.mkdir(parents=True, exist_ok=True)
    # Minimal show program is not supported by SQL backend; use empty program (no statements).
    src = out / "empty.hand"
    src.write_text("", encoding="utf-8")
    rc, _o, _e, rep = run_handc([str(src), "--target", "sql", "--out", str(out)], out)
    assert rc == 0
    assert rep["status"] == "ok"
    assert (out/"main.sql").exists()

def test_cli_html_ok(tmp_path: Path):
    out = tmp_path / "dist"
    out.mkdir(parents=True, exist_ok=True)
    src = out / "show.hand"
    src.write_text('show "hi"\n', encoding="utf-8")
    rc, _o, _e, rep = run_handc([str(src), "--target", "html", "--out", str(out)], out)
    assert rc == 0
    assert rep["status"] == "ok"
    assert (out/"index.html").exists()
