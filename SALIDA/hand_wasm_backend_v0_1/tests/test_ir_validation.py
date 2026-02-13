import json
from pathlib import Path
import pytest
import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]

from handc.lexer import lex
from handc.parser import parse
from handc.lowering import lower_program

SCHEMA=json.loads((REPO_ROOT/"hand_ir.schema.json").read_text(encoding="utf-8"))

def validate_ir(ir):
    jsonschema.validate(instance=ir, schema=SCHEMA)

@pytest.mark.parametrize("hand_file", sorted((REPO_ROOT/"examples").glob("*.hand")))
def test_examples_lower_to_valid_ir(hand_file):
    src=hand_file.read_text(encoding="utf-8")
    toks, ldiags = lex(src, str(hand_file))
    assert not ldiags
    pres=parse(toks, str(hand_file))
    assert not pres.diagnostics
    ir=lower_program(pres.program, module_name=hand_file.stem)
    validate_ir(ir)

def test_origin_format_is_enforced():
    bad={"ir_version":"0.1.0","origin":{"actor":"👤","ref":"badref"},"module":{"name":"m","functions":[],"toplevel":[],"capabilities":[]}}
    with pytest.raises(jsonschema.ValidationError):
        validate_ir(bad)
