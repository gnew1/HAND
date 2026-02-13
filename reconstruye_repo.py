#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
reconstruye_repo.py

Reconstruye un árbol de archivos/carpetas a partir de un PROGRAMA.txt
generado por exporta_programas.py (formato con BEGIN_FILE, CONTENT_START,
fence ```text, CONTENT_END, END_FILE).

Soluciona el bug típico de separadores:
- Si PROGRAMA.txt contiene rutas Windows con "\" y reconstruyes en Linux/macOS,
  "\" no es separador y se creaban archivos con el nombre literal "src\utils\a.py".
- Este script normaliza rutas: "\" y "/" -> "/" antes de crear Path.

Uso:
  python reconstruye_repo.py --in PROGRAMA.txt --out ./SALIDA

Opciones:
  --mode overwrite|skip|append   (default: overwrite)
  --dry-run                     (no escribe, solo reporta)
  --log reconstruccion.log      (default: reconstruccion.log)
"""

import os
import sys
import argparse
import time
from pathlib import Path
import traceback


BEGIN_PREFIX = "BEGIN_FILE:"
END_PREFIX = "END_FILE:"
CONTENT_START = "CONTENT_START"
CONTENT_END = "CONTENT_END"

FENCE_START_PREFIX = "```"  # puede ser ```text
FENCE_END = "```"


def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def make_writable(path: Path):
    """
    Intenta hacer writable el archivo (o carpeta) en Windows/Linux.
    """
    try:
        if not path.exists():
            return
        if path.is_dir():
            os.chmod(path, 0o777)
        else:
            os.chmod(path, 0o666)
    except Exception:
        pass


def atomic_write_text(dst: Path, text: str, retries: int = 3, sleep_s: float = 0.2):
    """
    Escribe a un temp y luego reemplaza. Reintenta ante PermissionError/OSError típicos.
    """
    parent = dst.parent
    safe_mkdir(parent)

    tmp = parent / (dst.name + ".tmp__writing__")

    last_err = None
    for i in range(retries):
        try:
            if tmp.exists():
                make_writable(tmp)
                tmp.unlink(missing_ok=True)

            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(text)

            if dst.exists():
                make_writable(dst)

            os.replace(tmp, dst)
            return

        except PermissionError as e:
            last_err = e
            make_writable(parent)
            make_writable(dst)
            make_writable(tmp)
            time.sleep(sleep_s * (i + 1))

        except OSError as e:
            last_err = e
            make_writable(parent)
            make_writable(dst)
            make_writable(tmp)
            time.sleep(sleep_s * (i + 1))

        except Exception as e:
            last_err = e
            break

    try:
        if tmp.exists():
            make_writable(tmp)
            tmp.unlink(missing_ok=True)
    except Exception:
        pass

    raise last_err if last_err else RuntimeError("atomic_write_text failed without exception?")


def parse_programa_txt(lines):
    """
    Genera tuplas (rel_path:str, content:str, note:str|None).
    Espera el formato:
      BEGIN_FILE: path
      ...
      CONTENT_START
      ```text
      ... contenido ...
      ```
      CONTENT_END
      END_FILE: path

    Ignora LANGUAGE/NOTE/etc.
    """
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].rstrip("\n")
        if line.startswith(BEGIN_PREFIX):
            rel_path = line[len(BEGIN_PREFIX):].strip()

            i += 1
            while i < n and lines[i].rstrip("\n") != CONTENT_START:
                i += 1
            if i >= n:
                yield rel_path, None, "ERROR: missing CONTENT_START"
                break

            i += 1  # línea después de CONTENT_START

            if i >= n:
                yield rel_path, None, "ERROR: unexpected EOF after CONTENT_START"
                break

            fence_line = lines[i].rstrip("\n")
            if not fence_line.startswith(FENCE_START_PREFIX):
                # tolerancia: sin fence, leer hasta CONTENT_END
                content_buf = []
                while i < n and lines[i].rstrip("\n") != CONTENT_END:
                    content_buf.append(lines[i])
                    i += 1
                content = "".join(content_buf)
            else:
                # saltar fence start (```text o similar)
                i += 1
                content_buf = []
                while i < n:
                    curr = lines[i].rstrip("\n")
                    if curr == FENCE_END:
                        break
                    content_buf.append(lines[i])
                    i += 1
                content = "".join(content_buf)

                # saltar fence end
                if i < n and lines[i].rstrip("\n") == FENCE_END:
                    i += 1

                # avanzar hasta CONTENT_END
                while i < n and lines[i].rstrip("\n") != CONTENT_END:
                    i += 1

            # saltar CONTENT_END si está
            if i < n and lines[i].rstrip("\n") == CONTENT_END:
                i += 1

            # buscar END_FILE (tolerante)
            found_end = False
            while i < n:
                l2 = lines[i].rstrip("\n")
                if l2.startswith(END_PREFIX):
                    found_end = True
                    i += 1
                    break
                if l2.startswith(BEGIN_PREFIX):
                    break
                i += 1

            if not found_end:
                yield rel_path, content, "WARN: missing END_FILE marker"
            else:
                yield rel_path, content, None

            continue

        i += 1


