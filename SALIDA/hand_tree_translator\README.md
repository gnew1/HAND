# hand-tree-translator

CLI tool that walks an input folder tree and produces:

- `out/hand/` : `.hand` files (a **simple HAND** representation) mirroring the directory structure.
- `out/no_traducible/` : original files we could not translate (or that you chose to quarantine).

It tries a *safe* translator first:
- **Python** (via built-in `ast`) for a conservative subset: assignments, if/else, while, for, function defs, returns, basic expressions, and `print()` → `show`.

Everything else is copied to `no_traducible/` unchanged.

## Install (editable)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
