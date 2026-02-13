from __future__ import annotations
from pathlib import Path
import pytest

from transliterate import validate_translation


BASE = """🎬 PROGRAMA:
    show "keep"
    show 🌐 "Hello"
📋 DESCRIPCIÓN:
    This is English description.
    It can be translated freely.
    Emojis and keywords are allowed here: show if while 🛠 🔍 🌐
▶️ INICIAR:
    show "run"
"""

ES_OK = """🎬 PROGRAMA:
    show "keep"
    show 🌐 "Hola"
📋 DESCRIPCIÓN:
    Esta es una descripción en español.
    Se puede traducir libremente.
    Aquí pueden aparecer palabras como show/if/while o emojis 🛠 🔍 🌐 sin afectar al código.
▶️ INICIAR:
    show "run"
"""

PT_OK = """🎬 PROGRAMA:
    show "keep"
    show 🌐 "Olá"
📋 DESCRIPCIÓN:
    Esta é uma descrição em português.
    Pode ser traduzida livremente.
▶️ INICIAR:
    show "run"
"""

BAD_KEYWORD_TRANSLATED = """🎬 PROGRAMA:
    mostrar "keep"
    show 🌐 "Hola"
📋 DESCRIPCIÓN:
    ok
▶️ INICIAR:
    show "run"
"""

BAD_UNMARKED_STRING_CHANGED = """🎬 PROGRAMA:
    show "changed"
    show 🌐 "Hola"
📋 DESCRIPCIÓN:
    ok
▶️ INICIAR:
    show "run"
"""

BAD_EMOJI_CHANGED = """🎬 PROGRAMA:
    show "keep"
    show 🧭 "Hola"
📋 DESCRIPCIÓN:
    ok
▶️ INICIAR:
    show "run"
"""

def test_translation_ok_es():
    v = validate_translation(BASE, ES_OK, "base", "es")
    assert v == []

def test_translation_ok_pt():
    v = validate_translation(BASE, PT_OK, "base", "pt")
    assert v == []

def test_reject_translated_keyword():
    v = validate_translation(BASE, BAD_KEYWORD_TRANSLATED, "base", "bad")
    assert v and any("Token" in x.message or "mismatch" in x.message for x in v)

def test_reject_unmarked_string_change():
    v = validate_translation(BASE, BAD_UNMARKED_STRING_CHANGED, "base", "bad2")
    assert v and any("Unmarked string literal changed" in x.message for x in v)

def test_reject_marker_emoji_change():
    v = validate_translation(BASE, BAD_EMOJI_CHANGED, "base", "bad3")
    assert v and any("Token value mismatch" in x.message or "kind mismatch" in x.message for x in v)
