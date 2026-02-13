# HAND-IR v0.1 (stable) + lowering + origin tracing

This package defines a strict JSON Schema for HAND-IR v0.1, a lowering pass from HAND AST -> IR,
and validation tests (CI-style) that ensure produced IR conforms to the schema.

## Run validation tests
```bash
python -m pytest -q
```

## Generate IR from HAND source (example)
```python
from handc.interpreter import run_source
from handc.lexer import lex
from handc.parser import parse
from handc.lowering import lower_program

src = 'x: Int = 1\nshow x\n'
toks, diags = lex(src)
pres = parse(toks)
ir = lower_program(pres.program, module_name="main")
```
