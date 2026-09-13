#!/usr/bin/env python3
"""
canon_merge_peek.py  -  offline diagnosis only, no network, writes nothing.

Dumps the exact regions of build_feed.py, build_site.py and check_changes.py
needed to finish the Canon merge by hand-free patching.
Run:  python canon_merge_peek.py > peek_canon_merge.txt
Then paste peek_canon_merge.txt back into chat.
"""
from pathlib import Path
import re

NL = chr(10)

TARGETS = {
    "build_feed.py": [
        r"json", r"read_text", r"loads", r"\.json", r"feed", r"extend",
        r"append", r"makes?\b", r"red", r"sony", r"arri", r"smallhd", r"print",
    ],
    "build_site.py": [
        r"EXPECTED_MAKES", r"[Dd]ownload", r"download_url", r"download_opens_page",
        r"Release Notes", r"Source", r"button", r"btn", r"href",
    ],
    "check_changes.py": [
        r"count", r"len\(", r"EXPECTED", r"vanish", r"refus", r"make",
        r"threshold", r"min", r"print", r"sys.exit",
    ],
}

CONTEXT = 3


def dump(name, patterns):
    p = Path(name)
    print("=" * 70)
    print("FILE:", name)
    print("=" * 70)
    if not p.exists():
        print("  !! not found in", Path.cwd())
        print()
        return
    lines = p.read_text(encoding="utf-8", errors="replace").split(NL)
    print("  total lines:", len(lines))
    print()
    rx = re.compile("|".join(patterns))
    keep = set()
    for i, line in enumerate(lines):
        if rx.search(line):
            for j in range(max(0, i - CONTEXT), min(len(lines), i + CONTEXT + 1)):
                keep.add(j)
    last = -1
    for i in sorted(keep):
        if last != -1 and i != last + 1:
            print("      ...")
        # 4-space left margin keeps chat from reflowing the indentation
        print("    %4d| %s" % (i + 1, lines[i]))
        last = i
    print()


def full(name, limit=200):
    p = Path(name)
    print("=" * 70)
    print("FULL FILE (short enough to show whole):", name)
    print("=" * 70)
    if not p.exists():
        print("  !! not found")
        print()
        return
    lines = p.read_text(encoding="utf-8", errors="replace").split(NL)
    if len(lines) > limit:
        print("  %d lines, too long for a full dump, see excerpt above" % len(lines))
        print()
        return
    for i, line in enumerate(lines):
        print("    %4d| %s" % (i + 1, line))
    print()


def main():
    print("cwd:", Path.cwd())
    print("python files present:")
    for f in sorted(Path(".").glob("*.py")):
        print("   ", f.name, f.stat().st_size, "bytes")
    print("json files present:")
    for f in sorted(Path(".").glob("*.json")):
        print("   ", f.name, f.stat().st_size, "bytes")
    print()

    for name, pats in TARGETS.items():
        dump(name, pats)

    # these two are usually small, a full dump saves a round trip
    full("build_feed.py")
    full("check_changes.py")


if __name__ == "__main__":
    main()
