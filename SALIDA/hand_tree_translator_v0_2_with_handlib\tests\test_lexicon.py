from hand_tree_translator.handlib.lexicon import EmojiLexicon

def test_lexicon_loads():
    lex = EmojiLexicon.load_builtin()
    assert lex.emoji_for("flow.if") is not None
