# HAND Control Center (Web)

Interfaz web para gestionar los proyectos de `SALIDA/` desde una sola página.

## Funciones

- Descubre carpetas de `SALIDA` y muestra acciones disponibles por proyecto.
- Ejecuta acciones comunes: ayuda de CLI, generación de ejemplos/snapshots y pruebas.
- Compila código HAND rápido usando `handc.py` (MVP) con targets `python/html/sql/rust/wasm`.
- Traduce árboles de archivos con `hand_tree_translator` (`safe` y `raw`).

## Ejecutar

```bash
cd /workspaces/HAND
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python web_manager/app.py
```

Abrir en navegador:

- `http://localhost:8000`

## Notas

- La app ejecuta comandos locales con `subprocess` y muestra `stdout/stderr`.
- Los archivos temporales se guardan en `SALIDA/.web_manager/`.
- Para acciones que requieran dependencias específicas, instala en cada subproyecto con `pip install -e .`.
