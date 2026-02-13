# Extending the HAND Tree Translator

This repo is split into **tree-walking** and **translation library** (`handlib/`).

## 1) Add emojis / keywords
Edit: `src/hand_tree_translator/handlib/data/emoji_lexicon.yaml`

- Add a new layer (e.g. `types`, `async`, `crypto`)
- Map semantic tags like `types.int`, `async.await` to emojis
- Emitters can choose to include emojis (`--emojis`) or not.

## 2) Add a new language
Implement a new **frontend**:
- Create `handlib/frontends/<lang>.py`
- Implement: `translate_<lang>(unit: SourceUnit, opts: dict) -> TranslationResult`
- Produce `hand_ir` as a Program node tree (or dict)

Register it:
```python
from hand_tree_translator.handlib import Registry
from hand_tree_translator.handlib.registry import Handler

reg.register_ext(".js", Handler(language="javascript", frontend=translate_js, backend=emit_hand_simple))
