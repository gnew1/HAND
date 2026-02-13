from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

CANON_CAPS: Set[str] = {
    "compute",
    "io.read",
    "io.write",
    "fs.read",
    "fs.write",
    "net",
    "env",
    "crypto",
}

@dataclass(frozen=True)
class CapPolicy:
    allowed_without_approval: Set[str]
    allowed_with_approval: Set[str]
    denied: Set[str]

POLICY: Dict[int, CapPolicy] = {
    1: CapPolicy(
        allowed_without_approval={"compute"},
        allowed_with_approval=set(),
        denied=CANON_CAPS - {"compute"},
    ),
    2: CapPolicy(
        allowed_without_approval={"compute", "io.write"},
        allowed_with_approval={"io.read"},
        denied=CANON_CAPS - {"compute", "io.write", "io.read"},
    ),
    3: CapPolicy(
        allowed_without_approval={"compute", "io.read", "io.write"},
        allowed_with_approval={"fs.read", "fs.write", "net"},
        denied=CANON_CAPS - {"compute", "io.read", "io.write", "fs.read", "fs.write", "net"},
    ),
    4: CapPolicy(
        allowed_without_approval={"compute", "io.read", "io.write", "fs.read"},
        allowed_with_approval={"fs.write", "net", "env", "crypto"},
        denied=set(),
    ),
}

EFFECT_TO_CAP: Dict[str, str] = {
    "io.show": "io.write",
    "io.ask": "io.read",
    "contract.verify": "compute",
    "control.return": "compute",
    "fs.read": "fs.read",
    "fs.write": "fs.write",
    "net.request": "net",
    "env.read": "env",
    "crypto.use": "crypto",
}

def caps_required_for_effects(effects: List[str]) -> Set[str]:
    req={"compute"}
    for ef in effects or []:
        cap=EFFECT_TO_CAP.get(ef)
        if cap:
            req.add(cap)
    return req

def normalize_caps(caps: Optional[List[str]]) -> List[str]:
    if not caps:
        return []
    out=[]
    seen=set()
    for c in caps:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out
