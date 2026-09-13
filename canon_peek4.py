#!/usr/bin/env python3
"""canon_peek4.py  --  Find Canon's firmware XML feed.

peek3 proved the download table on /support/p/<slug> is built client-side,
and leaked the shape of Canon's data store:

  /content/dam/nw3s/driver-downloads/data/cusa/en/<fileid>EN.xml
      -> { version, linkDownload (pdisp01.c-wss.com), filename }

This script, run offline against the saved C400 page, hunts for:
  1. window.productInfo  (the product/SKU the page asks about)
  2. every driver-downloads XML path present
  3. any /bin/canon or servlet endpoint the page calls
  4. the 11 c-wss URLs that sit OUTSIDE <script>
  5. how the loadFirmware event gets its data

Then it goes live: fetches any XML path it found, plus a few guessed
endpoints, and dumps what comes back. If the XML carries version, date,
changelog and install steps, that single file is the uniform path for
every camera.
"""

import base64, re, subprocess, sys
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
BASE = "https://www.usa.canon.com"


def curl(url, timeout=40, referer=None):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout), "--compressed",
           "-w", "%{http_code}",
           "-H", "User-Agent: " + UA,
           "-H", "Accept: application/xml,text/xml,application/json,text/html,*/*;q=0.8",
           "-H", "Accept-Language: en-US,en;q=0.9",
           "-H", "X-Requested-With: XMLHttpRequest"]
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


# ── load the saved page ────────────────────────────────────────────
CAND = ["debug_support_eos-c400.html", "peek2_eos-c400.txt",
        "debug_support_eos-c50.html", "peek2_eos-c50.txt"]
path = next((Path(c) for c in CAND if Path(c).exists()), None)
if path is None:
    print("ERROR: no saved support page found. Run:")
    print("  python canon_cameras.py --debug --only c400")
    sys.exit(1)

html = path.read_text(errors="replace")
print("File: " + str(path) + "  (" + str(len(html)) + " bytes)")
print()

# ── 1. product identity ────────────────────────────────────────────
print("=" * 72)
print("1. PRODUCT IDENTITY")
print("=" * 72)
for pat in [r"window\.productInfo\s*=\s*(\{.{0,1200}?\});",
            r"productInfo\s*=\s*(\{.{0,1200}?\})",
            r"\"productId\"\s*:\s*\"([^\"]+)\"",
            r"'productId'\s*:\s*'([^']+)'",
            r"productId\s*[:=]\s*[\"']([^\"']+)[\"']",
            r"materialCode\s*[:=]\s*[\"']([^\"']+)[\"']",
            r"modelCode\s*[:=]\s*[\"']([^\"']+)[\"']",
            r"data-product-id=[\"']([^\"']+)[\"']"]:
    for m in list(re.finditer(pat, html, re.I | re.S))[:3]:
        seg = re.sub(r"\s+", " ", m.group(0))
        print("  " + seg[:300])
print()

# ── 2. XML data paths ──────────────────────────────────────────────
print("=" * 72)
print("2. DRIVER-DOWNLOAD XML PATHS")
print("=" * 72)
xmls = sorted(set(re.findall(r"[/\w.-]*driver-downloads/data/[\w/.-]+\.xml", html)))
print("  found " + str(len(xmls)))
for x in xmls[:25]:
    print("    " + x)
print()

# ── 3. endpoints the page might call ───────────────────────────────
print("=" * 72)
print("3. CANDIDATE ENDPOINTS")
print("=" * 72)
eps = set()
for pat in [r"[\"'](/bin/canon/[^\"'\s]+)[\"']",
            r"[\"'](/content/[\w/.-]*(?:driver|download|firmware)[\w/.-]*)[\"']",
            r"[\"']([^\"'\s]*\.model\.json)[\"']",
            r"fetch\(\s*[\"']([^\"']+)[\"']",
            r"\$\.(?:get|ajax|getJSON)\(\s*[\"']([^\"']+)[\"']",
            r"url\s*:\s*[\"']([^\"']+)[\"']",
            r"[\"'](/[\w/.-]*servlet[\w/.-]*)[\"']",
            r"[\"'](/apps/[\w/.-]+)[\"']"]:
    for m in re.finditer(pat, html, re.I):
        u = m.group(1)
        if len(u) > 4 and not u.startswith("data:"):
            eps.add(u)
