import pytest
from handc.enforce import enforce_capabilities, CapabilityError
from handc.lowering import lower_program
from handc.lexer import lex
from handc.parser import parse

def ir_from_src(src: str, name: str="m"):
    toks, ldiags = lex(src, "<mem>")
    assert not ldiags
    pres = parse(toks, "<mem>")
    assert not pres.diagnostics
    return lower_program(pres.program, module_name=name)

def set_module_caps(ir, caps):
    ir["module"]["capabilities"]=caps
    return ir

CASES_OK = [
    ("l1_compute_ok_1", "x: Int = 1\nx = x + 1\n", 1, set(), ["compute"]),
    ("l1_compute_ok_2", "i: Int = 0\nwhile i < 2:\n    i = i + 1\n", 1, set(), ["compute"]),
    ("l1_if_ok", "if true:\n    x: Int = 1\n", 1, set(), ["compute"]),
    ("l2_show_ok_1", "show 1\n", 2, set(), ["compute","io.write"]),
    ("l2_show_ok_2", 'show "a"\n', 2, set(), ["compute","io.write"]),
    ("l2_show_in_if_ok", "if true:\n    show 1\n", 2, set(), ["compute","io.write"]),
    ("l2_ask_ok_with_approval", 'x: Text = ask("p")\nshow x\n', 2, {"io.read"}, ["compute","io.read","io.write"]),
    ("l3_ask_ok", 'x: Text = ask("p")\nshow x\n', 3, set(), ["compute","io.read","io.write"]),
    ("l3_show_only_ok", "show 9\n", 3, set(), ["compute","io.write"]),
    ("l3_mixed_ok", 'x: Text = ask("p")\nshow x + "!"\n', 3, set(), ["compute","io.read","io.write"]),
    ("l4_fs_read_declared_ok", "x: Int = 1\n", 4, set(), ["compute","fs.read"]),
    ("l4_io_ok", 'x: Text = ask("p")\nshow x\n', 4, set(), ["compute","io.read","io.write"]),
]

CASES_DENY = [
    ("l1_show_denied", "show 1\n", 1, set(), ["compute","io.write"], "HND-CAP-0101"),
    ("l1_ask_denied", 'x: Text = ask("p")\n', 1, set(), ["compute","io.read"], "HND-CAP-0101"),
    ("l2_missing_io_write", "show 1\n", 2, set(), ["compute"], "HND-CAP-0201"),
    ("l2_missing_io_read_decl", 'x: Text = ask("p")\n', 2, {"io.read"}, ["compute"], "HND-CAP-0201"),
    ("l2_ask_no_approval", 'x: Text = ask("p")\n', 2, set(), ["compute","io.read"], "HND-CAP-0102"),
    ("l2_fs_denied", "x: Int = 1\n", 2, set(), ["compute","fs.read"], "HND-CAP-0101"),
    ("l3_missing_io_read", 'x: Text = ask("p")\n', 3, set(), ["compute"], "HND-CAP-0201"),
    ("l3_net_needs_approval", "x: Int = 1\n", 3, set(), ["compute","net"], "HND-CAP-0102"),
    ("l4_net_needs_approval", "x: Int = 1\n", 4, set(), ["compute","net"], "HND-CAP-0102"),
    ("unknown_cap", "x: Int = 1\n", 3, set(), ["compute","io.writ"], "HND-CAP-0001"),
]

@pytest.mark.parametrize("name, src, level, approvals, declared_caps", CASES_OK)
def test_capabilities_ok(name, src, level, approvals, declared_caps):
    ir=ir_from_src(src, name=name)
    ir=set_module_caps(ir, declared_caps)
    enforce_capabilities(ir, supervision_level=level, approvals=approvals)

@pytest.mark.parametrize("name, src, level, approvals, declared_caps, expect_code", CASES_DENY)
def test_capabilities_deny(name, src, level, approvals, declared_caps, expect_code):
    ir=ir_from_src(src, name=name)
    ir=set_module_caps(ir, declared_caps)

    # Inject synthetic effects to force capability requirements when a capability is declared.
    if "net" in declared_caps:
        ir["module"]["toplevel"].append({
            "kind":"expr",
            "value":{"kind":"lit","value":None,"type":{"kind":"Null"}},
            "origin":{"actor":"👤","ref":"[AST][🌐][N0].net"},
            "effects":["net.request"],
            "capabilities":["net"]
        })
    if "fs.read" in declared_caps:
        ir["module"]["toplevel"].append({
            "kind":"expr",
            "value":{"kind":"lit","value":None,"type":{"kind":"Null"}},
            "origin":{"actor":"👤","ref":"[AST][📥][N0].fsr"},
            "effects":["fs.read"],
            "capabilities":["fs.read"]
        })
    if "fs.write" in declared_caps:
        ir["module"]["toplevel"].append({
            "kind":"expr",
            "value":{"kind":"lit","value":None,"type":{"kind":"Null"}},
            "origin":{"actor":"👤","ref":"[AST][💾][N0].fsw"},
            "effects":["fs.write"],
            "capabilities":["fs.write"]
        })

    with pytest.raises(CapabilityError) as ei:
        enforce_capabilities(ir, supervision_level=level, approvals=approvals)
    assert ei.value.diag.code == expect_code

def test_function_scope_missing_caps():
    src='🛠 f() -> Null:\n    show 1\n    return null\n'
    ir=ir_from_src(src, name="fn_scope")
    ir["module"]["capabilities"]=["compute","io.write"]
    for fn in ir["module"]["functions"]:
        fn["capabilities"]=["compute"]  # missing io.write
    with pytest.raises(CapabilityError) as ei:
        enforce_capabilities(ir, supervision_level=2, approvals=set(), scope="function")
    assert ei.value.diag.code == "HND-CAP-0202"

def test_function_scope_ok():
    src='🛠 f() -> Null:\n    show 1\n    return null\n'
    ir=ir_from_src(src, name="fn_scope_ok")
    ir["module"]["capabilities"]=["compute","io.write"]
    for fn in ir["module"]["functions"]:
        fn["capabilities"]=["compute","io.write"]
    enforce_capabilities(ir, supervision_level=2, approvals=set(), scope="function")

def test_level4_fs_write_requires_approval():
    ir=ir_from_src("x: Int = 1\n", name="fsw4")
    ir["module"]["capabilities"]=["compute","fs.write"]
    ir["module"]["toplevel"].append({
        "kind":"expr",
        "value":{"kind":"lit","value":None,"type":{"kind":"Null"}},
        "origin":{"actor":"👤","ref":"[AST][💾][N0].fsw"},
        "effects":["fs.write"],
        "capabilities":["fs.write"]
    })
    with pytest.raises(CapabilityError) as ei:
        enforce_capabilities(ir, supervision_level=4, approvals=set())
    assert ei.value.diag.code == "HND-CAP-0102"
    enforce_capabilities(ir, supervision_level=4, approvals={"fs.write"})
