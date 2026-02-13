from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from handc.lexer import lex
from handc.parser import parse
from handc.format import format_hand

# -----------------------
# handfix codemod framework
# -----------------------
#
# v0.1 ships a *stub* with the stable interface.
# Future versions add rules under `RULES` and implement AST pattern transforms.
#

@dataclass
class FixChange:
    rule_id: str
    file: str
    message: str
    changed: bool


def _parse_program(src: str, file_name: str):
    toks, diags = lex(src, file_name)
    if diags:
        return None, {"stage":"lexer","diagnostics":[getattr(d,'__dict__',{'message':str(d)}) for d in diags]}
    pres = parse(toks, file_name)
    if pres.diagnostics:
        return None, {"stage":"parser","diagnostics":[getattr(d,'__dict__',{'message':str(d)}) for d in pres.diagnostics]}
    return pres.program, {}


# Placeholder registry (future releases populate this)
RULES: List[Any] = []


def apply_fixes(src: str, file_name: str, from_version: str, to_version: str) -> Dict[str, Any]:
    program, err = _parse_program(src, file_name)
    if err:
        return {"status":"error", "error": err, "changes":[]}

    changes: List[FixChange] = []
    new_program = program

    # v0.1: no transformations shipped; framework only.
    # Future: iterate RULES and transform new_program, append changes.

    out_src = format_hand(new_program)
    return {
        "status": "ok",
        "from": from_version,
        "to": to_version,
        "changes": [c.__dict__ for c in changes],
        "output": out_src,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="handfix — codemod/migration tool for HAND")
    ap.add_argument("file", help=".hand file")
    ap.add_argument("--from", dest="from_version", default="0.1.0", help="source version")
    ap.add_argument("--to", dest="to_version", default="0.1.0", help="target version")
    ap.add_argument("--out", default=None, help="write migrated file (default: overwrite input)")
    ap.add_argument("--report", default=None, help="write JSON report of applied fixes")
    ap.add_argument("--check", action="store_true", help="exit non-zero if changes would be made")
    args = ap.parse_args(argv)

    p = Path(args.file)
    src = p.read_text(encoding="utf-8")
    rep = apply_fixes(src, p.name, args.from_version, args.to_version)
    if rep["status"] != "ok":
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 2

    out_src = rep["output"]
    changed = out_src != src

    if args.report:
        Path(args.report).write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")

    if args.check:
        return 2 if changed else 0

    out_path = Path(args.out) if args.out else p
    out_path.write_text(out_src, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
