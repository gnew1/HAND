# Definition of Done — HAND compiler v0.1

A release is considered **Done** when:

## Core correctness
- Lexer is deterministic: same bytes → same tokens (all OS).
- Parser produces canonical AST; round-trip parse/format/parse passes.
- Typechecker implements Γ ⊢ e : T rules 1:1 with spec.
- Interpreter matches operational semantics and is treated as **source of truth**.

## Security
- Capabilities/effects enforcement denies undeclared IO/NET/FS, etc., per spec.
- Supervision levels 1–4 respected (fatal when required).

## IR
- Lowering produces HAND-IR v0.1.
- IR validates against `hand_ir.schema.json` in CI.

## Backends
- Python backend passes **equivalence** vs interpreter (Ω + Σ) for the oracle subset.
- Other targets either:
  - compile with correct output, OR
  - emit explicit degradations with human-readable reasons.

## Tooling
- `handc` CLI supports: target, out, level, emit-ast/ir/trace, json diagnostics.
- `handfmt` formats without semantic changes.
- `handfix` exists with stable interface (even if no rules yet).
- Conformance suite ≥ 60 cases.

## Release hygiene
- README, LICENSE present
- CI configured and passing
- Packaging via `pyproject.toml` works (pip install works)
