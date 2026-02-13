from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import re

from handc.lexer import lex, Token
from handc.diagnostics import Diagnostic


# Translation Determinism Contract (HAND v0.1)
#
# Rule: The CODE must not change across languages. Only:
#   (1) the 📋 DESCRIPCIÓN block contents MAY change
#   (2) string literals explicitly marked as translatable MAY change
#
# Everything else MUST be byte-for-byte identical at token level: keywords, identifiers,
# operators, numbers, emojis, indentation structure, etc.
#
# Marked translatable literals:
#   A string literal token is considered "translatable" iff the immediately preceding
#   non-whitespace token is the canonical marker emoji 🌐.
#
# Example:
#   show 🌐 "Hola"     # allowed to translate "Hola" -> "Hello" (marker stays)
#
# Note: This script validates. It does not perform machine translation.


TRANSLATABLE_MARKER = "🌐"
DESCRIPTION_HEADER = "📋 DESCRIPCIÓN:"  # canonical header line, must remain in code


@dataclass(frozen=True)
class SpanRef:
    file: str
    line: int
    col: int
    end_col: int


@dataclass(frozen=True)
class Violation:
    where: SpanRef
    message: str


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _description_lines(src: str) -> Set[int]:
    """
    Return 1-based line numbers that are inside the 📋 DESCRIPCIÓN: block.

    Definition (v0.1):
      - The block starts at the line that begins with DESCRIPTION_HEADER.
      - The block body is the subsequent indented lines (>= 4 spaces).
      - The block ends at the first non-empty line that is not indented (dedent to col 0),
        or end of file.
    """
    lines = src.splitlines()
    desc_start_idx: Optional[int] = None
    for i, ln in enumerate(lines):
        if ln.strip() == DESCRIPTION_HEADER:
            desc_start_idx = i
            break
    if desc_start_idx is None:
        return set()

    editable: Set[int] = set()
    editable.add(desc_start_idx + 1)  # header line itself is allowed to move? No. But content in body is allowed.
    # Actually: header is CODE and must remain. We'll mark only body as editable.
    editable.remove(desc_start_idx + 1)

    for j in range(desc_start_idx + 1, len(lines)):
        ln = lines[j]
        if ln.strip() == "":
            # blank lines in description are allowed; keep them in editable region
            editable.add(j + 1)
            continue
        if ln.startswith("    "):  # 4 spaces
            editable.add(j + 1)
            continue
        # dedent ends description block
        break
    return editable




def _mask_description(src: str, editable_lines: Set[int]) -> str:
    """
    Replace DESCRIPTION-body lines with lexable placeholders so the HAND lexer can run.

    Rationale: HAND v0.1 lexer is intentionally strict; natural language punctuation (.,!?)
    may not be valid as code tokens. Since DESCRIPTION is non-code, we mask it before lexing.
    """
    out_lines=[]
    for i, ln in enumerate(src.splitlines(), start=1):
        if i in editable_lines:
            if ln.strip()=="":
                out_lines.append("")
            else:
                # preserve indentation (>=4 spaces) and replace remainder with an empty string literal
                m = re.match(r"^(\s+)", ln)
                indent = m.group(1) if m else ""
                out_lines.append(f"{indent}\"\"")
        else:
            out_lines.append(ln)
    return "\n".join(out_lines) + ("\n" if src.endswith("\n") else "")


def _is_translatable_string(tokens: List[Token], idx: int) -> bool:
    """
    Returns True if tokens[idx] is a STRING token and is preceded by a 🌐 marker emoji.
    """
    t = tokens[idx]
    if t.kind != "STRING":
        return False

    # find previous non-NL token (lexer doesn't emit whitespace tokens; skip NL only)
    k = idx - 1
    while k >= 0 and tokens[k].kind in ("NL",):
        k -= 1
    if k < 0:
        return False
    prev = tokens[k]
    return prev.kind == "EMOJI" and prev.value == TRANSLATABLE_MARKER


