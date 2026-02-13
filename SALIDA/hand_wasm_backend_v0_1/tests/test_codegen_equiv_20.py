import json, subprocess, sys, os
from pathlib import Path
import pytest

from handc.lexer import lex
from handc.parser import parse
from handc.lowering import lower_program
from handc.python_gen import gen_python
from handc.interpreter_ref import run_source as run_ref

REPO_ROOT = Path(__file__).resolve().parents[1]
PROG_DIR = REPO_ROOT / "tests" / "programs"

CASES = [
    ("p01_hello", []),
    ("p02_assign_show", []),
    ("p03_if_true", []),
    ("p04_if_false", []),
    ("p05_while_count", []),
    ("p06_arith", []),
    ("p07_bool_null", []),
    ("p08_compare", []),
    ("p09_function_add", []),
    ("p10_function_nested", []),
    ("p11_ask_echo", ["hola"]),
    ("p12_ask_concat", ["h", "i"]),
    ("p13_verify_ok", []),
    ("p14_while_with_if", []),
    ("p15_function_if", []),
    ("p16_shadowing", []),
    ("p17_text_plus", []),
    ("p18_float_ops", []),
    ("p19_multi_returns", []),
    ("p20_top_expr_call", []),]

def _compile_to_ir(src: str, name: str):
    toks, ldiags = lex(src, name)
    assert not ldiags
    pres = parse(toks, name)
    assert not pres.diagnostics
    return lower_program(pres.program, module_name=name)

def _run_generated(py_code: str, inputs):
    # Run in subprocess to avoid state bleed. Pass inputs as JSON arg.
    p = subprocess.run(
        [sys.executable, "-c", py_code, json.dumps(inputs, ensure_ascii=False)],
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout.strip() or "{}")
    return data["outputs"]

@pytest.mark.parametrize("name, inputs", CASES)
def test_codegen_python_equivalence(name, inputs, tmp_path):
    src = (PROG_DIR / f"{name}.hand").read_text(encoding="utf-8")

    # Reference interpreter (Ω)
    res = run_ref(src, inputs=list(inputs))
    out_ref = res.outputs

    # Lowering to IR
    ir = _compile_to_ir(src, name)

    # Generate Python
    py = gen_python(ir, module_name=name)

    # Run Python and compare Ω
    out_py = _run_generated(py, list(inputs))
    assert out_py == out_ref
