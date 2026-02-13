from __future__ import annotations
import argparse
from pathlib import Path
from typing import List, Optional

from handc.lexer import lex
from handc.parser import parse
from handc.format import format_hand


def format_source(src: str, file_name: str = "<stdin>") -> str:
    toks, diags = lex(src, file_name)
    if diags:
        msgs = "\n".join([f"{getattr(d,'code','DIAG')}: {getattr(d,'message',d)}" for d in diags[:10]])
        raise SystemExit(f"handfmt: lex error(s)\n{msgs}")

    pres = parse(toks, file_name)
    if pres.diagnostics:
        msgs = "\n".join([f"{getattr(d,'code','DIAG')}: {getattr(d,'message',d)}" for d in pres.diagnostics[:10]])
        raise SystemExit(f"handfmt: parse error(s)\n{msgs}")

    return format_hand(pres.program)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="handfmt — canonical formatter for HAND")
    ap.add_argument("files", nargs="+", help=".hand files to format")
    ap.add_argument("--check", action="store_true", help="do not write; exit non-zero if changes would be made")
    ap.add_argument("--in-place", action="store_true", help="overwrite input files (default)")
    ap.add_argument("--out", default=None, help="write formatted output to a single file (only if one input)")
    args = ap.parse_args(argv)

    changed = 0
    for f in args.files:
        p = Path(f)
        src = p.read_text(encoding="utf-8")
        formatted = format_source(src, p.name)

        if formatted != src:
            changed += 1

        if args.check:
            continue

        if args.out:
            if len(args.files) != 1:
                raise SystemExit("--out requires a single input file")
            Path(args.out).write_text(formatted, encoding="utf-8")
        else:
            if not args.in_place and len(args.files) > 1:
                raise SystemExit("Multiple inputs require --in-place or --out")
            p.write_text(formatted, encoding="utf-8")

    if args.check and changed:
        print(f"handfmt: {changed} file(s) would change")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