def normalize_rel_path(rel_path: str) -> str:
    """
    Normaliza rutas para que funcionen cross-platform:
    - convierte "\" y "/" a "/"
    - elimina prefijos ./ o .\
    - colapsa dobles separadores
    """
    rel_path = (rel_path or "").strip()

    if rel_path.startswith(".\\"):
        rel_path = rel_path[2:]
    if rel_path.startswith("./"):
        rel_path = rel_path[2:]

    # Normaliza separadores a "/"
    rel_path = rel_path.replace("\\", "/")

    # colapsar //
    while "//" in rel_path:
        rel_path = rel_path.replace("//", "/")

    return rel_path


def is_path_safe(rel_path: str) -> bool:
    """
    Evita path traversal: no permitir .. ni rutas absolutas.
    """
    try:
        p = Path(rel_path)
        if p.is_absolute():
            return False
        if any(part == ".." for part in p.parts):
            return False
        # Evitar rutas vacías o "." (sin archivo)
        if rel_path.strip() in ("", ".", "./"):
            return False
        return True
    except Exception:
        return False


def apply_mode(existing: Path, new_text: str, mode: str) -> str | None:
    """
    Devuelve el texto a escribir según modo, o None si no hay que escribir.
    """
    if mode == "skip" and existing.exists():
        return None
    if mode == "append" and existing.exists():
        try:
            old = existing.read_text(encoding="utf-8")
        except Exception:
            old = ""
        return old + new_text
    return new_text  # overwrite


def main():
    ap = argparse.ArgumentParser(description="Reconstruye repo desde PROGRAMA.txt")
    ap.add_argument("--in", dest="inp", default="PROGRAMA.txt",
                    help="Ruta a PROGRAMA.txt (default: PROGRAMA.txt)")
    ap.add_argument("--out", dest="out", required=True,
                    help="Carpeta de salida (raíz) donde reconstruir")
    ap.add_argument("--mode", choices=["overwrite", "skip", "append"], default="overwrite",
                    help="Qué hacer si el archivo existe (default: overwrite)")
    ap.add_argument("--dry-run", action="store_true",
                    help="No escribe nada, solo muestra lo que haría")
    ap.add_argument("--log", default="reconstruccion.log",
                    help="Archivo de log (default: reconstruccion.log)")
    ap.add_argument("--retries", type=int, default=3,
                    help="Reintentos por archivo ante bloqueo/permisos (default: 3)")
    args = ap.parse_args()

    inp = Path(args.inp)
    out_root = Path(args.out)

    if not inp.exists():
        print(f"ERROR: No existe el archivo de entrada: {inp}", file=sys.stderr)
        sys.exit(1)

    safe_mkdir(out_root)

    log_path = out_root / args.log

    def log(msg: str):
        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
        except Exception:
            pass

    # Leer manteniendo saltos de línea
    lines = inp.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    total = 0
    written = 0
    skipped = 0
    failed = 0

    log("=== START reconstruccion ===")
    log(f"INPUT: {inp.resolve()}")
    log(f"OUTPUT_ROOT: {out_root.resolve()}")
    log(f"MODE: {args.mode}  DRY_RUN: {args.dry_run}")
    log("")

    for rel_path, content, note in parse_programa_txt(lines):
        total += 1

        rel_path_norm = normalize_rel_path(rel_path)

        if not rel_path_norm or not is_path_safe(rel_path_norm):
            failed += 1
            log(f"[FAIL] Unsafe or empty path: {rel_path!r} -> {rel_path_norm!r}")
            continue

        if content is None:
            failed += 1
            log(f"[FAIL] Missing content for {rel_path_norm} ({note})")
            continue

        if note:
            log(f"[NOTE] {rel_path_norm}: {note}")

        dst = out_root / Path(rel_path_norm)

        text_to_write = apply_mode(dst, content, args.mode)
        if text_to_write is None:
            skipped += 1
            log(f"[SKIP] {rel_path_norm} (exists, mode=skip)")
            continue

        if args.dry_run:
            written += 1
            log(f"[DRY] Would write: {rel_path_norm} ({len(text_to_write)} chars)")
            continue

        try:
            atomic_write_text(dst, text_to_write, retries=args.retries)
            written += 1
            log(f"[OK] Wrote: {rel_path_norm} ({len(text_to_write)} chars)")
        except Exception as e:
            failed += 1
            log(f"[FAIL] {rel_path_norm}: {repr(e)}")
            log(traceback.format_exc())
            continue

    log("")
    log("=== SUMMARY ===")
    log(f"BLOCKS_PARSED: {total}")
    log(f"FILES_WRITTEN: {written}")
    log(f"FILES_SKIPPED: {skipped}")
    log(f"FILES_FAILED: {failed}")
    log("=== END ===")

    print(f"OK. total={total}, escritos={written}, omitidos={skipped}, fallidos={failed}")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
