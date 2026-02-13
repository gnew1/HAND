# HAND Language Evolution Policy (v0.1 baseline)

This document defines the **controlled extension process** for HAND so that:
- v0.1 remains **stable and deterministic**
- new keywords/emojis/types can be added without breaking existing programs
- every change is backed by conformance tests and (when possible) automatic migration tooling

> **Golden rule:** existing v0.1 programs MUST continue to compile and run unchanged under any v0.1.x and any v0.(1+).0 release,
> unless the release is explicitly a **breaking** major version bump.

---

## 1. Versioning model (SemVer)

HAND uses SemVer: **MAJOR.MINOR.PATCH**

### PATCH (0.1.x) — bugfix / clarity
MUST NOT:
- change tokenization
- change grammar
- change type rules
- change runtime semantics
- introduce new keywords/emojis/types

MAY:
- improve diagnostics
- fix compiler bugs that violated the spec
- tighten validation only when the spec already required it
- add **new tests** (conformance grows)

### MINOR (0.Y.0, e.g. 0.2.0) — additive, backwards compatible
MUST:
- keep all v0.1 programs valid
- keep semantics for existing constructs unchanged

MAY:
- add new **reserved emojis** becoming **active**
- add new keywords/types as additive features
- add new IR fields with defaults (schema additive)
- add new lints (as warnings) but not errors for v0.1 programs

### MAJOR (1.0.0, 2.0.0...) — breaking
MAY:
- change grammar / semantics / tokenization
- remove features
MUST:
- ship `handfix` migrations for common patterns
- ship a compatibility mode for previous MAJOR when feasible

---

## 2. Extension surfaces

HAND extends in three primary surfaces:
1) **Emoji token** (semantic operator)
2) **Keyword** (ASCII reserved word)
3) **Type** (static type system construct)

### 2.1 Adding an emoji (reserved → active)

#### Requirements (MUST)
- Emoji must be in the **Reserved Emoji Registry** (spec-owned list).
- 1 emoji = 1 semantic function (**no reuse**).
- Define:
  - token kind (operator/marker/section/etc.)
  - typing rule(s) if applicable
  - runtime semantics (Ω/Σ impact, effects)
  - lowering to IR op(s)
  - codegen mapping for each backend (or explicit degradation)
- Provide **examples correct/incorrect**.

#### Process
1) Open a proposal: `proposals/emoji_<NAME>.md`
2) Assign an ID and freeze semantics.
3) Add to `lexicon/emoji_reserved.json` (reserved) or `lexicon/emoji_active.json` (active).
4) Add conformance tests (see §4).
5) Implement in: lexer → parser → typechecker → interpreter → lowering → codegen.
6) `handfmt` MUST preserve and normalize placement.

### 2.2 Adding a keyword

#### Requirements (MUST)
- Keywords are ASCII lowercase (`snake_case`) unless section headers.
- No synonyms. Adding a keyword MUST NOT introduce ambiguity.
- Update:
  - lexer keyword table
  - grammar (PEG/EBNF)
  - AST node (strict)
  - typing rules
  - interpreter semantics
  - IR lowering (stable op)
  - codegen per target (or explicit degradation)

#### Anti-ambiguity gate
- The new keyword MUST NOT create shift/reduce ambiguity with existing tokens.
- If precedence matters, specify and test precedence explicitly.

### 2.3 Adding a type

#### Requirements (MUST)
- Define:
  - syntax (T, T?, List[T], etc.)
  - Γ ⊢ e : T rules (normative)
  - runtime representation (if any)
  - mapping to targets (Python/Rust/SQL/HTML/WASM subset)
  - how it interacts with VERIFY/ENSURE and contracts
- If the type has no runtime representation, it must be erased with validated checks.

---

## 3. Compatibility rules

### 3.1 Backwards compatibility (MINOR)
- Existing tokens retain meaning.
- Existing IR ops retain meaning.
- New features MUST be **feature-gated** in conformance (tests must show old programs still pass).

### 3.2 Forward compatibility (IR)
- IR schema additions MUST be optional with defaults.
- Consumers must ignore unknown fields.

---

## 4. Tests that MUST be added for every extension

For each new emoji/keyword/type, add tests across the pipeline:

### 4.1 Lexer
- tokenization golden tests (bytes → tokens stable)
- invalid bytes / ZWJ / surrogate edge tests if emoji-related

### 4.2 Parser
- parse success case(s)
- parse failure case(s) with specific diagnostics
- round-trip: parse → format → parse equivalence

### 4.3 Typechecker
- 3+ OK cases
- 3+ error cases (type mismatch, missing VERIFY, etc.)

### 4.4 Interpreter (ground truth)
- execution trace Ω equality
- final store Σ equality

### 4.5 IR Lowering
- IR snapshot test (schema-valid)
- origin tracing preserved

### 4.6 Capabilities / Effects
- declared vs required capability test (if applicable)

### 4.7 Codegen
- python equivalence against interpreter for all executable cases
- degraded targets must emit a clear degradation reason

Minimum: **12 tests per new feature** (spread across stages).

---

## 5. Migration tooling

### 5.1 `handfmt` (formatter)
- Canonicalizes indentation, spacing, and section ordering
- MUST NOT change semantics
- Used as the first step of any codemod to reduce diff noise

### 5.2 `handfix` (codemod)
- Applies version-to-version migrations
- Runs `handfmt` after transformations
- Must produce a machine-readable report:
  - which rules fired
  - which spans changed
  - whether manual review is required

#### Rule structure
Each codemod rule:
- has an ID: `FX<major><minor>.<nn>`
- declares source version range (e.g. 0.1.* → 0.2.0)
- matches AST patterns, not raw text (except trivial lexical renames)

---

## 6. Extension checklist (copy/paste)

- [ ] Proposal doc created
- [ ] Spec updated (lexicon/grammar/types/semantics)
- [ ] Lexer supports token
- [ ] Parser + AST updated
- [ ] Typechecker updated
- [ ] Interpreter updated (Ω/Σ)
- [ ] IR + schema updated (additive)
- [ ] Capabilities/effects updated
- [ ] Codegen updated or degradation declared
- [ ] Conformance tests added (min 12)
- [ ] `handfmt` keeps formatting stable
- [ ] `handfix` migration added if needed

