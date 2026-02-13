from pathlib import Path
import json
import pytest
from handc.html_gen import gen_html

REPO_ROOT = Path(__file__).resolve().parents[1]
IR_DIR = REPO_ROOT / "tests" / "ir_html"
SNAP_DIR = REPO_ROOT / "tests" / "snapshots_html"

CASES = ["ask_show", "record_preview", "show_only"]

@pytest.mark.parametrize("name", CASES)
def test_html_snapshot(name):
    ir = json.loads((IR_DIR / f"{name}.json").read_text(encoding="utf-8"))
    html, notes = gen_html(ir)
    assert notes == []
    exp = (SNAP_DIR / f"{name}.html").read_text(encoding="utf-8")
    assert html == exp
