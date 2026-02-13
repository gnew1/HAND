"""
Minimal HAND-ish formatter for the *simple HAND* output of this translator.

Rules (aligned with HAND docs):
- Indentation uses spaces only, multiples of 4.
- We generate sections: 🎬 PROGRAMA, 📦 ORIGEN, 🧩 COMPONENTES, ▶️ INICIAR, 🔧 FUNCIÓN...
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def _indent(lines: List[str], level: int) -> List[str]:
    prefix = " " * (4 * level)
    return [prefix + ln if ln else "" for ln in lines]


def hand_header(program_name: str, source_path: str, lang: str) -> List[str]:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return [
        f'🎬 PROGRAMA "{program_name}":',
        f'📦 ORIGEN "{source_path}":',
        f"    lang = {lang}",
        f"    generated_utc = {now}",
        "",
    ]


def hand_block(title: str, body: List[str], level: int = 0) -> List[str]:
    out = [f"{title}:"]
    out += _indent(body, level + 1)
    return out


def hand_code_literal(lang: str, code: str, level: int = 0) -> List[str]:
    # Use a visible literal block marker; this is a pragmatic choice for the translator.
    lines = [f'🧾 LITERAL lang="{lang}":']
    body = ["```", *code.splitlines(), "```"]
    lines += _indent(body, level + 1)
    return lines
