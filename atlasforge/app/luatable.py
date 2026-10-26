"""Tiny reader for the Lua table literals Atlas Map Forge writes (start boxes), so the app can draw them.

Only handles what our own files contain: tables, strings, numbers, `name = value`, `[n] = value`.
Code before the first `return {` (for example an `if ... then` branch) is skipped; the first returned
table is read.
"""
import re

_TOKEN = re.compile(r'\s*(?:(--[^\n]*)|("(?:[^"\\]|\\.)*")|(-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)|([A-Za-z_]\w*)|(\[)|(\])|(\{)|(\})|(=)|(,|;))')


def _tokens(s):
    pos = 0
    out = []
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            if s[pos:].strip() == "":
                break
            raise ValueError(f"unexpected Lua at {pos}: {s[pos:pos + 20]!r}")
        pos = m.end()
        if m.group(1):
            continue
        for i, kind in enumerate(("str", "num", "name", "[", "]", "{", "}", "=", ","), start=2):
            if m.group(i) is not None:
                v = m.group(i)
                if kind == "str":
                    v = bytes(v[1:-1], "utf8").decode("unicode_escape")
                elif kind == "num":
                    v = float(v)
                out.append((kind, v))
                break
    return out


def _table(tok, i):
    assert tok[i][0] == "{"
    i += 1
    arr, rec = [], {}
    while tok[i][0] != "}":
        if tok[i][0] == "[":
            key = tok[i + 1][1]
            key = int(key) if isinstance(key, float) and key.is_integer() else key
            i += 4                                  # [ key ] =
            val, i = _value(tok, i)
            rec[key] = val
        elif tok[i][0] == "name" and i + 1 < len(tok) and tok[i + 1][0] == "=":
            key = tok[i][1]
            val, i = _value(tok, i + 2)
            rec[key] = val
        else:
            val, i = _value(tok, i)
            arr.append(val)
        if tok[i][0] == ",":
            i += 1
    if rec and not arr:
        return rec, i + 1
    if arr and not rec:
        return arr, i + 1
    rec.update({k + 1: v for k, v in enumerate(arr)})
    return rec, i + 1


def _value(tok, i):
    kind, v = tok[i]
    if kind == "{":
        return _table(tok, i)
    if kind in ("str", "num"):
        return v, i + 1
    if kind == "name":
        return {"true": True, "false": False, "nil": None}.get(v, v), i + 1
    raise ValueError(f"unexpected token {tok[i]}")


def first_returned_table(src):
    k = src.find("return")
    while k >= 0:
        rest = src[k + 6:].lstrip()
        if rest.startswith("{"):
            return _value(_tokens(rest[:_matching_brace(rest) + 1]), 0)[0]
        k = src.find("return", k + 6)
    raise ValueError("no 'return {' found")


def _matching_brace(s):
    depth, instr = 0, False
    for i, c in enumerate(s):
        if instr:
            if c == '"' and s[i - 1] != "\\":
                instr = False
        elif c == '"':
            instr = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces")


def startboxes(src):
    """-> [{team, name, short, polygons: [[[x, z], ...]], startpoints: [[x, z]]}] from map_startboxes.lua."""
    t = first_returned_table(src)
    out = []
    for team in sorted(k for k in t if isinstance(k, int)):
        e = t[team]
        polys = [[[float(p[0]), float(p[1])] for p in poly] for poly in e.get("boxes", [])]
        sps = [[float(p[0]), float(p[1])] for p in e.get("startpoints", [])]
        out.append(dict(team=team, name=e.get("nameLong", f"Team {team}"), short=e.get("nameShort", str(team)),
                        polygons=polys, startpoints=sps))
    return out
