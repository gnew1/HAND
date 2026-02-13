# HAND v0.1 Reference Interpreter (Operational Semantics)

This repository provides a deterministic, auditable reference interpreter for HAND Core v0.1.
It is intended to be the "source of truth" for validating codegen targets.

## Run tests
```bash
python -m pytest -q
```

## Run a program
```python
from handc.interpreter import run_source

src = '''
🛠 add(a: Int, b: Int) -> Int:
    return a + b
x: Int = add(2, 3)
show x
'''
result = run_source(src, inputs=[])
print(result.outputs)   # ["5"]
print(result.trace_path)  # path to trace.json
```
