#!/usr/bin/env python3
"""canon_peek3.py  --  Where do Canon's download links actually live?

Offline. Reads debug_support_eos-c400.html (written by the --debug run),
so no network calls.

Answers: is each pdisp01.c-wss.com URL inside a <script> block, an <a href>,
or somewhere else? And what does the surrounding markup look like, so the
version, date and file name can be paired to the right link.

Throwaway diagnostic.
"""

import re, sys
from pathlib import Path

CAND = ["debug_support_eos-c400.html", "debug_support_eos-c50.html",
        "peek2_eos-c400.txt", "peek2_eos-c50.txt"]

path = None
for c in CAND:
    if Path(c).exists():
        path = Path(c)
        break
if path is None:
    print("ERROR: no debug file found. Looked for:")
    for c in CAND:
        print("  " + c)
    print()
    print("Run: python canon_cameras.py --debug --only c400")
    sys.exit(1)

html = path.read_text(errors="replace")
print("File: " + str(path) + "   " + str(len(html)) + " bytes")
print()

# ── map every <script> span so we can test containment ─────────────
spans = [(m.start(), m.end()) for m in re.finditer(r"<script\b.*?</script>", html, re.S | re.I)]
print("script blocks: " + str(len(spans)))

def in_script(pos):
    for s, e in spans:
        if s <= pos < e:
            return True
    return False

# ── every c-wss occurrence, classified ─────────────────────────────
hits = list(re.finditer(r"https?://[^\s\"'<>\\)]*c-wss\.com[^\s\"'<>\\)]*", html))
print("c-wss URLs: " + str(len(hits)))

inside = sum(1 for m in hits if in_script(m.start()))
outside = len(hits) - inside
print("  inside <script>: " + str(inside))
print("  outside:         " + str(outside))

with_id = [m for m in hits if "id=" in m.group(0)]
print("  carrying an id=: " + str(len(with_id)))
print()

# ── are they in anchors? ───────────────────────────────────────────
anchors = re.findall(r"<a\b[^>]*href=[\"']([^\"']*c-wss[^\"']*)[\"'][^>]*>", html, re.I)
print("<a href> pointing at c-wss: " + str(len(anchors)))
if anchors:
    for a in anchors[:5]:
        print("    " + a[:130])
print()

# ── raw context around firmware-looking links ──────────────────────
print("=" * 72)
print("RAW CONTEXT around c-wss links that look like camera firmware")
print("=" * 72)

shown = 0
for m in with_id:
    start, end = m.start(), m.end()
    window = html[max(0, start - 2500): end + 600]
    # only interested in blocks that mention a firmware version
    if not re.search(r"Firmware\s+Version\s+\d", window, re.I):
        continue
    # skip software/plugin rows
    if re.search(r"XF Utility|Cinema RAW Development|Plugin|EOS VR|Activator|"
                 r"Picture Style|Upscaling|Remote Camera", window, re.I):
        continue

    shown += 1
    print()
    print("-" * 72)
    print("MATCH " + str(shown) + "   in_script=" + str(in_script(start)))
    print("URL: " + m.group(0)[:150])
    print("-" * 72)

    # collapse whitespace but KEEP tags so the structure is visible
    seg = re.sub(r"[ \t]+", " ", window)
    seg = re.sub(r"\n\s*\n+", "\n", seg)
    print(seg[-2200:])

    if shown >= 3:
        break

if not shown:
    print()
    print("No firmware-looking context found. Showing the first id= link raw:")
    if with_id:
        m = with_id[0]
        seg = re.sub(r"[ \t]+", " ", html[max(0, m.start() - 2000): m.end() + 500])
        print(seg)

# ── how are versions and dates marked up? ──────────────────────────
print()
print("=" * 72)
print("VERSION / DATE MARKUP SAMPLES")
print("=" * 72)
for m in list(re.finditer(r"Firmware\s+Version\s+\d[\d.]*", html, re.I))[:4]:
    seg = re.sub(r"[ \t]+", " ", html[max(0, m.start() - 700): m.start() + 900])
    seg = re.sub(r"\n\s*\n+", "\n", seg)
    print()
    print("-" * 72)
    print(seg)

print()
print("=" * 72)
print("Done. Paste the output back.")
