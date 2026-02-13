#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
exporta_programas.py
Crea un PROGRAMA.txt con todos los archivos de código (human-friendly) dentro de la carpeta actual
y sus subcarpetas, incluyendo ruta relativa, lenguaje estimado y contenido completo.

Uso:
  python exporta_programas.py
Opcional:
  python exporta_programas.py --out PROGRAMA.txt --max-bytes 800000 --max-lines 20000
"""

import os
import sys
import argparse
from pathlib import Path

# Carpetas típicas de dependencias/build que suelen ser "ruido" para alimentar IA
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "bower_components",
    "dist", "build", "out", ".next", ".nuxt",
    ".venv", "venv", "env", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "target",  # rust
    "vendor",  # a veces dependencias
    ".idea", ".vscode",
}

# Extensiones típicas de código / configs útiles
EXT_TO_LANG = {
    ".py": "Python",
    ".pyw": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".env": "Env",
    ".xml": "XML",
    ".md": "Markdown",
    ".txt": "Text",
    ".dockerfile": "Dockerfile",
    "dockerfile": "Dockerfile",
    ".makefile": "Makefile",
    "makefile": "Makefile",
}

# Extensiones típicas binarias o de “ruido”
BINARY_EXTS = {
    ".exe", ".dll", ".so", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".pdf",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz",
    ".mp3", ".wav", ".mp4", ".mov", ".avi", ".mkv",
    ".ttf", ".otf", ".woff", ".woff2",
    ".bin", ".dat", ".class", ".pyc", ".pyo",
    ".wasm",
    ".db", ".sqlite", ".sqlite3",
}

# Heurística: si el archivo es minificado
def is_minified_name(name: str) -> bool:
    lower = name.lower()
    return (".min." in lower) or lower.endswith(".min.js") or lower.endswith(".min.css")

def guess_language(path: Path) -> str:
    name_lower = path.name.lower()
    ext_lower = path.suffix.lower()

    # casos especiales por nombre
    if name_lower == "dockerfile":
        return "Dockerfile"
    if name_lower == "makefile":
        return "Makefile"

    # por extensión normal
    if ext_lower in EXT_TO_LANG:
        return EXT_TO_LANG[ext_lower]

    # extensiones dobles raras
    if name_lower.endswith(".d.ts"):
        return "TypeScript Declarations"

    # fallback
    if ext_lower == "":
        # sin extensión: a veces scripts, configs
        return "Unknown (no extension)"
    return f"Unknown ({ext_lower})"

def should_skip_dir(dir_name: str, extra_excludes: set[str]) -> bool:
    return dir_name in DEFAULT_EXCLUDE_DIRS or dir_name in extra_excludes

def looks_binary_bytes(sample: bytes) -> bool:
    # Si hay NUL, casi seguro binario
    if b"\x00" in sample:
        return True
    # Cuenta caracteres "raros" fuera de rango habitual de texto
    # Permitimos UTF-8, pero una muestra con muchos bytes <9 o >127 no siempre es binario.
    # Nos basamos en ratio de bytes imprimibles/espacios/nuevas líneas.
    printable = 0
    for b in sample:
        if b in (9, 10, 13):  # tab, lf, cr
            printable += 1
        elif 32 <= b <= 126:
            printable += 1
    ratio = printable / max(1, len(sample))
    return ratio < 0.70

def read_text_safely(path: Path, max_bytes: int) -> tuple[str | None, str | None]:
    """
    Devuelve (texto, error). Si el archivo parece binario o excede max_bytes => (None, reason)
    """
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return None, f"SKIP: too large ({size} bytes > {max_bytes})"

        with open(path, "rb") as f:
            sample = f.read(min(8192, size))
            if looks_binary_bytes(sample):
                return None, "SKIP: looks binary / non-text"

        # Intentamos UTF-8 primero; si falla, probamos latin-1 como fallback “no ideal”
        try:
            text = path.read_text(encoding="utf-8")
            return text, None
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
            return text, "WARN: decoded with latin-1 (utf-8 failed)"
    except Exception as e:
        return None, f"SKIP: read error ({e})"

def count_lines(text: str) -> int:
    return text.count("\n") + 1

def likely_machine_or_library_dump(text: str) -> bool:
    """
    Heurística adicional para evitar “cosas enormes sin sentido humano”:
    - líneas extremadamente largas repetidas (minificado)
    - muy baja proporción de espacios/palabras frente a símbolos
    """
    if not text:
        return True

    # si hay líneas absurdamente largas (minificado o dumps)
    long_lines = 0
    for line in text.splitlines()[:200]:  # solo muestra inicial
        if len(line) > 2000:
            long_lines += 1
    if long_lines >= 2:
        return True

    # ratio simple de "caracteres alfabéticos" vs total
    total = len(text)
    alpha = sum(ch.isalpha() for ch in text)
    space = text.count(" ")
    # si es casi todo símbolos y nada de letras/espacios, sospechoso
    if (alpha / max(1, total) < 0.08) and (space / max(1, total) < 0.03):
        return True

    return False

def should_include_file(path: Path, max_bytes: int, max_lines: int) -> tuple[bool, str | None, str | None]:
    """
    Decide si incluir el archivo.
    Devuelve (include, text, note)
    """
    ext = path.suffix.lower()
    name = path.name

    if is_minified_name(name):
        return False, None, "SKIP: minified filename"

    if ext in BINARY_EXTS:
        return False, None, f"SKIP: binary ext {ext}"

    text, err = read_text_safely(path, max_bytes=max_bytes)
    if text is None:
        return False, None, err

    # límite de líneas
    lines = count_lines(text)
    if lines > max_lines:
        return False, None, f"SKIP: too many lines ({lines} > {max_lines})"

    if likely_machine_or_library_dump(text):
        return False, None, "SKIP: looks like minified/dump/library noise"

    return True, text, err  # err puede ser WARN

def iter_files(root: Path, extra_excludes: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        # filtra dirs in-place para que os.walk no entre
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d, extra_excludes)]

        for fn in filenames:
            yield Path(dirpath) / fn

def write_block(out_f, rel_path: str, language: str, note: str | None, content: str):
    sep = "=" * 90
    out_f.write(sep + "\n")
    out_f.write(f"BEGIN_FILE: {rel_path}\n")
    out_f.write(f"LANGUAGE: {language}\n")
    if note:
        out_f.write(f"NOTE: {note}\n")
    out_f.write("CONTENT_START\n")
    out_f.write("```text\n")
    out_f.write(content)
    if not content.endswith("\n"):
        out_f.write("\n")
    out_f.write("```\n")
    out_f.write("CONTENT_END\n")
    out_f.write(f"END_FILE: {rel_path}\n")
    out_f.write(sep + "\n\n")

def main():
    parser = argparse.ArgumentParser(description="Exporta código a PROGRAMA.txt para alimentar a una IA.")
    parser.add_argument("--out", default="PROGRAMA.txt", help="Nombre del archivo de salida (default: PROGRAMA.txt)")
    parser.add_argument("--max-bytes", type=int, default=800_000, help="Tamaño máximo por archivo (default: 800000 bytes)")
    parser.add_argument("--max-lines", type=int, default=20_000, help="Líneas máximas por archivo (default: 20000)")
    parser.add_argument("--exclude-dir", action="append", default=[], help="Añadir carpetas a excluir (puedes repetir)")
    args = parser.parse_args()

    root = Path.cwd()
    out_path = root / args.out
    extra_excludes = set(args.exclude_dir or [])

    written = 0
    skipped = 0

    with open(out_path, "w", encoding="utf-8") as out_f:
        out_f.write("# PROGRAMA.txt\n")
        out_f.write(f"# Root: {root}\n")
        out_f.write(f"# max_bytes={args.max_bytes}, max_lines={args.max_lines}\n")
        out_f.write(f"# excluded_dirs(default)={sorted(DEFAULT_EXCLUDE_DIRS)}\n")
        if extra_excludes:
            out_f.write(f"# excluded_dirs(extra)={sorted(extra_excludes)}\n")
        out_f.write("\n")

        for path in iter_files(root, extra_excludes):
            # No re-exportar el archivo de salida si está en la raíz
            try:
                if path.resolve() == out_path.resolve():
                    continue
            except Exception:
                pass

            rel_path = str(path.relative_to(root))
            language = guess_language(path)

            include, text, note = should_include_file(path, args.max_bytes, args.max_lines)
            if not include:
                skipped += 1
                continue

            write_block(out_f, rel_path=rel_path, language=language, note=note, content=text)
            written += 1

        out_f.write("\n")
        out_f.write("# SUMMARY\n")
        out_f.write(f"# INCLUDED_FILES: {written}\n")
        out_f.write(f"# SKIPPED_FILES: {skipped}\n")

    print(f"OK: generado {out_path} (incluidos={written}, omitidos={skipped})")

if __name__ == "__main__":
    main()
