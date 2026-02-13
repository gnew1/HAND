# HAND Conformance Suite (v0.1)

This directory is the **official** conformance suite for HAND Core v0.1.

## Layout

- `manifest.json`: list of all cases + declared features
- `cases/<NN_name>/program.hand`
- expected snapshots:
  - `expected.tokens.json`
  - `expected.ast.json` (if parses)
  - `expected.type_diags.json`
  - `expected.ir.json` (if typechecks)
  - `expected.trace.json` (if typechecks)
  - `expected.python_run.json` (if typechecks)

## Runner

The pytest suite calls `conformance.runner.run_all()` which runs:

lexer → parser → typechecker → lowering → interpreter → python codegen (equivalence)

## Coverage

`semantic_coverage_report()` aggregates features declared in `manifest.json`.
