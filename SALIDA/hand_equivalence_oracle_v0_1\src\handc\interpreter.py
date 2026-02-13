from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import pathlib

from .lexer import lex
from .parser import parse
from . import ast as A

# -------------------------
# Trace model (auditability)
# -------------------------

@dataclass
class TraceEvent:
    step: int
    kind: str                      # "enter_stmt", "exit_stmt", "eval_expr", "io", "assign", "call", "return", "error"
    detail: Dict[str, Any]

@dataclass
class RunResult:
    outputs: List[str]
    final_store: Dict[str, Any]
    trace: List[TraceEvent]
    trace_path: str

# -------------------------
# Runtime errors
# -------------------------

class HandRuntimeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code=code
        self.message=message

class _ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value=value

# -------------------------
# Environment / Store (Σ)
# -------------------------

@dataclass
class Store:
    # Σ: mutable variable bindings per scope stack (each frame is a dict)
    frames: List[Dict[str, Any]]

    def get(self, name: str) -> Any:
        for fr in reversed(self.frames):
            if name in fr:
                return fr[name]
        raise HandRuntimeError("HND-RT-0001", f"Undefined variable '{name}'.")

    def set(self, name: str, value: Any) -> None:
        # assign to nearest existing binding, else create in top frame
        for fr in reversed(self.frames):
            if name in fr:
                fr[name]=value
                return
        self.frames[-1][name]=value

    def declare(self, name: str, value: Any) -> None:
        self.frames[-1][name]=value

    def push(self) -> None:
        self.frames.append({})

    def pop(self) -> None:
        self.frames.pop()

@dataclass
class OutputTrace:
    # Ω: list of emitted outputs (show/log)
    out: List[str]

# -------------------------
# Interpreter
# -------------------------

