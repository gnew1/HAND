from handc.lexer import lex, TK_IDENT, TK_EQ, TK_NUMBER

def test_span_columns_basic():
    toks, diags = lex("a = 12\n", "<mem>")
    assert diags == []
    a, eq, n = toks[0], toks[1], toks[2]
    assert (a.kind, a.value) == (TK_IDENT, "a")
    assert (a.span.col, a.span.end_col) == (1, 2)
    assert (eq.kind, eq.value) == (TK_EQ, "=")
    assert (eq.span.col, eq.span.end_col) == (3, 4)
    assert (n.kind, n.value) == (TK_NUMBER, "12")
    assert (n.span.col, n.span.end_col) == (5, 7)
