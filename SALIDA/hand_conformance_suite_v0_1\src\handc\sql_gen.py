from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# HAND-IR v0.1 -> SQL v0.1 (script)
#
# Design goals:
# - Set-based queries only (SELECT/INSERT/UPDATE/DELETE).
# - DDL emitted from module.types (Record declarations).
# - DML emitted from top-level expr statements calling canonical SQL builtins.
# - Transactions are emitted when explicit begin/commit/rollback builtins appear.
#
# Dialect:
# - Generic ANSI-ish SQL with PostgreSQL-friendly types.
#
# Subset (supported):
# - DDL: Record types -> CREATE TABLE with constraints (NOT NULL by default).
# - DML builtins:
#   - select(table, columns=list(...)? , where=map(...)?)
#   - insert(table, values=map(...))
#   - update(table, set=map(...), where=map(...))
#   - delete(table, where=map(...))
#   - begin_tx(), commit(), rollback()
# Helper constructors (purely for IR, no runtime):
#   - list(x1, x2, ...)          -> SQL column list
#   - map(k1, v1, k2, v2, ...)   -> SQL key/value map (keys MUST be Text literals)
#
# Declared but NOT compiled (hard errors):
# - Any control-flow (if/while), functions, show/ask/verify, non-SQL calls.
# - Any type not mapped (List/Map/Result in schemas; runtime SQL values limited).
# - Any module.toplevel stmt that's not expr(call ...).

@dataclass(frozen=True)
class SqlNote:
    kind: str   # ERROR|WARN|INFO
    code: str
    message: str
    origin_ref: Optional[str]=None

class SqlGenError(Exception):
    def __init__(self, note: SqlNote):
        super().__init__(note.message)
        self.note = note

def _origin_ref(node: Dict[str, Any]) -> Optional[str]:
    try:
        return node.get("origin", {}).get("ref")
    except Exception:
        return None

def _type_to_sql(t: Dict[str, Any]) -> Tuple[str, bool]:
    """Return (sql_type, nullable)."""
    k = t.get("kind")
    if k == "Optional":
        inner = (t.get("args") or [None])[0]
        if not inner:
            raise ValueError("Optional missing inner type")
        sql, _ = _type_to_sql(inner)
        return sql, True
    if k == "Int":
        return "INTEGER", False
    if k == "Float":
        return "REAL", False
    if k == "Bool":
        return "BOOLEAN", False
    if k == "Text":
        return "TEXT", False
    if k == "Null":
        return "TEXT", True
    if k == "Record":
        # Foreign-key-ish reference (by convention: <Record>.id)
        return "INTEGER", False
    raise SqlGenError(SqlNote("ERROR", "SQL-0300", f"Type '{k}' is not supported in SQL v0.1.", None))

def _lit_to_sql(expr: Dict[str, Any]) -> str:
    v = expr.get("value")
    ty = (expr.get("type") or {}).get("kind")
    if v is None or (isinstance(v, str) and v.strip().lower() == "null"):
        return "NULL"
    if ty == "Bool" and isinstance(v, str):
        s=v.strip().lower()
        if s=="true": return "TRUE"
        if s=="false": return "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # Text literal tokens come like '"hi"' from lowering; accept either raw or token.
        s=v
        if len(s)>=2 and s[0]==s[-1]=='"':
            s=s[1:-1]
        s=s.replace("'", "''")
        return "'" + s + "'"
    return "'" + str(v).replace("'", "''") + "'"

