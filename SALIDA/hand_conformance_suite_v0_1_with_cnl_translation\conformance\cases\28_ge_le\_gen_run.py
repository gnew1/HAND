from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List

# --- Runtime (matches interpreter_ref repr rules) ---
@dataclass
class Store:
    frames: List[Dict[str, Any]]
    def get(self, name: str) -> Any:
        for fr in reversed(self.frames):
            if name in fr:
                return fr[name]
        raise RuntimeError(f"HND-RT-0001 Undefined variable '{name}'.")
    def set(self, name: str, value: Any) -> None:
        for fr in reversed(self.frames):
            if name in fr:
                fr[name] = value
                return
        self.frames[-1][name] = value
    def declare(self, name: str, value: Any) -> None:
        self.frames[-1][name] = value
    def push(self) -> None:
        self.frames.append({})
    def pop(self) -> None:
        self.frames.pop()

@dataclass
class Runtime:
    inputs: List[str]
    outputs: List[str]
    ip: int = 0
    def _repr(self, v: Any) -> str:
        if v is None:
            return 'null'
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, float):
            return format(v, '.15g')
        if isinstance(v, (int, str)):
            return str(v)
        if isinstance(v, list):
            return '[' + ', '.join(self._repr(x) for x in v) + ']'
        if isinstance(v, dict):
            items = ', '.join(f"{self._repr(k)}: {self._repr(val)}" for k, val in v.items())
            return '{' + items + '}'
        return str(v)
    def show(self, v: Any) -> None:
        self.outputs.append(self._repr(v))
    def ask(self, prompt: Any) -> str:
        if self.ip >= len(self.inputs):
            raise RuntimeError('HND-RT-0101 ask() requested input but no more mocked inputs were provided.')
        v = self.inputs[self.ip]
        self.ip += 1
        return v

class _ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value

def _truthy(v: Any) -> bool:
    return bool(v)

# --- User functions ---
# --- Top-level ---
def __hand_main(inputs: List[str]) -> List[str]:
    store = Store(frames=[{}])
    rt = Runtime(inputs=list(inputs), outputs=[])
    rt.show((3 >= 3))
    rt.show((2 <= 1))
    return rt.outputs

def __hand_run_and_print_json(inputs: List[str]) -> None:
    import json
    out = __hand_main(inputs)
    print(json.dumps({'outputs': out}, ensure_ascii=False))

if __name__ == '__main__':
    import json, sys
    inputs = []
    if len(sys.argv) > 1:
        inputs = json.loads(sys.argv[1])
    __hand_run_and_print_json(inputs)

