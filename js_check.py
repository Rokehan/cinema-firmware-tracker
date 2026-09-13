#!/usr/bin/env python3
"""
js_check.py  -  find why the page's JavaScript stopped running.
Offline. Reads index.html and build_site.py. Writes nothing.

Symptom: clicking a plate does nothing and the search box no longer filters.
Both live in the same inline script, so the script is failing at parse time and
nothing in it runs. The likely cause is patch_cat_single.py, whose regex cut
from a comment to the first "});" and may have removed only part of a block.

This prints:
  1. every inline script in index.html with a brace, paren and bracket balance
     check, which is how a truncated block shows up
  2. the region around the category filter and apply(), with line numbers
  3. any obvious dangling fragment: an orphan "});", a function that never
     closes, or a name used but never declared
  4. the same region in build_site.py's template, since that is what to patch

Run:  python js_check.py
"""
from pathlib import Path
import re
import sys

NL = chr(10)


def balance(src):
    """Counts, ignoring strings and comments well enough for a sanity check."""
    depth = {"{": 0, "(": 0, "[": 0}
    pairs = {"}": "{", ")": "(", "]": "["}
    i = 0
    n = len(src)
    line = 1
    problems = []
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == NL:
            line += 1
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < n and src[i] != NL:
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                if src[i] == NL:
                    line += 1
                i += 1
            i += 2
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            while i < n and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                if src[i] == NL:
                    line += 1
                    break
                i += 1
            i += 1
            continue
        if ch in depth:
            depth[ch] += 1
        elif ch in pairs:
            opener = pairs[ch]
            depth[opener] -= 1
            if depth[opener] < 0:
                problems.append("line " + str(line) + ": extra '" + ch + "'")
                depth[opener] = 0
        i += 1
    for k, v in depth.items():
        if v:
            problems.append("unclosed '" + k + "' x" + str(v))
    return problems


def main():
    idx = Path("index.html")
    if not idx.exists():
        sys.exit("index.html not found")
    html = idx.read_text(encoding="utf-8", errors="replace")

    print("=" * 70)
    print("1. inline scripts in index.html")
    print("=" * 70)
    scripts = list(re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S | re.I))
    print("  scripts: " + str(len(scripts)))
    worst = None
    for k, m in enumerate(scripts):
        body = m.group(1)
        if len(body.strip()) < 20:
            continue
        probs = balance(body)
        before = html[:m.start()].count(NL) + 1
        print("  script %d: starts at html line %d, %d chars"
              % (k + 1, before, len(body)))
        if probs:
            print("    PROBLEMS: " + "; ".join(probs[:6]))
            if worst is None:
                worst = (k, before, body, probs)
        else:
            print("    balanced")
    print()

    print("=" * 70)
    print("2. the category filter and apply() in index.html")
    print("=" * 70)
    lines = html.split(NL)
    for i, line in enumerate(lines):
        if re.search(r"var cat |var cats |catButtons|inCat|function apply|"
                     r"var make |buttons\.forEach|dataset\.category", line):
            lo = max(0, i - 2)
            hi = min(len(lines), i + 6)
            print("  --- html line " + str(i + 1) + " ---")
            for j in range(lo, hi):
                print("    %5d| %s" % (j + 1, lines[j][:130]))
            print()
            break
    # dump the whole filter area once
    m = re.search(r"var plates = ", html)
    if m:
        start = html[:m.start()].count(NL)
        print("  filter block, 60 lines from line " + str(start + 1) + ":")
        for j in range(start, min(len(lines), start + 60)):
            print("    %5d| %s" % (j + 1, lines[j][:130]))
    print()

    print("=" * 70)
    print("3. dangling fragments")
    print("=" * 70)
    for pat, label in [
            (r"^\s*\}\);\s*$", "a bare '});' line"),
            (r"cats\.", "leftover 'cats.' from the multi-select version"),
            (r"aria-pressed", "leftover aria-pressed"),
            (r"var cat\b", "single-select 'var cat'"),
            (r"var cats\b", "multi-select 'var cats'")]:
        hits = [i + 1 for i, l in enumerate(lines) if re.search(pat, l)]
        print("  %-46s %s" % (label, (str(len(hits)) + " at lines "
                                      + ", ".join(str(h) for h in hits[:8]))
                              if hits else "none"))
    print()

    print("=" * 70)
    print("4. the same region in build_site.py")
    print("=" * 70)
    site = Path("build_site.py")
    if not site.exists():
        print("  build_site.py not found")
        return
    slines = site.read_text(encoding="utf-8", errors="replace").split(NL)
    for i, line in enumerate(slines):
        if re.search(r"var cat |var cats |catButtons|inCat|Equipment type|"
                     r"Equipment categories", line):
            lo = max(0, i - 3)
            hi = min(len(slines), i + 22)
            print("  from build_site.py line " + str(i + 1) + ":")
            for j in range(lo, hi):
                print("    %5d| %s" % (j + 1, slines[j][:130]))
            break
    print()


if __name__ == "__main__":
    main()
