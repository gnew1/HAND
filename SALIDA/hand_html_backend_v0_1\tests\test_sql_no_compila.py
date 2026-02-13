import pytest
from handc.sql_gen import gen_sql, SqlGenError

def test_no_functions():
    ir={
      "ir_version":"0.1.0",
      "module":{"name":"m","capabilities":["compute"],"types":[],"toplevel":[],
               "functions":[{"name":"f","params":[],"ret_type":{"kind":"Int"},"body":[],"origin":{"actor":"👤","ref":"x"}}]}
    }
    with pytest.raises(SqlGenError) as ei:
        gen_sql(ir)
    assert ei.value.note.code == "SQL-0001"

def test_no_control_flow_stmt():
    ir={"ir_version":"0.1.0","module":{"name":"m","capabilities":["compute"],"types":[],
        "functions":[],
        "toplevel":[{"kind":"if","cond":{"kind":"lit","value":"true","type":{"kind":"Bool"}}, "then":[], "else":[], "origin":{"actor":"👤","ref":"x"}}]
    }}
    with pytest.raises(SqlGenError) as ei:
        gen_sql(ir)
    assert ei.value.note.code == "SQL-0002"
