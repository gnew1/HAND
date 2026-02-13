from pathlib import Path
import json
import pytest

from handc.sql_gen import gen_sql

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = REPO_ROOT / "tests" / "snapshots_sql"

def _load_ir(name: str) -> dict:
    p = REPO_ROOT / "tests" / "ir_sql" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))

CASES = [
    "ddl_user",
    "crud_basic",
    "tx_block",
    "ddl_two_tables_fk",
]

@pytest.mark.parametrize("name", CASES)
def test_sql_snapshot(name):
    ir = _load_ir(name)
    sql, notes = gen_sql(ir)
    assert notes == []
    exp = (SNAP_DIR / f"{name}.sql").read_text(encoding="utf-8")
    assert sql == exp
