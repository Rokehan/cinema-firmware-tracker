#!/usr/bin/env python3
"""canon_peek5.py  --  Extract Canon's embedded firmware JSON.

peek4 found the payload: the support page carries an HTML attribute holding
a JSON array of download objects, HTML-escaped (&#34;) with JS unicode
escapes (\\u003d for =, \\u0026 for &). Observed fields:

    fileDescr, recommended, language, postDate, fileType,
    fileSize, fileUrl (pdisp01.c-wss.com), renditionUrl

fileType distinguishes Firmware from Software and manuals, which is the
filter the old HTML scraper was missing.

This script (offline) unescapes and parses that JSON out of the saved page
and prints every field of every Firmware entry. Then it goes live and
fetches a renditionUrl (.xml.html) to see whether that carries the
changelog and install steps.

Throwaway diagnostic.
"""

import html as htmllib
import json, re, subprocess, sys
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
BASE = "https://www.usa.canon.com"


def curl(url, timeout=40, referer=None):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout), "--compressed",
           "-w", "%{http_code}",
           "-H", "User-Agent: " + UA,
           "-H", "Accept: text/html,application/xml,*/*;q=0.8",
           "-H", "Accept-Language: en-US,en;q=0.9"]
    if referer:
        cmd += ["-H", "Referer: " + referer]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        b = r.stdout
        if len(b) >= 3:
            return b[:-3], b[-3:]
        return "", "000"
    except Exception:
        return "", "ERR"


def unescape_payload(s):
    """HTML entities then JS unicode escapes."""
    s = htmllib.unescape(s)
    s = s.replace("\\u003d", "=").replace("\\u0026", "&")
    s = s.replace("\\u003c", "<").replace("\\u003e", ">")
    s = s.replace("\\u002f", "/")
    return s


# ── load saved page ────────────────────────────────────────────────
CAND = ["debug_support_eos-c400.html", "peek2_eos-c400.txt",
        "debug_support_eos-c50.html", "peek2_eos-c50.txt",
        "peek2_eos-c70.txt"]
path = next((Path(c) for c in CAND if Path(c).exists()), None)
if path is None:
    print("ERROR: no saved support page. Run:")
    print("  python canon_cameras.py --debug --only c400")
    sys.exit(1)

raw = path.read_text(errors="replace")
print("File: " + str(path) + "  (" + str(len(raw)) + " bytes)")
print()

# ── 1. locate the attribute holding the JSON array ─────────────────
print("=" * 72)
print("1. LOCATING THE EMBEDDED JSON")
print("=" * 72)

# Walk back from each fileType marker to the opening [ of the array,
# then forward to its matching ] . Works on the escaped text directly.
starts = set()
for m in re.finditer(r"(?:&#34;|\")fileType(?:&#34;|\")", raw):
    seg = raw[max(0, m.start() - 6000): m.start()]
    k = seg.rfind("[{")
    if k != -1:
        starts.add(max(0, m.start() - 6000) + k)
print("  candidate array starts: " + str(len(starts)))

def grab_array(text, start):
    """Return the [...] slice beginning at start, brace-counted."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return None

parsed_sets = []
for s in sorted(starts):
    blob = grab_array(raw, s)
    if not blob or len(blob) < 80:
        continue
    cleaned = unescape_payload(blob)
    # attribute boundaries can leave a stray tail, trim to last ]
    k = cleaned.rfind("]")
    if k != -1:
        cleaned = cleaned[:k + 1]
    try:
        data = json.loads(cleaned)
    except Exception:
        # try repairing a truncated array by cutting at the last complete }
        k2 = cleaned.rfind("},")
        if k2 == -1:
            continue
        try:
            data = json.loads(cleaned[:k2 + 1] + "]")
        except Exception:
            continue
    if isinstance(data, list) and data and isinstance(data[0], dict):
        parsed_sets.append(data)

print("  arrays parsed: " + str(len(parsed_sets)))

# merge, dedup on fileUrl
allrows = []
seen = set()
for arr in parsed_sets:
    for row in arr:
        key = json.dumps(row, sort_keys=True)[:400]
        if key not in seen:
            seen.add(key)
            allrows.append(row)
print("  unique rows: " + str(len(allrows)))

if not allrows:
    print()
    print("  Extraction failed. Raw sample around first fileType:")
    m = re.search(r"(?:&#34;|\")fileType(?:&#34;|\")", raw)
    if m:
        print(raw[max(0, m.start() - 1500): m.start() + 800])
    sys.exit(1)

Path("peek5_rows.json").write_text(json.dumps(allrows, indent=2, ensure_ascii=False))
print("  saved: peek5_rows.json")

# ── 2. what keys exist, and what fileTypes ─────────────────────────
print()
print("=" * 72)
print("2. SCHEMA")
print("=" * 72)
keys = {}
for r in allrows:
    for k in r:
        keys[k] = keys.get(k, 0) + 1
print("  keys (count):")
for k, c in sorted(keys.items(), key=lambda kv: -kv[1]):
    print("    " + k.ljust(22) + str(c))

types = {}
for r in allrows:
    t = str(r.get("fileType", "?"))
    types[t] = types.get(t, 0) + 1
print()
print("  fileType values:")
for t, c in sorted(types.items(), key=lambda kv: -kv[1]):
    print("    " + t.ljust(22) + str(c))

# ── 3. the firmware rows in full ───────────────────────────────────
print()
print("=" * 72)
print("3. FIRMWARE ROWS (fileType == Firmware)")
print("=" * 72)
fw = [r for r in allrows if str(r.get("fileType", "")).strip().lower() == "firmware"]
print("  " + str(len(fw)) + " firmware rows")
for r in fw:
    print()
    for k in ["fileName", "fileDescr", "version", "os", "postDate",
              "fileSize", "language", "recommended", "fileUrl", "renditionUrl"]:
        if k in r:
            v = str(r[k])
            print("    " + k.ljust(14) + ": " + v[:150])

# ── 4. live: does the rendition carry changelog / install? ─────────
print()
print("=" * 72)
print("4. LIVE: renditionUrl content")
print("=" * 72)

rends = []
for r in fw + allrows:
    u = str(r.get("renditionUrl", "")).strip()
    if not u:
        continue
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = BASE + u
    if u.startswith("http") and u not in rends:
        rends.append(u)

print("  " + str(len(rends)) + " rendition URLs, probing up to 2")
referer = BASE + "/support/p/eos-c400?subtab=downloads-firmware"
for u in rends[:2]:
    print()
    print("-" * 72)
    print("  " + u)
    body, code = curl(u, referer=referer)
    print("  HTTP " + str(code) + "  " + str(len(body)) + " bytes")
    if len(body) < 60:
        continue
    Path("peek5_rendition.html").write_text(body)
    print("  saved: peek5_rendition.html")
    flat = re.sub(r"<[^>]+>", " ", body)
    flat = re.sub(r"\s+", " ", htmllib.unescape(flat)).strip()
    print("  --- text, first 2500 chars ---")
    print("  " + flat[:2500])
    print()
    for kw in ["Caution", "Preparations", "incorporates", "History",
               "following items are required", "Firmware Version"]:
        print("  contains " + kw.ljust(32) + str(kw.lower() in flat.lower()))

print()
print("=" * 72)
print("Done. Paste the output back.")
