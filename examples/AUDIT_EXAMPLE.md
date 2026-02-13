# Audit demo: "de dónde salió cada línea"

Build:
```bash
python -m handc.cli examples/audit_demo.hand --target python --out dist_audit --emit-trace --origin-actor 👤
```

Look at:
- `dist_audit/audit_demo.py` : generated Python. Lines produced from HAND statements include an inline origin comment: `# [AST]...`
- `dist_audit/trace.json` : machine-readable mapping of `line_no -> ref`.
- `trace_event.schema.json` : schema for `trace.json`.
