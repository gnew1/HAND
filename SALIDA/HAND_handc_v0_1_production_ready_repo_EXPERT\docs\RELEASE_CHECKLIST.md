# Release checklist (v0.1.x)

## Preconditions
- All tests green locally: `pytest`
- CI green on main branch
- `handc --help` works
- Conformance suite runner completes
- Equivalence oracle passes for python target

## Steps
1. Bump version in `pyproject.toml` (and any internal `__version__` if added).
2. Update CHANGELOG (optional but recommended).
3. Run:
   - `ruff check .`
   - `pytest -q`
   - `python equivalence_runner.py examples/equiv_simple.hand --targets python --out _equiv.json`
4. Build distributions:
   - `python -m build`
5. Tag:
   - `git tag v0.1.X`
   - `git push --tags`
6. Publish (if desired):
   - `twine upload dist/*`

## Post-release
- Verify install from clean env.
- Verify CLI entrypoints: `handc`, `handfmt`, `handfix`.
