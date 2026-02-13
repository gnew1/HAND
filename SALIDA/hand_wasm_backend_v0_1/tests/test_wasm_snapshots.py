from pathlib import Path
import pytest

from handc.lexer import lex
from handc.parser import parse
from handc.lowering import lower_program
from handc.wasm_gen import gen_wat

REPO_ROOT = Path(__file__).resolve().parents[1]
PROG_DIR = REPO_ROOT / "tests" / "programs_wasm"
SNAP_DIR = REPO_ROOT / "tests" / "snapshots"

CASES = ["p01_add","p02_fact","p03_if","p04_call","p05_bool"]

def _ir_from_hand(src: str, name: str):
    toks, ldiags = lex(src, name)
    assert not ldiags
    pres = parse(toks, name)
    assert not pres.diagnostics
    return lower_program(pres.program, module_name=name)

@pytest.mark.parametrize("name", CASES)
def test_wasm_wat_snapshot(name):
    src = (PROG_DIR / f"{name}.hand").read_text(encoding="utf-8")
    ir = _ir_from_hand(src, name)
    wat, notes = gen_wat(ir)
    assert notes == []
    exp_path = SNAP_DIR / f"{name}.wat"
    assert exp_path.exists()
    assert wat == exp_path.read_text(encoding="utf-8")
