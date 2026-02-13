from handc.lexer import lex

def test_tabs_forbidden():
    src="a\t= 1\n"
    _, diags = lex(src, "<mem>")
    assert any(d.code=="HND-LEX-0002" for d in diags)

def test_invalid_indent_multiple():
    src="if true:\n  show 1\n"
    _, diags = lex(src, "<mem>")
    assert any(d.code=="HND-INDENT-0001" for d in diags)

def test_invalid_indent_jump():
    src="if true:\n        show 1\n"
    _, diags = lex(src, "<mem>")
    assert any(d.code=="HND-INDENT-0002" for d in diags)

def test_invalid_dedent_level():
    src="if true:\n    show 1\n  show 2\n"
    _, diags = lex(src, "<mem>")
    assert any(d.code=="HND-INDENT-0003" for d in diags)

def test_non_ascii_outside_string_rejected():
    src="café = 1\n"
    _, diags = lex(src, "<mem>")
    assert any(d.code=="HND-LEX-0004" for d in diags)

def test_surrogate_rejected():
    src="a = \ud800\n"
    _, diags = lex(src, "<mem>")
    assert any(d.code=="HND-LEX-0003" for d in diags)
