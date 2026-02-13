import pytest
from handc.lexer import lex
from handc.parser import parse
from handc.format import format_hand

PROGRAMS = [
    # 1
    "show 1\n",
    # 2
    "a = 1\nshow a\n",
    # 3
    "a = 1 + 2 * 3\nshow a\n",
    # 4
    "if true:\n    show 1\nelse:\n    show 2\n",
    # 5
    "while a < 3:\n    a = a + 1\n",
    # 6
    "return\n",
    # 7
    "🔧 FUNCIÓN add(a, b):\n    return a + b\n",
    # 8
    "show add(1, 2)\n",
    # 9
    "a = -5\nshow a\n",
    # 10
    "if a >= 10:\n    show \"big\"\n",
    # 11
    "show (1 + 2) * 3\n",
    # 12
    "a = null\nif a == null:\n    show true\n",
    # 13
    "🎬 PROGRAMA \"Demo\":\n",
    # 14
    "▶️ INICIAR:\n    show 1\n",
    # 15
    "show \"a\\n\\\"b\"\n",
    # 16
    "if true:\n    if false:\n        show 1\n    show 2\nshow 3\n",
    # 17
    "show 👨‍👩‍👧‍👦\n",
    # 18
    "a = 1\n\n\nshow a\n",
    # 19
    "show 1%2 + 3\n",
    # 20
    "🔧 FUNCIÓN f():\n    show \"ok\"\n    return\n",
]

@pytest.mark.parametrize("src", PROGRAMS)
def test_round_trip_parse_format_parse(src):
    toks, diags1 = lex(src, "<mem>")
    assert diags1 == []
    r1 = parse(toks, "<mem>")
    assert r1.diagnostics == []
    formatted = format_hand(r1.program)
    toks2, diags2 = lex(formatted, "<mem>")
    assert diags2 == []
    r2 = parse(toks2, "<mem>")
    assert r2.diagnostics == []
    assert r1.program == r2.program
