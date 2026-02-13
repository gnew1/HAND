from __future__ import annotations

import argparse
import sys

from .translate_tree import translate_tree


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hand-tree-translate", description="Translate a folder tree into simple HAND + quarantine non-translatable files.")
    p.add_argument("--in", dest="in_root", required=True, help="Input folder root")
    p.add_argument("--out", dest="out_root", required=True, help="Output folder root")
    p.add_argument("--include", action="append", default=None, help="Glob to include (repeatable). Default: **/*")
    p.add_argument("--exclude", action="append", default=None, help="Glob to exclude (repeatable). Adds to defaults.")
    p.add_argument("--force", action="store_true", help="Overwrite output folder if it exists")
    p.add_argument("--mode", choices=["safe", "raw"], default="safe", help="safe=translate supported subset only, raw=wrap everything as literal when needed")
    args = p.parse_args(argv)

    try:
        t, q, s = translate_tree(
            args.in_root,
            args.out_root,
            include=args.include,
            exclude=args.exclude,
            force=args.force,
            mode=args.mode,
        )
        print(f"OK. translated={t} quarantined={q} skipped={s}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