def _expect_call(expr: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    if expr.get("kind") != "call":
        raise SqlGenError(SqlNote("ERROR","SQL-0102","SQL v0.1 requires call expressions for DML.", _origin_ref(expr)))
    return expr["callee"], (expr.get("args") or [])

def _as_text_key(expr: Dict[str, Any]) -> str:
    if expr.get("kind") != "lit":
        raise SqlGenError(SqlNote("ERROR","SQL-0103","map() keys must be Text literals.", _origin_ref(expr)))
    v = expr.get("value")
    if not isinstance(v, str):
        raise SqlGenError(SqlNote("ERROR","SQL-0103","map() keys must be Text literals.", _origin_ref(expr)))
    if len(v)>=2 and v[0]==v[-1]=='"':
        v=v[1:-1]
    return v

def _decode_list(expr: Dict[str, Any]) -> List[Dict[str, Any]]:
    cal, args = _expect_call(expr)
    if cal != "list":
        raise SqlGenError(SqlNote("ERROR","SQL-0104","Expected list(...).", _origin_ref(expr)))
    return args

def _decode_map(expr: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    cal, args = _expect_call(expr)
    if cal != "map":
        raise SqlGenError(SqlNote("ERROR","SQL-0105","Expected map(k1,v1,...).", _origin_ref(expr)))
    if len(args) % 2 != 0:
        raise SqlGenError(SqlNote("ERROR","SQL-0106","map() requires even number of args (k,v pairs).", _origin_ref(expr)))
    pairs=[]
    for i in range(0,len(args),2):
        k = _as_text_key(args[i])
        v = args[i+1]
        pairs.append((k, v))
    return pairs

def _expr_value_to_sql(expr: Dict[str, Any]) -> str:
    k=expr.get("kind")
    if k=="lit":
        return _lit_to_sql(expr)
    if k=="var":
        # By convention variables are SQL parameters (named).
        return ":" + expr["name"]
    raise SqlGenError(SqlNote("ERROR","SQL-0200",f"Value expression kind '{k}' unsupported in SQL v0.1 (use literals or :params).", _origin_ref(expr)))

def _build_where(pairs: List[Tuple[str, Dict[str, Any]]]) -> str:
    if not pairs:
        return ""
    clauses=[]
    for col, vexpr in pairs:
        clauses.append(f"{col} = {_expr_value_to_sql(vexpr)}")
    return " WHERE " + " AND ".join(clauses)

def gen_sql(ir: Dict[str, Any]) -> Tuple[str, List[SqlNote]]:
    if ir.get("ir_version") != "0.1.0":
        raise ValueError("Unsupported IR version")
    mod = ir["module"]
    notes: List[SqlNote] = []

    # Hard rules: no functions in v0.1
    if (mod.get("functions") or []):
        raise SqlGenError(SqlNote("ERROR","SQL-0001","SQL v0.1 does not compile HAND functions (only module.types + top-level DML calls).", _origin_ref((mod.get('functions') or [])[0])))

    lines: List[str] = []
    emit = lines.append

    emit("-- HAND SQL v0.1 (generated)")
    emit(f"-- module: {mod.get('name')}")
    emit("")

    # DDL from types
    if mod.get("types"):
        emit("-- DDL")
        for td in mod.get("types") or []:
            if td.get("kind") != "record":
                raise SqlGenError(SqlNote("ERROR","SQL-0301",f"Unsupported type_decl kind: {td.get('kind')}", _origin_ref(td)))
            tname = td["name"]
            fields = td.get("fields") or []
            col_lines=[]
            pk=None
            for f in fields:
                col = f["name"]
                sql_t, nullable = _type_to_sql(f["type"])
                nn = "" if nullable else " NOT NULL"
                col_lines.append(f"  {col} {sql_t}{nn}")
                if col == "id":
                    pk="id"
            if pk:
                col_lines.append(f"  PRIMARY KEY ({pk})")
            emit(f"CREATE TABLE IF NOT EXISTS {tname} (")
            emit(",\n".join(col_lines))
            emit(");")
            emit("")
        emit("")

    # DML from top-level
    emit("-- DML")
    for st in mod.get("toplevel") or []:
        if st.get("kind") != "expr":
            raise SqlGenError(SqlNote("ERROR","SQL-0002","Only expr statements are supported for SQL v0.1.", _origin_ref(st)))
        expr = st.get("value")
        cal, args = _expect_call(expr)

        if cal == "begin_tx":
            emit("BEGIN;")
            continue
        if cal == "commit":
            emit("COMMIT;")
            continue
        if cal == "rollback":
            emit("ROLLBACK;")
            continue

        if cal == "insert":
            # insert(table, values=map(...))
            if len(args) != 2:
                raise SqlGenError(SqlNote("ERROR","SQL-0400","insert(table, values) requires 2 args.", _origin_ref(expr)))
            table = _as_text_key(args[0])
            pairs = _decode_map(args[1])
            cols = ", ".join(k for k,_ in pairs)
            vals = ", ".join(_expr_value_to_sql(v) for _,v in pairs)
            emit(f"INSERT INTO {table} ({cols}) VALUES ({vals});")
            continue

        if cal == "select":
            # select(table, columns=list(...), where=map(...)?)
            if len(args) < 2 or len(args) > 3:
                raise SqlGenError(SqlNote("ERROR","SQL-0410","select(table, columns, [where]) expects 2 or 3 args.", _origin_ref(expr)))
            table = _as_text_key(args[0])
            cols_expr = args[1]
            cols = _decode_list(cols_expr)
            col_sql = ", ".join(_as_text_key(c) for c in cols) if cols else "*"
            where_sql = ""
            if len(args) == 3:
                where_pairs = _decode_map(args[2])
                where_sql = _build_where(where_pairs)
            emit(f"SELECT {col_sql} FROM {table}{where_sql};")
            continue

        if cal == "update":
            # update(table, set=map(...), where=map(...))
            if len(args) != 3:
                raise SqlGenError(SqlNote("ERROR","SQL-0420","update(table, set, where) expects 3 args.", _origin_ref(expr)))
            table = _as_text_key(args[0])
            set_pairs = _decode_map(args[1])
            where_pairs = _decode_map(args[2])
            set_sql = ", ".join(f"{k} = {_expr_value_to_sql(v)}" for k,v in set_pairs)
            where_sql = _build_where(where_pairs)
            emit(f"UPDATE {table} SET {set_sql}{where_sql};")
            continue

        if cal == "delete":
            # delete(table, where=map(...))
            if len(args) != 2:
                raise SqlGenError(SqlNote("ERROR","SQL-0430","delete(table, where) expects 2 args.", _origin_ref(expr)))
            table = _as_text_key(args[0])
            where_pairs = _decode_map(args[1])
            where_sql = _build_where(where_pairs)
            emit(f"DELETE FROM {table}{where_sql};")
            continue

        raise SqlGenError(SqlNote("ERROR","SQL-0999",f"Unsupported SQL builtin '{cal}'.", _origin_ref(expr)))

    emit("")
    return "\n".join(lines), notes
