# HAND v0.1 MVP Compiler (handc)

This is a minimal, pragmatic compiler for a small subset of **HAND**.

## What works (v0.1 MVP)
- Indentation-based blocks (4 spaces per indent)
- Statements:
  - `program "Name":` (optional)
  - `function name(a,b):`
  - `x = expr`  (assignment)
  - `ask "Prompt" -> var`  (input)
  - `show expr`  (output)
  - `if cond:` / `else:`
  - `loop N times:`
  - `while cond:`
  - `return expr`
  - `call foo(a,b)` (or just `foo(a,b)`)

- Emojis are allowed as semantic markers and generally ignored by the parser:
  - `📤` (show), `📥` (ask), `🔧` (function), `🏁` (return) … etc.

## Targets
- `python`: **supported** (generates runnable `program.py`)
- `html`: **supported** as an explainable "spec view" (generates `program.html`)
- `sql`: **supported** as a stub that emits explicit SQL blocks only (generates `program.sql`)
- `rust`: stub placeholder
- `wasm`: stub placeholder (.wat)

## Run
```bash
python handc.py examples/hello.hand --target python --out dist --emit-ir dist/hello.ir.json
python dist/program.py
