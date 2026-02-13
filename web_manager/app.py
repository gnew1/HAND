from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Dict, List

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename


ROOT = Path(__file__).resolve().parents[1]
SALIDA = ROOT / "SALIDA"
TMP_DIR = SALIDA / ".web_manager"
WORKSPACE_DIR = TMP_DIR / "workspace"
UPLOADS_DIR = WORKSPACE_DIR / "uploads"
HAND_ZONE_DIR = WORKSPACE_DIR / "hand_zone"
TRANSLATED_DIR = TMP_DIR / "translated"
RUNS_DIR = TMP_DIR / "runs"


@dataclass
class Action:
    key: str
    label: str
    command: List[str]
    cwd: Path
    env: Dict[str, str]
    description: str


@dataclass
class ProjectInfo:
    name: str
    rel_path: str
    abs_path: Path
    actions: List[Action]


def _ensure_dirs() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    HAND_ZONE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATED_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_workspace_path(rel_path: str) -> Path:
    rel = (rel_path or "").strip().replace("\\", "/")
    rel = rel.lstrip("/")
    target = (WORKSPACE_DIR / rel).resolve()
    base = WORKSPACE_DIR.resolve()
    if target != base and base not in target.parents:
        raise ValueError("Ruta fuera de workspace")
    return target


def _list_workspace_entries() -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for path in sorted(WORKSPACE_DIR.rglob("*")):
        rel = str(path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
        if path.is_dir():
            entries.append({"type": "dir", "rel": rel, "size": "-"})
        else:
            try:
                size = str(path.stat().st_size)
            except OSError:
                size = "?"
            entries.append({"type": "file", "rel": rel, "size": size})
    return entries[:500]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _escape_hand_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _text_to_hand(doc_name: str, text: str) -> str:
    clean_name = _escape_hand_text(doc_name or "Documento")
    lines = [line.rstrip() for line in text.splitlines()]
    lines = lines[:200]

    hand_lines = [f'program "{clean_name}":']
    if not lines:
        hand_lines.append('    show "Documento vacío"')
        return "\n".join(hand_lines) + "\n"

    hand_lines.append('    show "Contenido integrado:"')
    for line in lines:
        if line:
            hand_lines.append(f'    show "{_escape_hand_text(line[:300])}"')
    return "\n".join(hand_lines) + "\n"


def _run_command(command: List[str], cwd: Path, env_extra: Dict[str, str] | None = None, timeout: int = 180):
    started = time.time()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    if env_extra:
        env.update(env_extra)

    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        ended = time.time()
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": round(ended - started, 2),
            "command": " ".join(shlex.quote(part) for part in command),
            "cwd": str(cwd),
        }
    except subprocess.TimeoutExpired as exc:
        ended = time.time()
        return {
            "ok": False,
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nTimeout: {timeout}s",
            "duration": round(ended - started, 2),
            "command": " ".join(shlex.quote(part) for part in command),
            "cwd": str(cwd),
        }


def _project_actions(project_dir: Path) -> List[Action]:
    actions: List[Action] = []
    py = ["python"]
    src_handc = project_dir / "src" / "handc"
    src_tree = project_dir / "src" / "hand_tree_translator"
    env_src = {"PYTHONPATH": "src"}

    if (src_handc / "cli.py").exists():
        actions.append(
            Action(
                key="handc_help",
                label="Ver ayuda handc",
                command=py + ["-m", "handc.cli", "--help"],
                cwd=project_dir,
                env=env_src,
                description="Muestra todas las opciones del compilador CLI.",
            )
        )

    if (src_tree / "cli.py").exists():
        actions.append(
            Action(
                key="translator_help",
                label="Ver ayuda traductor",
                command=py + ["-m", "hand_tree_translator.cli", "--help"],
                cwd=project_dir,
                env=env_src,
                description="Muestra opciones del traductor de árboles de archivos.",
            )
        )

    if (project_dir / "tools" / "gen_examples.py").exists():
        actions.append(
            Action(
                key="gen_examples_help",
                label="Ayuda gen_examples",
                command=py + ["tools/gen_examples.py", "--help"],
                cwd=project_dir,
                env={},
                description="Muestra opciones para generar ejemplos/snapshots.",
            )
        )

    if (project_dir / "tools" / "handfmt.py").exists():
        actions.append(
            Action(
                key="handfmt_help",
                label="Ayuda handfmt",
                command=py + ["tools/handfmt.py", "--help"],
                cwd=project_dir,
                env={},
                description="Muestra opciones de formateo HAND.",
            )
        )

    if (project_dir / "tools" / "handfix.py").exists():
        actions.append(
            Action(
                key="handfix_help",
                label="Ayuda handfix",
                command=py + ["tools/handfix.py", "--help"],
                cwd=project_dir,
                env={},
                description="Muestra opciones de corrección automática.",
            )
        )

    if (project_dir / "_gen_snaps.py").exists():
        actions.append(
            Action(
                key="gen_snaps",
                label="Ejecutar snapshots",
                command=py + ["_gen_snaps.py"],
                cwd=project_dir,
                env={},
                description="Regenera snapshots de referencia del proyecto.",
            )
        )

    if (project_dir / "tests").exists():
        actions.append(
            Action(
                key="pytest",
                label="Ejecutar pruebas",
                command=py + ["-m", "pytest", "-q"],
                cwd=project_dir,
                env=env_src if (project_dir / "src").exists() else {},
                description="Ejecuta la suite de pruebas del proyecto.",
            )
        )

    handc_mvp = project_dir / "handc_mvp" / "handc.py"
    if handc_mvp.exists():
        actions.append(
            Action(
                key="mvp_help",
                label="Ayuda handc.py (MVP)",
                command=py + [str(handc_mvp.relative_to(project_dir)), "--help"],
                cwd=project_dir,
                env={},
                description="Muestra opciones del compilador MVP por script.",
            )
        )

    return actions


