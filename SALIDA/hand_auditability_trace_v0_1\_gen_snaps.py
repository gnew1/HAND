from pathlib import Path
from handc.lexer import lex
from handc.parser import parse
from handc.lowering import lower_program
from handc.wasm_gen import gen_wat

root = Path(__file__).resolve().parent
prog_dir = root/"tests"/"programs_wasm"
snap_dir = root/"tests"/"snapshots"
snap_dir.mkdir(parents=True, exist_ok=True)

for p in sorted(prog_dir.glob("*.hand")):
    name = p.stem
    src = p.read_text(encoding="utf-8")
    toks, di = lex(src, name)
    assert not di
    pres = parse(toks, name)
    assert not pres.diagnostics
    ir = lower_program(pres.program, module_name=name)
    wat, notes = gen_wat(ir)
    assert notes == []
    (snap_dir/f"{name}.wat").write_text(wat, encoding="utf-8")
print("snapshots generated")
