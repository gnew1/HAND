import json
import pytest
from handc.interpreter import run_source, HandRuntimeError

CASES = json.loads(open("tests/cases_30.json","r",encoding="utf-8").read())

@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_case(case, tmp_path, monkeypatch):
    # ensure deterministic trace output path
    monkeypatch.chdir(tmp_path)
    src=case["src"]
    inputs=case["inputs"]
    expected=case.get("expected_outputs")
    if expected is None:
        with pytest.raises(HandRuntimeError):
            run_source(src, inputs=inputs)
        return
    res=run_source(src, inputs=inputs)
    assert res.outputs == expected
    # trace file exists and is valid JSON
    with open(res.trace_path,"r",encoding="utf-8") as f:
        data=json.load(f)
    assert isinstance(data, list)
    assert len(data) >= 1
