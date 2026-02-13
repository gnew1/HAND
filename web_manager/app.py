from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from flask import Flask, render_template, request


ROOT = Path(__file__).resolve().parents[1]
SALIDA = ROOT / "SALIDA"
TMP_DIR = SALIDA / ".web_manager"


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


app = Flask(__name__)


@app.get("/")
def index():
    projects = discover_projects()
    return render_template(
        "index.html",
        projects=projects,
        last_result=None,
        compile_result=None,
        translate_result=None,
        default_input="examples/hello.hand",
        default_out="SALIDA/.web_manager/out",
        default_translate_in="examples",
        default_translate_out="SALIDA/.web_manager/translated",
    )


@app.post("/run-action")
def run_action():
    projects = discover_projects()
    rel_path = request.form.get("project_path", "").strip()
    action_key = request.form.get("action_key", "").strip()
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

    return render_template(
        "index.html",
        projects=projects,
        last_result=last_result,
        compile_result=None,
        translate_result=None,
        default_input=request.form.get("default_input", "examples/hello.hand"),
        default_out=request.form.get("default_out", "SALIDA/.web_manager/out"),
        default_translate_in=request.form.get("default_translate_in", "examples"),
        default_translate_out=request.form.get("default_translate_out", "SALIDA/.web_manager/translated"),
    )


@app.post("/compile-hand")
def compile_hand():
    projects = discover_projects()
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

    return render_template(
        "index.html",
        projects=projects,
        last_result=None,
        compile_result=compile_result,
        translate_result=None,
        default_input=request.form.get("input_ref", "examples/hello.hand"),
        default_out=out_dir_raw,
        default_translate_in=request.form.get("default_translate_in", "examples"),
        default_translate_out=request.form.get("default_translate_out", "SALIDA/.web_manager/translated"),
    )


@app.post("/translate-tree")
def translate_tree():
    projects = discover_projects()
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

    return render_template(
        "index.html",
        projects=projects,
        last_result=None,
        compile_result=None,
        translate_result=translate_result,
        default_input=request.form.get("default_input", "examples/hello.hand"),
        default_out=request.form.get("default_out", "SALIDA/.web_manager/out"),
        default_translate_in=in_root,
        default_translate_out=out_root,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