print("  found " + str(len(eps)))
for e in sorted(eps)[:40]:
    print("    " + e[:150])
print()

# ── 4. c-wss URLs outside <script> ─────────────────────────────────
print("=" * 72)
print("4. c-wss URLs OUTSIDE <script>  (peek3 counted 11)")
print("=" * 72)
spans = [(m.start(), m.end()) for m in re.finditer(r"<script\b.*?</script>", html, re.S | re.I)]
def in_script(p):
    return any(s <= p < e for s, e in spans)
outside = [m for m in re.finditer(r"https?://[^\s\"'<>\\)]*c-wss\.com[^\s\"'<>\\)]*", html)
           if not in_script(m.start())]
print("  " + str(len(outside)) + " outside")
for m in outside[:8]:
    print()
    print("    URL: " + m.group(0)[:140])
    seg = re.sub(r"[ \t]+", " ", html[max(0, m.start() - 500): m.end() + 250])
    seg = re.sub(r"\n\s*\n+", "\n", seg)
    print("    context: " + seg[-600:].replace(chr(10), " | "))
print()

# ── 5. loadFirmware wiring ─────────────────────────────────────────
print("=" * 72)
print("5. loadFirmware / firmwareFiles WIRING")
print("=" * 72)
for kw in ["loadFirmware", "firmwareFiles", "software-downloads", "driverDownload"]:
    i = html.find(kw)
    if i == -1:
        continue
    print()
    print("  --- around '" + kw + "' ---")
    seg = re.sub(r"[ \t]+", " ", html[max(0, i - 900): i + 900])
    seg = re.sub(r"\n\s*\n+", "\n", seg)
    print(seg)

# ── LIVE probes ────────────────────────────────────────────────────
print()
print("=" * 72)
print("LIVE PROBES")
print("=" * 72)

referer = BASE + "/support/p/eos-c400?subtab=downloads-firmware"
tried = []

# any XML path we actually found
for x in xmls[:3]:
    u = x if x.startswith("http") else BASE + ("" if x.startswith("/") else "/") + x
    tried.append(("found_xml", u))

# the printer XML from peek3, to learn the schema
tried.append(("schema_sample",
              BASE + "/content/dam/nw3s/driver-downloads/data/cusa/en/0401139602EN.xml"))

for label, u in tried:
    print()
    print("-" * 72)
    print(label + ": " + u)
    body, code = curl(u, referer=referer)
    print("  HTTP " + str(code) + "  " + str(len(body)) + " bytes")
    if len(body) < 40:
        continue
    Path("peek4_" + label + ".txt").write_text(body)
    print("  saved: peek4_" + label + ".txt")
    print("  --- first 2500 chars ---")
    print(body[:2500])
    dl = sorted(set(re.findall(r"https?://[^\s\"'<>]*c-wss\.com[^\s\"'<>]*", body)))
    if dl:
        print()
        print("  download URLs inside: " + str(len(dl)))
        for d in dl[:5]:
            print("    " + d[:150])
            mid = re.search(r"[?&]id=([A-Za-z0-9+/=]+)", d)
            if mid:
                try:
                    print("        id -> " + base64.b64decode(mid.group(1)).decode(errors="replace"))
                except Exception:
                    pass
    for kw in ["Caution", "Preparations", "incorporates", "<version", "<date", "<filename"]:
        if kw.lower() in body.lower():
            print("  contains: " + kw)

print()
print("=" * 72)
print("Done. Paste the output back.")
