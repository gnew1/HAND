# HAND Core v0.1 (Normative Specification)

**Status:** Stable (v0.1.0)  
**Scope:** This document defines the executable core of HAND: **Lexicon**, **Grammar**, **Type System**, **Operational Semantics**, **Effects/Capabilities**, and **Supervision Levels**.

This spec uses the key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** as in RFC 2119.

---

## 0. Non‑negotiable norms

1. **Determinism**  
   - Given identical UTF‑8 bytes, a conforming implementation **MUST** produce identical tokens, AST, IR, diagnostics (modulo file path), and interpreter traces.  
   - The interpreter is the **source of truth** for runtime behavior. Codegen backends **MUST** match interpreter observables for supported subsets.

2. **No synonyms**  
   - The lexicon is closed: reserved words and emojis have **single canonical forms**. Implementations **MUST NOT** accept synonyms, aliases, or translated keywords.

3. **No implicit coercions**  
   - The type system **MUST NOT** perform implicit numeric or textual coercions. All conversions **MUST** be explicit (future feature; not in v0.1).

4. **Effects are visible**  
   - Any operation that can cause IO or external interaction **MUST** be represented explicitly in the program (keyword/emoji/operator) and **MUST** be traceable (origin metadata).

5. **Auditability**  
   - Implementations **MUST** support stable origin references for diagnostics and (when emitting code) SHOULD support trace emission.

---

## 1. Source text and encoding

- Source files are UTF‑8.  
- Tabs are **forbidden**. Indentation uses **exactly 4 spaces** per level.  
- Newlines MAY be `\n` or `\r\n`; they are normalized during lexing.

---

## 2. Lexicon (v0.1)

### 2.1 Keywords (canonical, ASCII)

Conforming implementations **MUST** recognize the following keywords as reserved:

**Statements / control**
- `if`, `else`, `while`, `return`

**Boolean ops**
- `and`, `or`, `not`

**IO**
- `show`, `ask`

**Literals**
- `null`, `true`, `false`

**Type constructors**
- `List`, `Map`, `Record`, `Result`, `Optional`

> Note: Type constructors are identifiers in the grammar but reserved at the type level.

**Prohibited synonyms (non‑exhaustive)**  
Implementations MUST NOT accept:
- `print` (synonym for `show`)
- `input` (synonym for `ask`)
- `elif` (synonym for `else if`)
- any localized translation (`si`, `mostrar`, `preguntar`, etc.)

### 2.2 Emoji tokens

In v0.1, emojis are reserved for **trace/origin and sectioning**. The following are canonical:

**Audit / origin actors**
- `👤` human
- `🤖` AI
- `⭐` trusted/verified source

**Diagnostics severity markers (used in reports)**
- `⚠️` warning
- `🐛` error
- `💀` fatal

**Capabilities marker**
- `🛡️` denotes capability declarations (in metadata/IR; not required in surface syntax subset)

**Contract markers (subset)**
- `🔍` VERIFY
- `🎯` ENSURE

> Implementations MUST treat emojis as single tokens even when their UTF‑8 encoding involves variation selectors. The lexer MUST NOT normalize them into other codepoints.

### 2.3 Identifiers

- Identifier regex (ASCII subset): `[A-Za-z_][A-Za-z0-9_]*`
- Naming conventions:
  - variables/functions: `snake_case` SHOULD be used
  - types: `PascalCase` SHOULD be used
- Identifiers MUST NOT shadow reserved keywords.

### 2.4 Literals

- Integers: base‑10 digits, no separators (e.g., `0`, `12`, `-7`)
- Floats: digits with a dot (e.g., `3.14`, `-0.5`)
- Strings: double quotes `"..."` with escapes `\n`, `\t`, `\"`, `\\`
- Booleans: `true`, `false`
- Null: `null`

---

## 3. Grammar (EBNF)

### 3.1 Layout

- Blocks are defined by INDENT/DEDENT tokens produced by the lexer.
- Each INDENT level is exactly +4 spaces.
- Empty lines MAY appear anywhere and do not affect indentation.

### 3.2 EBNF

