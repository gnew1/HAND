from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import jsonschema
except ImportError:
    raise SystemExit("validate_ir requires jsonschema (add to dev deps).")

def main(argv: Optional[List[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        raise SystemExit("usage: validate_ir.py hand_ir.schema.json <ir.json> [<ir2.json> ...]")
    schema_path = Path(argv[0])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    ok = 0
    bad = 0
    for p in argv[1:]:
        j = json.loads(Path(p).read_text(encoding="utf-8"))
        try:
            jsonschema.validate(j, schema)
            ok += 1
        except Exception as e:
            bad += 1
            print(f"INVALID {p}: {e}")
    print(f"validated ok={ok} bad={bad}")
    return 0 if bad == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