class Interpreter:
    def __init__(self, *, inputs: Optional[List[str]]=None, max_steps: int=200_000, max_loop_iters: int=1_000_000):
        self.inputs=list(inputs or [])
        self.input_i=0
        self.max_steps=max_steps
        self.max_loop_iters=max_loop_iters

        self.step=0
        self.trace: List[TraceEvent]=[]
        self.outputs: List[str]=[]

        self.store=Store(frames=[{}])
        self.functions: Dict[str, A.FuncDef]={}

    def _emit(self, kind: str, detail: Dict[str, Any]) -> None:
        self.step += 1
        if self.step > self.max_steps:
            raise HandRuntimeError("HND-RT-9999", "Step limit exceeded (possible infinite loop).")
        self.trace.append(TraceEvent(step=self.step, kind=kind, detail=detail))

    # --------
    # IO
    # --------

    def _ask(self, prompt: Any) -> str:
        # deterministic: consumes from provided inputs
        if self.input_i >= len(self.inputs):
            raise HandRuntimeError("HND-RT-0101", "ask() requested input but no more mocked inputs were provided.")
        val=self.inputs[self.input_i]
        self.input_i += 1
        self._emit("io", {"op":"ask", "prompt": self._repr(prompt), "value": val})
        return val

    def _show(self, value: Any) -> None:
        s=self._repr(value)
        self.outputs.append(s)
        self._emit("io", {"op":"show", "value": s})

    # -----------
    # Value repr
    # -----------

    def _repr(self, v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float):
            # stable repr
            return format(v, ".15g")
        if isinstance(v, (int, str)):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(self._repr(x) for x in v) + "]"
        if isinstance(v, dict):
            items=", ".join(f"{self._repr(k)}: {self._repr(val)}" for k,val in v.items())
            return "{" + items + "}"
        return str(v)

    # ----------------
    # Expression eval
    # ----------------

    def eval_expr(self, e: A.Expr) -> Any:
        self._emit("eval_expr", {"expr": type(e).__name__})

        if isinstance(e, A.Literal):
            if e.kind == "Text":
                return self._unescape_string(e.value)
            return e.value

        if isinstance(e, A.Var):
            return self.store.get(e.name)

        if isinstance(e, A.Paren):
            return self.eval_expr(e.expr)

        if isinstance(e, A.Unary):
            v=self.eval_expr(e.expr)
            if e.op == "-":
                if not isinstance(v, (int,float)):
                    raise HandRuntimeError("HND-RT-0201", f"Unary '-' expects number, got {type(v).__name__}.")
                return -v
            raise HandRuntimeError("HND-RT-0200", f"Unknown unary operator '{e.op}'.")

        if isinstance(e, A.Binary):
            a=self.eval_expr(e.left)
            b=self.eval_expr(e.right)
            return self._eval_bin(a, e.op, b)

        if isinstance(e, A.Call):
            # builtins
            if e.callee == "ask":
                if len(e.args)!=1:
                    raise HandRuntimeError("HND-RT-0102", "ask(prompt) expects exactly 1 argument.")
                return self._ask(self.eval_expr(e.args[0]))
            if e.callee == "show":
                if len(e.args)!=1:
                    raise HandRuntimeError("HND-RT-0103", "show(value) expects exactly 1 argument.")
                self._show(self.eval_expr(e.args[0]))
                return None

            # user function
            if e.callee not in self.functions:
                raise HandRuntimeError("HND-RT-0301", f"Unknown function '{e.callee}'.")
            fn=self.functions[e.callee]
            if len(e.args) != len(fn.params):
                raise HandRuntimeError("HND-RT-0302", f"Function '{e.callee}' expects {len(fn.params)} args, got {len(e.args)}.")
            argvals=[self.eval_expr(a) for a in e.args]
            self._emit("call", {"fn": e.callee, "args":[self._repr(x) for x in argvals]})
            return self._call_user(fn, argvals)

        raise HandRuntimeError("HND-RT-0002", f"Unsupported expression node: {type(e).__name__}.")

    def _unescape_string(self, s: str) -> str:
        # lexer stores strings including quotes; preserve determinism
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            body=s[1:-1]
            # minimal escapes: \\n, \\t, \\\\, \\"
            out=[]
            i=0
            while i < len(body):
                ch=body[i]
                if ch != "\\": 
                    out.append(ch); i+=1; continue
                if i+1 >= len(body):
                    out.append("\\"); break
                nxt=body[i+1]
                # HAND v0.1: accept both "\\n" and "\\\\n" as newline for portability
                if nxt == "\\" and i+2 < len(body) and body[i+2] in ("n","t"):
                    out.append("\n".encode("utf-8").decode("unicode_escape") if body[i+2]=="n" else "\t".encode("utf-8").decode("unicode_escape"))
                    i += 3
                    continue
                if nxt == "n": out.append("\n".encode("utf-8").decode("unicode_escape"))
                elif nxt == "t": out.append("\t".encode("utf-8").decode("unicode_escape"))
                elif nxt == "\\": out.append("\\")
                elif nxt == '"': out.append('"')
                else:
                    # unknown escape -> keep literal (deterministic, strict)
                    out.append(nxt)
                i += 2
            return "".join(out)
        return s

    def _eval_bin(self, a: Any, op: str, b: Any) -> Any:
        if op in ("+","-","*","/","%"):
            if op == "+" and isinstance(a, str) and isinstance(b, str):
                return a + b
            if not isinstance(a, (int,float)) or not isinstance(b, (int,float)):
                raise HandRuntimeError("HND-RT-1201", f"Operator '{op}' expects numbers (or Text+Text), got {type(a).__name__} and {type(b).__name__}.")
            if op == "+": return a + b
            if op == "-": return a - b
            if op == "*": return a * b
            if op == "/": return a / b
            if op == "%": return a % b

        if op in ("==","!=","<","<=",">",">="):
            if op == "==": return a == b
            if op == "!=": return a != b
            # comparisons: numbers only (v0.1)
            if not isinstance(a, (int,float)) or not isinstance(b, (int,float)):
                raise HandRuntimeError("HND-RT-1202", f"Comparison '{op}' expects numbers, got {type(a).__name__} and {type(b).__name__}.")
            if op == "<": return a < b
            if op == "<=": return a <= b
            if op == ">": return a > b
            if op == ">=": return a >= b

        raise HandRuntimeError("HND-RT-1200", f"Unknown operator '{op}'.")

    # -------------
    # Statements
    # -------------

    def exec_stmt(self, s: A.Stmt) -> None:
        self._emit("enter_stmt", {"stmt": type(s).__name__})

        if isinstance(s, A.AssignStmt):
            v=self.eval_expr(s.value)
            self.store.set(s.name, v)
            self._emit("assign", {"name": s.name, "value": self._repr(v)})
            self._emit("exit_stmt", {"stmt": type(s).__name__})
            return

        if isinstance(s, A.ExprStmt):
            self.eval_expr(s.expr)
            self._emit("exit_stmt", {"stmt": type(s).__name__})
            return

        if isinstance(s, A.ShowStmt):
            v=self.eval_expr(s.value)
            self._show(v)
            self._emit("exit_stmt", {"stmt": type(s).__name__})
            return

        if isinstance(s, A.VerifyStmt):
            ok=self.eval_expr(s.expr)
            if not isinstance(ok, bool):
                raise HandRuntimeError("HND-RT-0402", f"VERIFY expects Bool, got {type(ok).__name__}.")
            self._emit("verify", {"expr": self._repr(ok)})
            if not ok:
                raise HandRuntimeError("HND-RT-0401", "VERIFY failed.")
            self._emit("exit_stmt", {"stmt": type(s).__name__})
            return

        if isinstance(s, A.IfStmt):
            cond=self.eval_expr(s.cond)
            if not isinstance(cond, bool):
                raise HandRuntimeError("HND-RT-0501", "if condition must be Bool.")
            self._emit("branch", {"cond": cond})
            body = s.then_body if cond else (s.else_body or [])
            self.store.push()
            try:
                for st in body:
                    self.exec_stmt(st)
            finally:
                self.store.pop()
            self._emit("exit_stmt", {"stmt": type(s).__name__})
            return

        if isinstance(s, A.WhileStmt):
            it=0
            while True:
                it += 1
                if it > self.max_loop_iters:
                    raise HandRuntimeError("HND-RT-9998", "Loop iteration limit exceeded.")
                cond=self.eval_expr(s.cond)
                if not isinstance(cond, bool):
                    raise HandRuntimeError("HND-RT-0601", "while condition must be Bool.")
                self._emit("loop_check", {"iter": it, "cond": cond})
                if not cond:
                    break
                self.store.push()
                try:
                    for st in s.body:
                        self.exec_stmt(st)
                finally:
                    self.store.pop()
            self._emit("exit_stmt", {"stmt": type(s).__name__})
            return

        if isinstance(s, A.ReturnStmt):
            val=None if s.value is None else self.eval_expr(s.value)
            self._emit("return", {"value": self._repr(val)})
            raise _ReturnSignal(val)

        raise HandRuntimeError("HND-RT-0003", f"Unsupported statement node: {type(s).__name__}.")

    # -------------
    # Program / funcs
    # -------------

    def load_program(self, p: A.Program) -> List[A.Stmt]:
        # collect function defs and top-level statements
        top: List[A.Stmt]=[]
        for item in p.items:
            if isinstance(item, A.Section):
                # v0.1: ignore sections in execution (metadata only); but execute statements inside a section body if present
                if item.body:
                    for st in item.body:
                        top.append(st)
                continue
            if isinstance(item, A.FuncDef):
                self.functions[item.name]=item
                continue
            if isinstance(item, (A.IfStmt, A.WhileStmt, A.ReturnStmt, A.ShowStmt, A.AssignStmt, A.ExprStmt, A.VerifyStmt)):
                top.append(item)
                continue
        return top

    def _call_user(self, fn: A.FuncDef, argvals: List[Any]) -> Any:
        self.store.push()
        try:
            for param, val in zip(fn.params, argvals):
                self.store.declare(param.name, val)
            try:
                for st in fn.body:
                    self.exec_stmt(st)
            except _ReturnSignal as r:
                return r.value
            # implicit return null
            return None
        finally:
            self.store.pop()

    def run(self, program: A.Program) -> RunResult:
        top=self.load_program(program)
        try:
            for st in top:
                self.exec_stmt(st)
        except HandRuntimeError as e:
            self._emit("error", {"code": e.code, "message": e.message})
            raise
        return self._finalize()

    
    def store_snapshot(self) -> Dict[str, Any]:
        # Σ: final observable store for equivalence oracle (top-level frame only)
        # Note: frames[-1] is the current scope; frames[0] is global.
        try:
            if isinstance(self.store, dict):
                # legacy
                return dict(self.store)
            frames = getattr(self.store, "frames", None)
            if isinstance(frames, list) and frames:
                # expose global frame
                return dict(frames[0])
        except Exception:
            pass
        return {}

    def _finalize(self) -> RunResult:
        # write trace to a deterministic json file next to cwd (caller can override by copying)
        trace_path=str(pathlib.Path("trace.json").absolute())
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump([asdict(ev) for ev in self.trace], f, ensure_ascii=False, indent=2)
        return RunResult(outputs=self.outputs, final_store=self.store_snapshot(), trace=self.trace, trace_path=trace_path)

# -------------------------
# Public convenience API
# -------------------------

def run_source(source: str, *, inputs: Optional[List[str]]=None, filename: str="<input>") -> RunResult:
    toks, ldiags = lex(source, filename)
    if ldiags:
        # lexer is deterministic; interpreter rejects invalid programs
        msg="\n".join(f"{d.idref} {d.code}: {d.message_human}" for d in ldiags)
        raise HandRuntimeError("HND-RT-LEX", msg)
    pres = parse(toks, filename)
    if pres.diagnostics:
        msg="\n".join(f"{d.idref} {d.code}: {d.message_human}" for d in pres.diagnostics)
        raise HandRuntimeError("HND-RT-PARSE", msg)
    it=Interpreter(inputs=inputs)
    return it.run(pres.program)
