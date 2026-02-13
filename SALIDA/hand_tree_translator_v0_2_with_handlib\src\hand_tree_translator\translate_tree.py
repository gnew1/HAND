from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional

from .handlib import Registry, register_default
from .handlib.types import SourceUnit, TranslationResult

@dataclass
class TreeTranslateOptions:
    mode: str = "safe"          # safe | raw
    force: bool = False
    emojis: bool = True
    no_translate_dirname: str = "no_traducible"

def translate_tree(input_dir: str, output_dir: str, opts: Optional[TreeTranslateOptions] = None) -> None:
    opts = opts or TreeTranslateOptions()
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)
    no_dir = os.path.join(output_dir, opts.no_translate_dirname)

    if os.path.exists(output_dir):
        if not opts.force:
            raise FileExistsError(f"Output directory exists: {output_dir}. Use --force.")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(no_dir, exist_ok=True)

    reg = register_default(Registry())

    for root, _, files in os.walk(input_dir):
        rel_root = os.path.relpath(root, input_dir)
        for fn in files:
            in_path = os.path.join(root, fn)
            rel_path = os.path.normpath(os.path.join(rel_root, fn))
            out_path_raw = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(out_path_raw), exist_ok=True)

            handler = reg.handler_for_path(in_path)
            if handler is None:
                # unknown file type -> passthrough
                _copy_passthrough(in_path, os.path.join(no_dir, rel_path))
                continue

            # read
            try:
                text = open(in_path, "r", encoding="utf-8").read()
            except UnicodeDecodeError:
                _copy_passthrough(in_path, os.path.join(no_dir, rel_path))
                continue

            unit = SourceUnit(path=rel_path, language=handler.language, text=text)
            res: TranslationResult = handler.frontend(unit, handler.opts or {})

            if not res.ok:
                if opts.mode == "raw":
                    # Wrap original as literal HAND block
                    hand = _wrap_literal(unit, res.passthrough_reason or "unsupported")
                    _write_hand(out_path_raw + ".hand", hand)
                else:
                    _copy_passthrough(in_path, os.path.join(no_dir, rel_path))
                continue

            # backend
            if handler.backend is None:
                _copy_passthrough(in_path, os.path.join(no_dir, rel_path))
                continue

            res = handler.backend(res, {"lexicon": reg.lexicon, "use_emojis": opts.emojis})

            if not res.ok or not res.hand_text:
                if opts.mode == "raw":
                    hand = _wrap_literal(unit, res.passthrough_reason or "emit_failed")
                    _write_hand(out_path_raw + ".hand", hand)
                else:
                    _copy_passthrough(in_path, os.path.join(no_dir, rel_path))
                continue

            # write HAND + IR
            _write_hand(out_path_raw + ".hand", res.hand_text)
            _write_text(out_path_raw + ".handir.json", _json(res.hand_ir))

def _copy_passthrough(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)

def _write_hand(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def _wrap_literal(unit: SourceUnit, reason: str) -> str:
    # A minimal HAND "literal import" wrapper so we don't lose information.
    return (
        "# HAND raw wrapper (not fully translated)\n"
        f"# source: {unit.path} ({unit.language})\n"
        f"# reason: {reason}\n\n"
        "literal:\n"
        "  language: " + unit.language + "\n"
        "  code: |\n"
        + "\n".join("    " + line.rstrip("\n") for line in unit.text.splitlines())
        + "\n"
    )
