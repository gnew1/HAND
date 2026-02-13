# HAND-IR v0.1 (stable) + lowering + origin tracing

This package defines a strict JSON Schema for HAND-IR v0.1, a lowering pass from HAND AST -> IR,
and validation tests (CI-style) that ensure produced IR conforms to the schema.

## Run validation tests
```bash
python -m pytest -q
