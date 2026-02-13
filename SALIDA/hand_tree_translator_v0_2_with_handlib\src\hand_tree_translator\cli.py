from __future__ import annotations

import argparse

from .translate_tree import translate_tree, TreeTranslateOptions

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hand-tree-translate",
        description="Translate a folder tree into HAND (simple) and quarantine non-translatable files."
    )
    p.add_argument("--in", dest="in_root", required=True, help="Input folder root")
    p.add_argument("--out", dest="out_root", required=True, help="Output folder root")
    p.add_argument("--mode", choices=["safe", "raw"], default="safe",
                   help="safe: only translate supported subset; raw: wrap unsupported files into literal HAND blocks")
    p.add_argument("--no-translate-dirname", default="no_traducible",
                   help="Folder name inside --out where passthrough files are copied")
    p.add_argument("--no-emojis", action="store_true", help="Disable emojis in generated HAND")
    p.add_argument("--force", action="store_true", help="Overwrite output folder if it exists")

    args = p.parse_args(argv)

    opts = TreeTranslateOptions(
        mode=args.mode,
        force=args.force,
        emojis=(not args.no_emojis),
        no_translate_dirname=args.no_translate_dirname,
    )
    translate_tree(args.in_root, args.out_root, opts)
    return 0
