# HAND Compiler (handc) — v0.1

HAND is a **human-readable, deterministic** language with a reference toolchain:

- **Lexer** (UTF-8, deterministic)
- **Parser** (indentation blocks)
- **Typechecker** (v0.1 types)
- **Reference Interpreter** (ground truth semantics)
- **HAND-IR** (JSON schema + lowering)
- **Capabilities/Effects enforcement**
- **Backends**: Python (equivalence-tested), WASM/SQL/HTML (snapshot/degraded v0.1)

This repository is the **reference implementation** of HAND Core v0.1 and the `handc` compiler CLI.

## Quickstart

### 1) Install (editable)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"
