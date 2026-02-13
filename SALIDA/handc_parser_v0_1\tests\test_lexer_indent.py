from handc.lexer import lex, TK_INDENT, TK_DEDENT

def test_indent_dedent_counts():
    src = "a = 1\n    b = 2\n    c = 3\nd = 4\n"
    toks, diags = lex(src, "x.hand")
    assert diags == []
    kinds = [t.kind for t in toks]
    assert kinds.count(TK_INDENT) == 1
    assert kinds.count(TK_DEDENT) == 1
