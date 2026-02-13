from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple, Any

from .types import SourceUnit, TranslationResult
from .lexicon import EmojiLexicon

FrontendFn = Callable[[SourceUnit, Dict[str, Any]], TranslationResult]
BackendFn  = Callable[[TranslationResult, Dict[str, Any]], TranslationResult]

@dataclass
class Handler:
    language: str
    frontend: FrontendFn
    backend: Optional[BackendFn] = None
    opts: Dict[str, Any] = None

class Registry:
    """Maps file extensions to translation handlers."""
    def __init__(self, lexicon: Optional[EmojiLexicon] = None):
        self.lexicon = lexicon or EmojiLexicon.load_builtin()
        self._by_ext: Dict[str, Handler] = {}

    def register_ext(self, ext: str, handler: Handler):
        if not ext.startswith("."):
            ext = "." + ext
        self._by_ext[ext.lower()] = handler

    def handler_for_path(self, path: str) -> Optional[Handler]:
        import os
        _, ext = os.path.splitext(path)
        return self._by_ext.get(ext.lower())

# -------- default wiring --------
def register_default(reg: Registry):
    # Python subset -> IR -> HAND simple
    from .frontends.python_ast import translate_python
    from .backends.hand_simple import emit_hand_simple

    reg.register_ext(".py", Handler(
        language="python",
        frontend=translate_python,
        backend=emit_hand_simple,
        opts={"subset": "v0"}
    ))
    return reg
