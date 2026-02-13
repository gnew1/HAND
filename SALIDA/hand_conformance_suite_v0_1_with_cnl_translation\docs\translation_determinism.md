# Deterministic Translation (CNL) — HAND v0.1

## Goal

Allow authors to write human-facing explanations in any natural language **without changing the executable code**.

This keeps the HAND lexical layer stable and preserves *determinism, auditability, and conformance testing* across locales.

## Normative rule

A translated `.hand` file is valid **iff**:

- **CODE is identical** between base and candidate, and
- only the following MAY change:
  1) the body of the `📋 DESCRIPCIÓN:` block (indented lines under the header), and
  2) string literals explicitly marked translatable with the 🌐 marker.

Everything else MUST remain unchanged:
- keywords (`show`, `if`, `while`, …)
- identifiers
- operators / punctuation
- numbers
- emojis used as semantic tokens
- indentation structure / block layout

## `📋 DESCRIPCIÓN:` block

Definition:
- starts at a line whose `strip()` equals `📋 DESCRIPCIÓN:`
- includes subsequent lines that are:
  - blank, or
  - indented with **>= 4 spaces**
- ends at first non-empty line that is not indented.

The header line `📋 DESCRIPCIÓN:` is part of **CODE** and MUST remain canonical.

## Marked translatable literals

A string literal token is translatable only if immediately preceded (ignoring newlines) by the canonical marker emoji:

- marker: `🌐`

Example:

```hand
show 🌐 "Hola"
