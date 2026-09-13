#!/usr/bin/env python3
"""
canon_shape_peek.py  -  offline, no network, writes nothing.

Two questions only:
  1. exact field names + value shapes in canon_cameras.json
  2. how build_site.state_of() classifies a non-RED, non-Sony page link,
     and the exact RED block in build_feed.py to mirror its style

Run:  python canon_shape_peek.py > peek_canon_shape.txt
"""
from pathlib import Path
import json

NL = chr(10)


def show(val, depth=0):
    """Type + shape of a value, truncated. Never dumps whole changelogs."""
    pad = "  " * depth
    if isinstance(val, str):
        s = val.replace(NL, "\\n")
        if len(s) > 90:
            return "str(%d) %s..." % (len(val), s[:90])
        return "str(%d) %s" % (len(val), s)
    if isinstance(val, bool):
        return "bool %s" % val
    if isinstance(val, (int, float)):
        return "%s %s" % (type(val).__name__, val)
    if val is None:
        return "None"
    if isinstance(val, list):
        if not val:
            return "list(0) []"
        out = ["list(%d), first item:" % len(val)]
        out.append(pad + "    " + show(val[0], depth + 1))
        return NL.join(out)
    if isinstance(val, dict):
        out = ["dict(%d keys)" % len(val)]
        for k, v in val.items():
            out.append(pad + "      ." + str(k) + " = " + show(v, depth + 1))
        return NL.join(out)
    return type(val).__name__


def dump_json():
    p = Path("canon_cameras.json")
    print("=" * 70)
    print("canon_cameras.json")
    print("=" * 70)
    if not p.exists():
        print("  !! not found")
        return
    rows = json.loads(p.read_text(encoding="utf-8"))
    print("rows:", len(rows))
    print()
    # union of keys across all rows: a field missing on row 0 still matters
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    print("union of keys across all %d rows:" % len(rows))
    for k in keys:
        present = sum(1 for r in rows if r.get(k) not in (None, "", [], {}))
        print("   %-24s non-empty in %d/%d rows" % (k, present, len(rows)))
    print()

    # a row with the most filled in, so every field shows a real example
    best = max(rows, key=lambda r: sum(1 for v in r.values() if v))
    print("-" * 70)
    print("RICHEST ROW, full shape:", best.get("product") or best.get("name") or "?")
    print("-" * 70)
    for k in keys:
        print("  ." + str(k) + " = " + show(best.get(k), 1))
    print()

    # a sparse row too: shows what an install-less body looks like
    worst = min(rows, key=lambda r: sum(1 for v in r.values() if v))
    print("-" * 70)
    print("SPARSEST ROW, full shape:", worst.get("product") or worst.get("name") or "?")
    print("-" * 70)
    for k in keys:
        print("  ." + str(k) + " = " + show(worst.get(k), 1))
    print()


def dump_lines(name, ranges):
    p = Path(name)
    print("=" * 70)
    print(name)
    print("=" * 70)
    if not p.exists():
        print("  !! not found")
        return
    lines = p.read_text(encoding="utf-8", errors="replace").split(NL)
    for lo, hi in ranges:
        print("--- lines %d-%d ---" % (lo, hi))
        for i in range(lo - 1, min(hi, len(lines))):
            print("    %4d| %s" % (i + 1, lines[i]))
        print()


def main():
    print("cwd:", Path.cwd())
    print()
    dump_json()
    # RED block to mirror, and the plate-state + panel logic
    dump_lines("build_feed.py", [(174, 202)])
    dump_lines("build_site.py", [(560, 600), (600, 664)])


if __name__ == "__main__":
    main()
