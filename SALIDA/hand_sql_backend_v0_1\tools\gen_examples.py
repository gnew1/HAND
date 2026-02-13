import json, os
from pathlib import Path
from handc.lexer import lex
from handc.parser import parse
from handc.lowering import lower_program

def gen_one(path: Path):
    src=path.read_text(encoding="utf-8")
    toks, diags = lex(src, str(path))
    if diags:
        raise SystemExit("LEX ERROR: " + "\n".join(d.message_human for d in diags))
    pres = parse(toks, str(path))
    if pres.diagnostics:
        raise SystemExit("PARSE ERROR: " + "\n".join(d.message_human for d in pres.diagnostics))
    ir=lower_program(pres.program, module_name=path.stem)
    out=path.with_suffix(".ir.json")
    out.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

def main():
    exdir=Path("examples")
    for p in exdir.glob("*.hand"):
        gen_one(p)

if __name__=="__main__":
    main()
