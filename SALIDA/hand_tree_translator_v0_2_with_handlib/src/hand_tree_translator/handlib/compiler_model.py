"""Compilation model for HAND.

Goal:
  Describe how source files map to compileable HAND units and which commands
  (build/run/test/package) are valid.

This is NOT a build system. It's a neutral "plan" representation so:
  - the translator can emit metadata (what is runnable, what is library code)
  - a future 'handc' compiler can consume it
  - you can support multi-language projects (py/js/go/etc.) progressively

Extend by:
  - adding new Toolchain adapters (e.g., node, python, rust)
  - adding new Artifact kinds (module, package, wasm, docker, etc.)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class CommandSpec:
    name: str                 # e.g. "run", "test", "build"
    argv: List[str]           # e.g. ["handc","build","./main.hand"]
    cwd: Optional[str] = None
    env: Dict[str,str] = field(default_factory=dict)
    description: str = ""

@dataclass
class Artifact:
    kind: str                 # "hand.module", "hand.package", "asset"
    path: str                 # output path
    entrypoint: Optional[str] = None
    commands: List[CommandSpec] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)

@dataclass
class ProjectPlan:
    artifacts: List[Artifact] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
