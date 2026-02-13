from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import yaml
from importlib import resources

@dataclass
class EmojiLexicon:
    """Mapping from semantic tags/keywords to emojis and vice-versa.

    This is the *main extension surface* for HAND emojis:
      - Add new layers (core, io, flow, types, async, crypto, etc.)
      - Reserve emojis for future evolution
      - Provide human descriptions and aliases

    File format: YAML.
    """
    data: Dict

    @classmethod
    def load_builtin(cls) -> "EmojiLexicon":
        with resources.files(__package__).joinpath("data/emoji_lexicon.yaml").open("r", encoding="utf-8") as f:
            return cls(yaml.safe_load(f))

    def emoji_for(self, tag: str, default: Optional[str] = None) -> Optional[str]:
        # tag can be "flow.if" or "io.print"
        layers = self.data.get("layers", {})
        for _, layer in layers.items():
            if tag in layer.get("tags", {}):
                return layer["tags"][tag]["emoji"]
        return default

    def description_for(self, tag: str, default: str = "") -> str:
        layers = self.data.get("layers", {})
        for _, layer in layers.items():
            if tag in layer.get("tags", {}):
                return layer["tags"][tag].get("desc", default)
        return default
