# Manual simple de uso — SALIDA

Este archivo consolida los programas reconstruidos dentro de `SALIDA/` y da una forma rápida de ejecutarlos.

## 0) Preparación general (una vez por proyecto)

En cada carpeta de proyecto:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Si el proyecto tiene extras de desarrollo:

```bash
pip install -e ".[dev]"
```

## 1) Script utilitario en raíz de SALIDA

### `SALIDA/exportaprogramas.py`

Genera un archivo `PROGRAMA.txt` desde una carpeta.

```bash
cd SALIDA
python exportaprogramas.py --help
python exportaprogramas.py --out PROGRAMA.txt
```

---

## 2) Proyectos y uso rápido

## `HAND_handc_v0_1_production_ready_repo_EXPERT`

Comandos principales (CLI instalada por `pyproject.toml`):

```bash
cd SALIDA/HAND_handc_v0_1_production_ready_repo_EXPERT
pip install -e ".[dev]"
handc --help
handfmt --help
handfix --help
hand-equivalence --help
python -m pytest -q
```

## `hand_auditability_trace_v0_1`

```bash
cd SALIDA/hand_auditability_trace_v0_1
pip install -e .
python -m handc.cli --help
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_conformance_suite_v0_1`

```bash
cd SALIDA/hand_conformance_suite_v0_1
pip install -e .
python -m handc.cli --help
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_conformance_suite_v0_1_with_cnl_translation`

```bash
cd SALIDA/hand_conformance_suite_v0_1_with_cnl_translation
pip install -e .
python -m handc.cli --help
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_equivalence_oracle_v0_1`

```bash
cd SALIDA/hand_equivalence_oracle_v0_1
pip install -e .
python -m handc.cli --help
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_html_backend_v0_1`

```bash
cd SALIDA/hand_html_backend_v0_1
pip install -e .
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_ir_capabilities_v0_1`

```bash
cd SALIDA/hand_ir_capabilities_v0_1
pip install -e .
python tools/gen_examples.py --help
python -m pytest -q
```

## `hand_language_evolution_v0_1`

```bash
cd SALIDA/hand_language_evolution_v0_1
pip install -e .
python -m handc.cli --help
python tools/handfmt.py --help
python tools/handfix.py --help
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_sql_backend_v0_1`

```bash
cd SALIDA/hand_sql_backend_v0_1
pip install -e .
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `hand_wasm_backend_v0_1`

```bash
cd SALIDA/hand_wasm_backend_v0_1
pip install -e .
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `handc_cli_toolchain_v0_1`

```bash
cd SALIDA/handc_cli_toolchain_v0_1
pip install -e .
python -m handc.cli --help
python tools/gen_examples.py --help
python _gen_snaps.py
python -m pytest -q
```

## `handc_interpreter_v0_1`

```bash
cd SALIDA/handc_interpreter_v0_1
pip install -e .
python -m pytest -q
```

## `hand_tree_translator`

CLI disponible como `hand-tree-translate`.

```bash
cd SALIDA/hand_tree_translator
pip install -e .
hand-tree-translate --help
```

## `hand_tree_translator_v0_2_with_handlib`

```bash
cd SALIDA/hand_tree_translator_v0_2_with_handlib
pip install -e .
hand-tree-translate --help
```

## 3) Variantes MVP anidadas

Estas tres carpetas contienen un MVP con ejecución directa por script `handc.py`:

- `SALIDA/handc_mvp/handc_mvp`
- `SALIDA/handc_lexer_v0_1/handc_mvp`
- `SALIDA/handc_parser_v0_1/handc_mvp`

Uso mínimo:

```bash
cd <ruta_de_la_variante_handc_mvp>
python handc.py examples/hello.hand --target python --out dist --emit-ir dist/hello.ir.json
python dist/program.py
```

---

## 4) Orden recomendado para empezar

1. Probar el compilador completo: `HAND_handc_v0_1_production_ready_repo_EXPERT`.
2. Probar traducción de árboles: `hand_tree_translator`.
3. Probar suites especializadas (`hand_*_v0_1`) con `pytest`.
4. Usar variantes `handc_mvp` para experimentación rápida.
