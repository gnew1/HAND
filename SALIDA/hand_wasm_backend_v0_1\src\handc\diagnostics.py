from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SrcLoc:
    file: str
    line: int
    col: int

@dataclass(frozen=True)
class Diagnostic:
    idref: str
    code: str
    severity: str  # "warning"|"error"|"fatal"
    message_human: str
    src: SrcLoc
    fix: Optional[str] = None

    def __str__(self) -> str:
        loc = f"{self.src.file}:{self.src.line}:{self.src.col}"
        fix = f" Fix: {self.fix}" if self.fix else ""
        return f"[{self.severity}] {self.idref} {self.code} {loc} {self.message_human}{fix}"
