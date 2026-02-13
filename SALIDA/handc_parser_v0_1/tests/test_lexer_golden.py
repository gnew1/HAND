import pytest
from handc.lexer import lex, TK_NEWLINE, TK_INDENT, TK_DEDENT, TK_EOF

def _kinds_vals(tokens):
    return [(t.kind, t.value) for t in tokens]

# 25 golden token-stream tests (kinds+values only)
GOLDEN = [
    ("empty", "", [(TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("newline_only", "\n", [(TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("assign_int", "a = 1\n", [("IDENT","a"), ("EQ","="), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("assign_float", "pi = 3.14\n", [("IDENT","pi"), ("EQ","="), ("NUMBER","3.14"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("show_string", "show \"hola\"\n", [("KEYWORD","show"), ("STRING","\"hola\""), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("if_block", "if true:\n    show 1\n", [("KEYWORD","if"), ("KEYWORD","true"), ("COLON",":"), (TK_NEWLINE,"\n"), (TK_INDENT,""),
                                              ("KEYWORD","show"), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_DEDENT,""), (TK_EOF,"")]),
    ("while_block", "while a < 3:\n    a = a + 1\n", [("KEYWORD","while"), ("IDENT","a"), ("OP","<"), ("NUMBER","3"), ("COLON",":"), (TK_NEWLINE,"\n"),
                                                       (TK_INDENT,""), ("IDENT","a"), ("EQ","="), ("IDENT","a"), ("OP","+"), ("NUMBER","1"), (TK_NEWLINE,"\n"),
                                                       (TK_DEDENT,""), (TK_EOF,"")]),
    ("func_def", "🔧 FUNCIÓN add(a,b):\n    return a + b\n", [("EMOJI","🔧"), ("IDENT","FUNCIÓN"), ("IDENT","add"), ("LPAREN","("),
                                                              ("IDENT","a"), ("COMMA",","), ("IDENT","b"), ("RPAREN",")"),
                                                              ("COLON",":"), (TK_NEWLINE,"\n"), (TK_INDENT,""),
                                                              ("KEYWORD","return"), ("IDENT","a"), ("OP","+"), ("IDENT","b"), (TK_NEWLINE,"\n"),
                                                              (TK_DEDENT,""), (TK_EOF,"")]),
    ("program_section", "🎬 PROGRAMA \"X\":\n", [("EMOJI","🎬"), ("IDENT","PROGRAMA"), ("STRING","\"X\""), ("COLON",":"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("start_section", "▶️ INICIAR:\n    show 1\n", [("EMOJI","▶️"), ("IDENT","INICIAR"), ("COLON",":"), (TK_NEWLINE,"\n"), (TK_INDENT,""),
                                                     ("KEYWORD","show"), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_DEDENT,""), (TK_EOF,"")]),
    ("ops_2char", "a==b\n", [("IDENT","a"), ("OP","=="), ("IDENT","b"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("ops_mix", "x>=1\n", [("IDENT","x"), ("OP",">="), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("parens", "show (1+2)*3\n", [("KEYWORD","show"), ("LPAREN","("), ("NUMBER","1"), ("OP","+"), ("NUMBER","2"), ("RPAREN",")"),
                                  ("OP","*"), ("NUMBER","3"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("comma_ws", "f(a, b)\n", [("IDENT","f"), ("LPAREN","("), ("IDENT","a"), ("COMMA",","), ("IDENT","b"), ("RPAREN",")"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("blank_lines", "a=1\n\nshow a\n", [("IDENT","a"), ("EQ","="), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_NEWLINE,"\n"),
                                          ("KEYWORD","show"), ("IDENT","a"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("string_escapes", "show \"a\\n\\\"b\"\n", [("KEYWORD","show"), ("STRING","\"a\\n\\\"b\""), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("negative_int", "a=-5\n", [("IDENT","a"), ("EQ","="), ("OP","-"), ("NUMBER","5"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("math_chain", "show 1+2-3*4/5%6\n", [("KEYWORD","show"), ("NUMBER","1"), ("OP","+"), ("NUMBER","2"), ("OP","-"), ("NUMBER","3"),
                                          ("OP","*"), ("NUMBER","4"), ("OP","/"), ("NUMBER","5"), ("OP","%"), ("NUMBER","6"),
                                          (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("identifier_keyword_boundary", "ifx = 1\n", [("IDENT","ifx"), ("EQ","="), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("keywords_literals", "a = true\nb = false\nc = null\n", [("IDENT","a"), ("EQ","="), ("KEYWORD","true"), (TK_NEWLINE,"\n"),
                                                                ("IDENT","b"), ("EQ","="), ("KEYWORD","false"), (TK_NEWLINE,"\n"),
                                                                ("IDENT","c"), ("EQ","="), ("KEYWORD","null"), (TK_NEWLINE,"\n"),
                                                                (TK_EOF,"")]),
    ("dedent_close", "if true:\n    if false:\n        show 1\n    show 2\nshow 3\n",
                     [("KEYWORD","if"), ("KEYWORD","true"), ("COLON",":"), (TK_NEWLINE,"\n"), (TK_INDENT,""),
                      ("KEYWORD","if"), ("KEYWORD","false"), ("COLON",":"), (TK_NEWLINE,"\n"), (TK_INDENT,""),
                      ("KEYWORD","show"), ("NUMBER","1"), (TK_NEWLINE,"\n"), (TK_DEDENT,""),
                      ("KEYWORD","show"), ("NUMBER","2"), (TK_NEWLINE,"\n"), (TK_DEDENT,""),
                      ("KEYWORD","show"), ("NUMBER","3"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("emoji_zwj_family", "show 👨‍👩‍👧‍👦\n", [("KEYWORD","show"), ("EMOJI","👨‍👩‍👧‍👦"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("emoji_vs16", "▶️ INICIAR:\n", [("EMOJI","▶️"), ("IDENT","INICIAR"), ("COLON",":"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
    ("multiple_emojis", "🎬 ▶️ 🔧\n", [("EMOJI","🎬"), ("EMOJI","▶️"), ("EMOJI","🔧"), (TK_NEWLINE,"\n"), (TK_EOF,"")]),
]

@pytest.mark.parametrize("name,src,expected", GOLDEN)
def test_golden_token_stream(name, src, expected):
    toks, diags = lex(src, "<mem>")
    assert diags == [], f"{name} had diags: {[d.code for d in diags]}"
    got=_kinds_vals(toks)
    assert got == expected