def validate_translation(base_src: str, cand_src: str, base_name: str = "base", cand_name: str = "candidate") -> List[Violation]:
    violations: List[Violation] = []

    base_desc = _description_lines(base_src)
    cand_desc = _description_lines(cand_src)

    # The DESCRIPTION header must exist in both or neither; if it exists in one, it's a code delta.
    base_has = DESCRIPTION_HEADER in base_src.splitlines()
    cand_has = DESCRIPTION_HEADER in cand_src.splitlines()
    if base_has != cand_has:
        violations.append(Violation(SpanRef(cand_name, 1, 1, 1), "📋 DESCRIPCIÓN block presence differs between base and candidate."))
        return violations

    base_src_masked = _mask_description(base_src, base_desc)
    cand_src_masked = _mask_description(cand_src, cand_desc)

    base_toks, base_diags = lex(base_src_masked, base_name)
    cand_toks, cand_diags = lex(cand_src_masked, cand_name)

    # Lexing MUST be deterministic and error-free for both.
    if base_diags:
        violations.append(Violation(SpanRef(base_name, 1, 1, 1), f"Base lex errors: {len(base_diags)}"))
        return violations
    if cand_diags:
        # Candidate may add non-ASCII etc, but must remain valid UTF-8 and valid tokens.
        first = cand_diags[0]
        sp = getattr(first, "span", None)
        if sp is not None and hasattr(sp, "line"):
            where = SpanRef(cand_name, sp.line, sp.col, sp.end_col)
        else:
            where = SpanRef(cand_name, 1, 1, 1)
        violations.append(Violation(where, f"Candidate lex errors: {len(cand_diags)}"))
        return violations

    # Compare token streams with allowed edit windows.
    # Strategy: walk both lists in lockstep. Outside editable areas:
    #   - token kind/value/span.line must match (span.cols may shift if description changed; we ignore col for comparison).
    # Inside editable areas:
    #   - if token is a STRING with 🌐 marker, allow value differences
    #   - otherwise, inside description block, ignore differences (but do not allow emojis/keywords outside block)
    #
    # For robust comparison despite description edits, we treat tokens in description lines as "skipped":
    # we remove those tokens from both streams and compare the remaining streams.

    def filter_tokens(tokens: List[Token], editable_lines: Set[int]) -> List[Tuple[int, Token]]:
        kept=[]
        for i,t in enumerate(tokens):
            if t.span.line in editable_lines:
                continue
            kept.append((i,t))
        return kept

    base_kept = filter_tokens(base_toks, base_desc)
    cand_kept = filter_tokens(cand_toks, cand_desc)

    # Now, compare kept streams allowing marked string deltas.
    bi=ci=0
    while bi < len(base_kept) and ci < len(cand_kept):
        bidx, bt = base_kept[bi]
        cidx, ct = cand_kept[ci]

        # Align on kind as a first approximation.
        if bt.kind != ct.kind:
            violations.append(Violation(
                SpanRef(cand_name, ct.span.line, ct.span.col, ct.span.end_col),
                f"Token kind mismatch outside 📋 DESCRIPCIÓN: base={bt.kind} candidate={ct.kind}"
            ))
            return violations

        # For strings: allow change only if both are translatable strings (🌐 marker) in their respective streams.
        if bt.kind == "STRING":
            base_ok = _is_translatable_string(base_toks, bidx)
            cand_ok = _is_translatable_string(cand_toks, cidx)
            if base_ok and cand_ok:
                # Marker must remain identical; enforced by token stream since 🌐 emoji token is outside description
                pass
            else:
                if bt.value != ct.value:
                    violations.append(Violation(
                        SpanRef(cand_name, ct.span.line, ct.span.col, ct.span.end_col),
                        "Unmarked string literal changed (only 🌐-marked literals may change)."
                    ))
                    return violations
        else:
            # All other tokens must match value exactly.
            if bt.value != ct.value:
                violations.append(Violation(
                    SpanRef(cand_name, ct.span.line, ct.span.col, ct.span.end_col),
                    f"Token value mismatch outside 📋 DESCRIPCIÓN: base={bt.value!r} candidate={ct.value!r}"
                ))
                return violations

        bi += 1
        ci += 1

    if bi != len(base_kept) or ci != len(cand_kept):
        # Token count differs outside description; illegal.
        where = SpanRef(cand_name, 1, 1, 1)
        violations.append(Violation(where, "Token stream length differs outside 📋 DESCRIPCIÓN (illegal code change)."))
        return violations

    # Additional: ensure DESCRIPTION header line itself is unchanged (since we filtered body only).
    # We compare raw lines containing the header.
    if base_has:
        base_lines = base_src.splitlines()
        cand_lines = cand_src.splitlines()
        base_hdr_idx = next(i for i,l in enumerate(base_lines) if l.strip()==DESCRIPTION_HEADER)
        cand_hdr_idx = next(i for i,l in enumerate(cand_lines) if l.strip()==DESCRIPTION_HEADER)
        if base_lines[base_hdr_idx].strip() != cand_lines[cand_hdr_idx].strip():
            violations.append(Violation(SpanRef(cand_name, cand_hdr_idx+1, 1, 1), "📋 DESCRIPCIÓN header line changed (must remain canonical)."))
            return violations

    return violations


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Validate deterministic CNL translation for HAND v0.1")
    ap.add_argument("--base", required=True, help="Base .hand file (canonical code)")
    ap.add_argument("--candidate", required=True, help="Translated .hand file to validate")
    args = ap.parse_args(argv)

    base_p = Path(args.base)
    cand_p = Path(args.candidate)
    base_src = _read_text(base_p)
    cand_src = _read_text(cand_p)

    v = validate_translation(base_src, cand_src, base_name=str(base_p), cand_name=str(cand_p))
    if v:
        for viol in v:
            print(f"{viol.where.file}:{viol.where.line}:{viol.where.col}: {viol.message}")
        return 2
    print("OK: translation is deterministic (code unchanged).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
