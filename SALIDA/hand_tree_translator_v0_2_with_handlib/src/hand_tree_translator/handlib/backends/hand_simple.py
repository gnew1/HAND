    from __future__ import annotations

    from typing import Any, Dict, List, Optional

    from ..types import TranslationResult
    from ..lexicon import EmojiLexicon

    # This emitter takes either:
    #   - a Program/Node object graph (recommended), OR
    #   - a dict-like IR (fallback)
    # For now we accept dict; future: tighten to explicit nodes.

    def emit_hand_simple(res: TranslationResult, opts: Dict[str, Any]) -> TranslationResult:
        lex: EmojiLexicon = opts.get("lexicon")  # injected by caller
        use_emojis: bool = bool(opts.get("use_emojis", True))

        ir = res.hand_ir
        if ir is None:
            res.ok = False
            res.passthrough_reason = res.passthrough_reason or "missing_ir"
            return res

        # If IR is dict (from dataclass __dict__), normalize.
        # Expected keys: kind, body
        def k(d): return d.get("kind")

        def e_expr(expr: Dict[str,Any]) -> str:
            kind = k(expr)
            if kind == "Name":
                return expr["id"]
            if kind == "Const":
                v = expr["value"]
                if isinstance(v, str):
                    return json_dumps(v)
                return str(v)
            if kind == "BinOp":
                return f"({e_expr(expr['left'])} {expr['op']} {e_expr(expr['right'])})"
            if kind == "Compare":
                return f"({e_expr(expr['left'])} {expr['op']} {e_expr(expr['right'])})"
            if kind == "Call":
                args = ", ".join(e_expr(a) for a in expr.get("args", []))
                return f"{expr['func']}({args})"
            return f"<expr:{kind}>"

        import json
        def json_dumps(s: str) -> str:
            return json.dumps(s, ensure_ascii=False)

        def tag(t: str, fallback: str) -> str:
            if not use_emojis or lex is None:
                return fallback
            return lex.emoji_for(t, fallback) or fallback

        def emit_stmt(stmt: Dict[str,Any], indent: int) -> List[str]:
            ind = "  " * indent
            kind = k(stmt)
            out=[]
            if kind == "Assign":
                out.append(f"{ind}{tag('core.assign','assign')} {stmt['target']} = {e_expr(stmt['value'])}")
            elif kind == "If":
                out.append(f"{ind}{tag('flow.if','if')} {e_expr(stmt['test'])}:")
                for s in stmt.get("then", []):
                    out += emit_stmt(s, indent+1)
                if stmt.get("otherwise"):
                    out.append(f"{ind}{tag('flow.else','else')}:")
                    for s in stmt.get('otherwise', []):
                        out += emit_stmt(s, indent+1)
            elif kind == "While":
                out.append(f"{ind}{tag('flow.while','while')} {e_expr(stmt['test'])}:")
                for s in stmt.get("body", []):
                    out += emit_stmt(s, indent+1)
            elif kind == "ForRange":
                out.append(f"{ind}{tag('flow.for','for')} {stmt['var']} in range({e_expr(stmt['start'])}, {e_expr(stmt['stop'])}, {e_expr(stmt['step'])}):")
                for s in stmt.get("body", []):
                    out += emit_stmt(s, indent+1)
            elif kind == "FuncDef":
                params = ", ".join(stmt.get("params", []))
                out.append(f"{ind}{tag('flow.func','func')} {stmt['name']}({params}):")
                for s in stmt.get("body", []):
                    out += emit_stmt(s, indent+1)
            elif kind == "Return":
                if stmt.get("value") is None:
                    out.append(f"{ind}{tag('flow.return','return')}")
                else:
                    out.append(f"{ind}{tag('flow.return','return')} {e_expr(stmt['value'])}")
            elif kind == "ExprStmt":
                call = e_expr(stmt["expr"])
                # Map print(...) -> show
                if call.startswith("print("):
                    out.append(f"{ind}{tag('io.print','show')} {call[len('print('):-1]}")
                else:
                    out.append(f"{ind}{call}")
            else:
                out.append(f"{ind}# <unsupported stmt {kind}>")
            return out

        # If we got dataclass __dict__, the children are objects not dicts sometimes; convert via json roundtrip.
        def to_plain(obj):
            return json.loads(json.dumps(obj, default=lambda o: o.__dict__, ensure_ascii=False))

        plain = to_plain(ir)
        if plain.get("kind") != "Program":
            res.ok = False
            res.passthrough_reason = res.passthrough_reason or "ir_not_program"
            return res

        lines = ["# HAND simple (generated)", ""]
        for s in plain.get("body", []):
            lines += emit_stmt(s, 0)
        res.ok = True
        res.hand_text = "
".join(lines).rstrip() + "
"
        res.hand_ir = plain
        return res
