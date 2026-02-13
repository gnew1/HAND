from hand_tree_translator.python_subset import python_to_simple_hand

def test_simple_translation():
    src = "x=1\nprint(x)\n"
    hand = python_to_simple_hand(src, program_name="t", source_path="t.py")
    assert '▶️ INICIAR:' in hand
    assert 'show x' in hand
