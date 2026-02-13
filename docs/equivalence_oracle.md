# Equivalence Oracle (Interpreter as Ground Truth) — HAND v0.1

## Observational equivalence (subset)

For the executable subset:

- Ω: ordered outputs produced by `show`
- Σ: final observable store (top-level/global frame)

`obs_eq(P, target) := Ω_target == Ω_ref AND Σ_target == Σ_ref`

The reference `Ω_ref, Σ_ref` are produced by `handc.interpreter.Interpreter`.

## Non-executable targets

In this repo:
- WASM backend emits **.wat** only (no runtime wired)
- SQL/HTML are **snapshot** targets

So the oracle reports a **DEGRADATION** and only checks codegen determinism.

## Usage

```bash
PYTHONPATH=src python equivalence_runner.py examples/audit_demo.hand --targets python,wasm,sql,html --level 2 --out equivalence_report.json
```
