# Contributing

## Dev setup
- Python 3.10+
- `pip install -e ".[dev]"`

## Quality gates (pre-PR)
- `pytest`
- `ruff check .`
- `mypy src` (optional)

## Rules
- Do not introduce synonyms in the lexicon.
- Changes to semantics MUST be accompanied by conformance tests.
- Interpreter is ground truth; Python backend must match Ω + Σ.
