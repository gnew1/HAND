"""
Tree translator: folder -> HAND mirror + quarantine.

Design goals:
- deterministic output structure
- safe default behavior (only translate conservative subset)
- always keep originals for traceability (metadata in .hand header)
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .hand_format import hand_code_literal
from .python_subset import python_to_simple_hand, UnsupportedConstruct


DEFAULT_EXCLUDES = [
    "**/.git/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/.next/**",
    "**/target/**",
]


def _match_any(path: str, globs: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:12]


def _safe_read(p: Path) -> str:
    # try utf-8, fallback latin-1; if binary, raise
    data = p.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:
            raise ValueError("Binary or unknown encoding")


def _program_name_from_path(p: Path) -> str:
    # Stable, filesystem-safe label for PROGRAMA
    return p.stem


def translate_tree(
    in_root: str | Path,
    out_root: str | Path,
    *,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    force: bool = False,
    mode: str = "safe",
) -> Tuple[int, int, int]:
    """
    Returns (translated, quarantined, skipped).
    """
    in_root = Path(in_root).resolve()
    out_root = Path(out_root).resolve()
    include = include or ["**/*"]
    exclude = (exclude or []) + DEFAULT_EXCLUDES

    out_hand = out_root / "hand"
    out_quarantine = out_root / "no_traducible"

    if out_root.exists():
        if not force:
            raise FileExistsError(f"Output folder exists: {out_root} (use --force)")
        shutil.rmtree(out_root)

    out_hand.mkdir(parents=True, exist_ok=True)
    out_quarantine.mkdir(parents=True, exist_ok=True)

    translated = quarantined = skipped = 0

    for p in sorted(in_root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(in_root)
        rel_posix = rel.as_posix()

        if not _match_any(rel_posix, include):
            skipped += 1
            continue
        if _match_any(rel_posix, exclude):
            skipped += 1
            continue

        suffix = p.suffix.lower()
        try:
            if suffix == ".py":
                src = _safe_read(p)
                try:
                    hand = python_to_simple_hand(src, program_name=_program_name_from_path(p), source_path=rel_posix)
                    out_path = (out_hand / rel).with_suffix(".hand")
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(hand, encoding="utf-8")
                    translated += 1
                except UnsupportedConstruct as e:
                    if mode == "raw":
                        # Wrap original as literal in HAND
                        hand_lines = []
                        hand_lines.append(f'🎬 PROGRAMA "{_program_name_from_path(p)}":')
                        hand_lines.append(f'📦 ORIGEN "{rel_posix}":')
                        hand_lines.append(f"    lang = python")
                        hand_lines.append(f"    note = raw_mode_unsupported_construct:{type(e).__name__}")
                        hand_lines.append("")
                        hand_lines += hand_code_literal("python", src)
                        out_path = (out_hand / rel).with_suffix(".hand")
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text("\n".join(hand_lines).rstrip() + "\n", encoding="utf-8")
                        translated += 1
                    else:
                        # quarantine
                        q = out_quarantine / rel
                        q.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, q)
                        quarantined += 1
            else:
                # Other languages: quarantine by default (safe), or wrap as literal in raw mode
                if mode == "raw":
                    try:
                        src = _safe_read(p)
                        hand_lines = []
                        hand_lines.append(f'🎬 PROGRAMA "{_program_name_from_path(p)}":')
                        hand_lines.append(f'📦 ORIGEN "{rel_posix}":')
                        hand_lines.append(f"    lang = {suffix.lstrip('.') or 'unknown'}")
                        hand_lines.append("")
                        hand_lines += hand_code_literal(suffix.lstrip(".") or "unknown", src)
                        out_path = (out_hand / rel).with_suffix(".hand")
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text("\n".join(hand_lines).rstrip() + "\n", encoding="utf-8")
                        translated += 1
                    except Exception:
                        q = out_quarantine / rel
                        q.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, q)
                        quarantined += 1
                else:
                    q = out_quarantine / rel
                    q.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, q)
                    quarantined += 1
        except Exception:
            # if anything odd happens, quarantine to avoid data loss
            q = out_quarantine / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
            quarantined += 1

    # Write a small report
    report = out_root / "report.txt"
    report.write_text(
        f"in_root: {in_root}\nout_root: {out_root}\nmode: {mode}\n"
        f"translated: {translated}\nquarantined: {quarantined}\nskipped: {skipped}\n",
        encoding="utf-8",
    )
    return translated, quarantined, skipped
