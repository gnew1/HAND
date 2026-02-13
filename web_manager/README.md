# HAND Control Center (Web)

Interfaz web para gestionar los proyectos de `SALIDA/` desde una sola página.

## Funciones

- Descubre carpetas de `SALIDA` y muestra acciones disponibles por proyecto.
- Ejecuta acciones comunes: ayuda de CLI, generación de ejemplos/snapshots y pruebas.
- Compila código HAND rápido usando `handc.py` (MVP) con targets `python/html/sql/rust/wasm`.
- Traduce árboles de archivos con `hand_tree_translator` (`safe` y `raw`).
- Mantiene una zona de trabajo con carpetas y archivos (`SALIDA/.web_manager/workspace`).
- Permite subir documentos, integrarlos, convertirlos a HAND y ejecutar archivos `.hand`.
- Incluye ayuda emergente por botón con explicación y confirmación de ejecución.
- Agrega menú de comandos comunes para ejecutar tareas frecuentes con tips previos.
- Incluye inserción rápida de snippets y paleta de emojis para el editor HAND.
- Suma una integración final del proyecto desde workspace en un solo botón.

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
- La conversión directa de documentos a HAND genera una versión textual ejecutable en `workspace/hand_zone`.
