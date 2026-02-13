"""HAND Translation Library (extensible).

This package is intentionally *framework-first*: you can add new languages, new
HAND dialects, emoji/keyword layers, and compilation command models without
rewriting the tree-walker.

Key concepts:
  - Frontend: source code -> IR (handlib.types)
  - Backend:  IR -> HAND text (or HAND-IR JSON)
  - Registry: maps file types to frontends/backends + options
"""

from .registry import Registry, register_default
from .types import (
    Diagnostic, Severity, TranslationResult, SourceUnit,
    Node, Program, Stmt, Expr
)
from .lexicon import EmojiLexicon