def discover_projects() -> List[ProjectInfo]:
    if not SALIDA.exists():
        return []

    projects: List[ProjectInfo] = []
    for child in sorted(SALIDA.iterdir()):
        if not child.is_dir():
            continue
        actions = _project_actions(child)
        projects.append(
            ProjectInfo(
                name=child.name,
                rel_path=str(child.relative_to(ROOT)),
                abs_path=child,
                actions=actions,
            )
        )
    return projects


def find_action(projects: List[ProjectInfo], rel_path: str, action_key: str) -> Action | None:
    for project in projects:
        if project.rel_path == rel_path:
            for action in project.actions:
                if action.key == action_key:
                    return action
    return None


def locate_default_compiler() -> Path | None:
    candidates = [
        SALIDA / "handc_mvp" / "handc_mvp" / "handc.py",
        SALIDA / "handc_lexer_v0_1" / "handc_mvp" / "handc.py",
        SALIDA / "handc_parser_v0_1" / "handc_mvp" / "handc.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def locate_translator_project() -> Path | None:
    candidates = [
        SALIDA / "hand_tree_translator",
        SALIDA / "hand_tree_translator_v0_2_with_handlib",
    ]
    for candidate in candidates:
        if (candidate / "src" / "hand_tree_translator" / "cli.py").exists():
            return candidate
    return None


def discover_common_commands() -> List[Action]:
    actions: List[Action] = []
    py = ["python"]

    if (ROOT / "src" / "handc" / "cli.py").exists():
        actions.append(
            Action(
                key="common_handc_help",
                label="Ayuda compilador HAND (CLI)",
                command=py + ["-m", "handc.cli", "--help"],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                description="Muestra todas las banderas del compilador HAND principal.",
            )
        )

    translator_project = locate_translator_project()
    if translator_project is not None:
        actions.append(
            Action(
                key="common_translator_help",
                label="Ayuda traductor de árbol",
                command=py + ["-m", "hand_tree_translator.cli", "--help"],
                cwd=translator_project,
                env={"PYTHONPATH": "src"},
                description="Muestra la ayuda del traductor para modo safe/raw.",
            )
        )

    if (ROOT / "tests").exists():
        actions.append(
            Action(
                key="common_pytest",
                label="Ejecutar pruebas rápidas",
                command=py + ["-m", "pytest", "-q"],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                description="Corre la suite de pruebas para validar cambios.",
            )
        )

    if (ROOT / "_gen_snaps.py").exists():
        actions.append(
            Action(
                key="common_snaps",
                label="Regenerar snapshots",
                command=py + ["_gen_snaps.py"],
                cwd=ROOT,
                env={},
                description="Actualiza snapshots de referencia del repositorio.",
            )
        )

    actions.append(
        Action(
            key="common_list_workspace",
            label="Listar workspace HAND",
            command=["find", str(WORKSPACE_DIR), "-maxdepth", "3"],
            cwd=ROOT,
            env={},
            description="Lista carpetas y archivos temporales de trabajo en web manager.",
        )
    )

    return actions


def find_common_action(actions: List[Action], action_key: str) -> Action | None:
    for action in actions:
        if action.key == action_key:
            return action
    return None


app = Flask(__name__)


def _render_page(
    *,
    last_result=None,
    compile_result=None,
    translate_result=None,
    workspace_result=None,
    hand_exec_result=None,
    selected_file_rel="",
    selected_file_content="",
    default_input="examples/hello.hand",
    default_out="SALIDA/.web_manager/out",
    default_translate_in="examples",
    default_translate_out="SALIDA/.web_manager/translated",
):
    _ensure_dirs()
    projects = discover_projects()
    common_commands = discover_common_commands()
    workspace_entries = _list_workspace_entries()
    return render_template(
        "index.html",
        projects=projects,
        common_commands=common_commands,
        last_result=last_result,
        compile_result=compile_result,
        translate_result=translate_result,
        workspace_result=workspace_result,
        hand_exec_result=hand_exec_result,
        selected_file_rel=selected_file_rel,
        selected_file_content=selected_file_content,
        workspace_entries=workspace_entries,
        default_input=default_input,
        default_out=default_out,
        default_translate_in=default_translate_in,
        default_translate_out=default_translate_out,
    )


@app.get("/")
def index():
    _ensure_dirs()
    selected = request.args.get("file", "").strip()
    content = ""
    if selected:
        try:
            selected_path = _safe_workspace_path(selected)
            if selected_path.exists() and selected_path.is_file():
                content = _read_text(selected_path)
        except Exception:
            selected = ""
            content = ""

    return _render_page(
        selected_file_rel=selected,
        selected_file_content=content,
    )


@app.post("/run-action")
def run_action():
    rel_path = request.form.get("project_path", "").strip()
    action_key = request.form.get("action_key", "").strip()
    projects = discover_projects()
    action = find_action(projects, rel_path, action_key)

    if action is None:
        last_result = {
            "ok": False,
            "returncode": 404,
            "stdout": "",
            "stderr": "Acción no encontrada. Recarga la página e intenta de nuevo.",
            "duration": 0,
            "command": "",
            "cwd": rel_path,
            "title": "Error",
        }
    else:
        run = _run_command(action.command, action.cwd, action.env)
        run["title"] = f"{Path(rel_path).name} · {action.label}"
        last_result = run

    return _render_page(
        last_result=last_result,
        default_input=request.form.get("default_input", "examples/hello.hand"),
        default_out=request.form.get("default_out", "SALIDA/.web_manager/out"),
        default_translate_in=request.form.get("default_translate_in", "examples"),
        default_translate_out=request.form.get("default_translate_out", "SALIDA/.web_manager/translated"),
    )


@app.post("/run-common-command")
def run_common_command():
    action_key = request.form.get("common_action_key", "").strip()
    actions = discover_common_commands()
    action = find_common_action(actions, action_key)

    if action is None:
        result = {
            "ok": False,
            "returncode": 404,
            "stdout": "",
            "stderr": "Comando común no encontrado. Recarga la página e intenta de nuevo.",
            "duration": 0,
            "command": "",
            "cwd": str(ROOT),
            "title": "Comando común",
        }
    else:
        run = _run_command(action.command, action.cwd, action.env)
        run["title"] = f"Comando común · {action.label}"
        result = run

    return _render_page(last_result=result)


@app.post("/compile-hand")
def compile_hand():
    hand_source = request.form.get("hand_source", "").strip()
    target = request.form.get("target", "python").strip()
    out_dir_raw = request.form.get("out_dir", "SALIDA/.web_manager/out").strip()
    run_python = request.form.get("run_python") == "on"

    compiler = locate_default_compiler()
    if compiler is None:
        compile_result = {
            "ok": False,
            "title": "Compilación HAND",
            "command": "",
            "cwd": str(ROOT),
            "stdout": "",
            "stderr": "No se encontró handc.py en las variantes MVP dentro de SALIDA.",
            "duration": 0,
            "returncode": 404,
        }
    else:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        source_file = TMP_DIR / "program_input.hand"
        source_file.write_text(hand_source if hand_source else "show \"hola\"\n", encoding="utf-8")

        out_dir = Path(out_dir_raw)
        if not out_dir.is_absolute():
            out_dir = ROOT / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        ir_file = out_dir / "program.ir.json"
        compile_cmd = [
            "python",
            str(compiler),
            str(source_file),
            "--target",
            target,
            "--out",
            str(out_dir),
            "--emit-ir",
            str(ir_file),
        ]
        compile_run = _run_command(compile_cmd, ROOT)
        stdout = compile_run["stdout"]
        stderr = compile_run["stderr"]

        if compile_run["ok"] and target == "python" and run_python:
            program_file = out_dir / "program.py"
            run_cmd = ["python", str(program_file)]
            run_exec = _run_command(run_cmd, ROOT)
            stdout += "\n\n=== Ejecución de program.py ===\n" + run_exec["stdout"]
            stderr += "\n\n=== stderr program.py ===\n" + run_exec["stderr"]

        compile_result = {
            **compile_run,
            "title": "Compilación HAND",
            "stdout": stdout,
            "stderr": stderr,
        }

    return _render_page(
        compile_result=compile_result,
        default_input=request.form.get("input_ref", "examples/hello.hand"),
        default_out=out_dir_raw,
        default_translate_in=request.form.get("default_translate_in", "examples"),
        default_translate_out=request.form.get("default_translate_out", "SALIDA/.web_manager/translated"),
    )


@app.post("/translate-tree")
def translate_tree():
    in_root = request.form.get("in_root", "examples").strip()
    out_root = request.form.get("translate_out", "SALIDA/.web_manager/translated").strip()
    mode = request.form.get("mode", "safe").strip()
    force = request.form.get("force") == "on"

    translator_project = locate_translator_project()
    if translator_project is None:
        translate_result = {
            "ok": False,
            "title": "Traducción de árbol",
            "command": "",
            "cwd": str(ROOT),
            "stdout": "",
            "stderr": "No se encontró proyecto hand_tree_translator en SALIDA.",
            "duration": 0,
            "returncode": 404,
        }
    else:
        in_path = Path(in_root)
        if not in_path.is_absolute():
            in_path = ROOT / in_path

        out_path = Path(out_root)
        if not out_path.is_absolute():
            out_path = ROOT / out_path

        cmd = [
            "python",
            "-m",
            "hand_tree_translator.cli",
            "--in",
            str(in_path),
            "--out",
            str(out_path),
            "--mode",
            mode,
        ]
        if force:
            cmd.append("--force")

        run = _run_command(cmd, translator_project, env_extra={"PYTHONPATH": "src"})
        translate_result = {
            **run,
            "title": "Traducción de árbol",
        }

    return _render_page(
        translate_result=translate_result,
        default_input=request.form.get("default_input", "examples/hello.hand"),
        default_out=request.form.get("default_out", "SALIDA/.web_manager/out"),
        default_translate_in=in_root,
        default_translate_out=out_root,
    )


@app.post("/workspace/create-folder")
def workspace_create_folder():
    folder_rel = request.form.get("folder_rel", "").strip()
    try:
        target = _safe_workspace_path(folder_rel)
        target.mkdir(parents=True, exist_ok=True)
        result = {
            "ok": True,
            "title": "Crear carpeta",
            "command": f"mkdir -p {folder_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": f"Carpeta creada: {folder_rel}",
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Crear carpeta",
            "command": f"mkdir -p {folder_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
    return _render_page(workspace_result=result)


@app.post("/workspace/create-file")
def workspace_create_file():
    file_rel = request.form.get("file_rel", "").strip()
    content = request.form.get("file_content", "")
    try:
        target = _safe_workspace_path(file_rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        result = {
            "ok": True,
            "title": "Crear archivo",
            "command": f"write {file_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": f"Archivo guardado: {file_rel}",
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Crear archivo",
            "command": f"write {file_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
    return _render_page(workspace_result=result, selected_file_rel=file_rel, selected_file_content=content)


@app.post("/workspace/open-file")
def workspace_open_file():
    file_rel = request.form.get("selected_file_rel", "").strip()
    content = ""
    result = None
    try:
        target = _safe_workspace_path(file_rel)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError("No existe el archivo seleccionado")
        content = _read_text(target)
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Abrir archivo",
            "command": f"open {file_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
        file_rel = ""
    return _render_page(workspace_result=result, selected_file_rel=file_rel, selected_file_content=content)


@app.post("/workspace/save-file")
def workspace_save_file():
    file_rel = request.form.get("selected_file_rel", "").strip()
    content = request.form.get("selected_file_content", "")
    try:
        target = _safe_workspace_path(file_rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        result = {
            "ok": True,
            "title": "Guardar archivo",
            "command": f"save {file_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": f"Archivo actualizado: {file_rel}",
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Guardar archivo",
            "command": f"save {file_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
    return _render_page(workspace_result=result, selected_file_rel=file_rel, selected_file_content=content)


@app.post("/workspace/delete")
def workspace_delete():
    path_rel = request.form.get("path_rel", "").strip()
    try:
        target = _safe_workspace_path(path_rel)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        result = {
            "ok": True,
            "title": "Eliminar",
            "command": f"delete {path_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": f"Eliminado: {path_rel}",
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Eliminar",
            "command": f"delete {path_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
    return _render_page(workspace_result=result)


@app.post("/workspace/upload")
def workspace_upload():
    _ensure_dirs()
    uploaded_files = request.files.getlist("documents")
    uploaded_names = []
    for file_obj in uploaded_files:
        if not file_obj or not file_obj.filename:
            continue
        safe_name = secure_filename(file_obj.filename)
        if not safe_name:
            continue
        out = UPLOADS_DIR / safe_name
        file_obj.save(out)
        uploaded_names.append(safe_name)

    if uploaded_names:
        result = {
            "ok": True,
            "title": "Subida de documentos",
            "command": "upload documents",
            "cwd": str(UPLOADS_DIR),
            "stdout": "Subidos: " + ", ".join(uploaded_names),
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
    else:
        result = {
            "ok": False,
            "title": "Subida de documentos",
            "command": "upload documents",
            "cwd": str(UPLOADS_DIR),
            "stdout": "",
            "stderr": "No se recibieron archivos válidos.",
            "duration": 0,
            "returncode": 1,
        }

    return _render_page(workspace_result=result)


@app.post("/workspace/convert-to-hand")
def workspace_convert_to_hand():
    source_rel = request.form.get("source_rel", "").strip()
    output_rel = request.form.get("output_rel", "hand_zone/imported.hand").strip()
    try:
        source = _safe_workspace_path(source_rel)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError("El documento origen no existe")
        text = _read_text(source)
        hand_code = _text_to_hand(source.name, text)

        output = _safe_workspace_path(output_rel)
        if output.suffix.lower() != ".hand":
            output = output.with_suffix(".hand")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(hand_code, encoding="utf-8")

        rel_out = str(output.relative_to(WORKSPACE_DIR)).replace("\\", "/")
        result = {
            "ok": True,
            "title": "Convertir a HAND",
            "command": f"convert {source_rel} -> {rel_out}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": f"Generado HAND: {rel_out}",
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
        return _render_page(workspace_result=result, selected_file_rel=rel_out, selected_file_content=hand_code)
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Convertir a HAND",
            "command": f"convert {source_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
        return _render_page(workspace_result=result)


@app.post("/workspace/translate-uploaded")
def workspace_translate_uploaded():
    mode = request.form.get("mode", "raw").strip()
    mode = mode if mode in {"safe", "raw"} else "raw"
    translator_project = locate_translator_project()
    if translator_project is None:
        result = {
            "ok": False,
            "title": "Traducir documentos subidos",
            "command": "translator",
            "cwd": str(ROOT),
            "stdout": "",
            "stderr": "No se encontró proyecto hand_tree_translator en SALIDA.",
            "duration": 0,
            "returncode": 404,
        }
        return _render_page(workspace_result=result)

    cmd = [
        "python",
        "-m",
        "hand_tree_translator.cli",
        "--in",
        str(UPLOADS_DIR),
        "--out",
        str(TRANSLATED_DIR),
        "--mode",
        mode,
        "--force",
    ]
    run = _run_command(cmd, translator_project, env_extra={"PYTHONPATH": "src"})
    run["title"] = "Traducir documentos subidos"
    return _render_page(workspace_result=run)


@app.post("/workspace/run-hand")
def workspace_run_hand():
    hand_rel = request.form.get("hand_rel", "").strip()
    target = request.form.get("target", "python").strip()
    run_python = request.form.get("run_python") == "on"

    compiler = locate_default_compiler()
    if compiler is None:
        result = {
            "ok": False,
            "title": "Ejecutar HAND",
            "command": "handc.py",
            "cwd": str(ROOT),
            "stdout": "",
            "stderr": "No se encontró compilador handc.py en SALIDA.",
            "duration": 0,
            "returncode": 404,
        }
        return _render_page(hand_exec_result=result)


@app.post("/workspace/integrate-project")
def workspace_integrate_project():
    _ensure_dirs()
    integrated_rel = "hand_zone/proyecto_integrado.hand"
    integrated_path = _safe_workspace_path(integrated_rel)
    integrated_path.parent.mkdir(parents=True, exist_ok=True)

    hand_files = sorted(HAND_ZONE_DIR.rglob("*.hand"))
    uploaded_files = sorted(path for path in UPLOADS_DIR.rglob("*") if path.is_file())

    hand_lines = ['program "Integración Final":', '    show "Proyecto integrado HAND"']
    hand_lines.append(f'    show "Archivos HAND detectados: {len(hand_files)}"')
    for file_path in hand_files[:40]:
        rel = str(file_path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
        hand_lines.append(f'    show "HAND: {_escape_hand_text(rel)}"')

    hand_lines.append(f'    show "Documentos subidos: {len(uploaded_files)}"')
    for file_path in uploaded_files[:40]:
        rel = str(file_path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
        preview = ""
        try:
            raw_text = _read_text(file_path)
            preview = (raw_text.splitlines()[0] if raw_text else "").strip()
        except Exception:
            preview = ""
        if preview:
            preview = preview[:70]
            line = f"DOC: {rel} :: {preview}"
        else:
            line = f"DOC: {rel}"
        hand_lines.append(f'    show "{_escape_hand_text(line)}"')

    integrated_code = "\n".join(hand_lines) + "\n"
    integrated_path.write_text(integrated_code, encoding="utf-8")

    compiler = locate_default_compiler()
    if compiler is None:
        result = {
            "ok": True,
            "title": "Integración final del proyecto",
            "command": "integrate workspace",
            "cwd": str(WORKSPACE_DIR),
            "stdout": f"Se generó {integrated_rel}, pero no se encontró handc.py para compilar.",
            "stderr": "",
            "duration": 0,
            "returncode": 0,
        }
        return _render_page(hand_exec_result=result, selected_file_rel=integrated_rel, selected_file_content=integrated_code)

    out_dir = RUNS_DIR / "proyecto_integrado"
    out_dir.mkdir(parents=True, exist_ok=True)
    ir_file = out_dir / "program.ir.json"

    compile_cmd = [
        "python",
        str(compiler),
        str(integrated_path),
        "--target",
        "python",
        "--out",
        str(out_dir),
        "--emit-ir",
        str(ir_file),
    ]
    compile_run = _run_command(compile_cmd, ROOT)
    stdout = f"Archivo integrado generado: {integrated_rel}\n\n" + compile_run["stdout"]
    stderr = compile_run["stderr"]

    if compile_run["ok"]:
        run_py = _run_command(["python", str(out_dir / "program.py")], ROOT)
        stdout += "\n\n=== Ejecución de proyecto integrado ===\n" + run_py["stdout"]
        stderr += "\n\n=== stderr ejecución integrada ===\n" + run_py["stderr"]

    result = {
        **compile_run,
        "title": "Integración final del proyecto",
        "stdout": stdout,
        "stderr": stderr,
    }
    return _render_page(hand_exec_result=result, selected_file_rel=integrated_rel, selected_file_content=integrated_code)

    try:
        source = _safe_workspace_path(hand_rel)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError("No existe el archivo HAND seleccionado")
        out_dir = RUNS_DIR / source.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        ir_file = out_dir / "program.ir.json"

        compile_cmd = [
            "python",
            str(compiler),
            str(source),
            "--target",
            target,
            "--out",
            str(out_dir),
            "--emit-ir",
            str(ir_file),
        ]
        compile_run = _run_command(compile_cmd, ROOT)
        stdout = compile_run["stdout"]
        stderr = compile_run["stderr"]

        if compile_run["ok"] and target == "python" and run_python:
            run_py = _run_command(["python", str(out_dir / "program.py")], ROOT)
            stdout += "\n\n=== Ejecución de program.py ===\n" + run_py["stdout"]
            stderr += "\n\n=== stderr program.py ===\n" + run_py["stderr"]

        result = {
            **compile_run,
            "title": f"Ejecutar HAND: {hand_rel}",
            "stdout": stdout,
            "stderr": stderr,
        }
        selected_content = _read_text(source)
        return _render_page(hand_exec_result=result, selected_file_rel=hand_rel, selected_file_content=selected_content)
    except Exception as exc:
        result = {
            "ok": False,
            "title": "Ejecutar HAND",
            "command": f"run {hand_rel}",
            "cwd": str(WORKSPACE_DIR),
            "stdout": "",
            "stderr": str(exc),
            "duration": 0,
            "returncode": 1,
        }
        return _render_page(hand_exec_result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
