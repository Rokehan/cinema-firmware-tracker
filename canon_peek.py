#!/usr/bin/env python3
"""canon_peek.py  --  Diagnostic. Inspect Canon notice page structure.

Reads debug_advisories.json (written by canon_cameras.py --debug),
picks representative notice pages, and dumps:
  - every <a> href with its link text
  - the text window around the word "Download"
  - the text window around "incorporates" / "Caution"
  - raw HTML to peek_<label>.html

Throwaway script. Delete once the download/changelog selectors are fixed.
"""

import json, re, subprocess, sys
from pathlib import Path
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")


def curl_get(url, timeout=35):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout), "--compressed",
           "-H", "User-Agent: " + UA,
           "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "-H", "Accept-Language: en-US,en;q=0.9",
           "-H", "Sec-Fetch-Dest: document",
           "-H", "Sec-Fetch-Mode: navigate",
           url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 8)
    return r.stdout


# ── pick targets from the discovered advisories ────────────────────

adv_file = Path("debug_advisories.json")
if not adv_file.exists():
    print("ERROR: debug_advisories.json not found.")
    print("Run: python canon_cameras.py --debug")
    sys.exit(1)

advisories = json.loads(adv_file.read_text())
print("Loaded " + str(len(advisories)) + " advisories" + chr(10))

# One current camera, one changelog-missing camera, one known-good
WANT = [
    ("current_C400",   r"C400"),
    ("current_C50",    r"C50\b"),
    ("missing_C200",   r"C200"),
    ("missing_C300",   r"EOS\s*C300(?!\s*(?:Mark|PL))"),
    ("good_C500II",    r"C500\s*Mark\s*II"),
]

targets = []
for label, pat in WANT:
    rx = re.compile(pat, re.I)
    hit = None
    for a in advisories:
        if rx.search(a["title"]) or rx.search(a["url"].replace("-", " ")):
            hit = a
            break
    if hit:
        targets.append((label, hit))
        print(label + ": " + hit["url"])
    else:
        print(label + ": NO MATCH")

print(chr(10) + "=" * 70)

# ── inspect each ───────────────────────────────────────────────────

for label, adv in targets:
    print(chr(10) + "#" * 70)
    print("# " + label + "  v" + adv["version"])
    print("# " + adv["url"])
    print("#" * 70)

    html = curl_get(adv["url"])
    if len(html) < 500:
        print("  FETCH FAILED (" + str(len(html)) + " bytes)")
        continue

    Path("peek_" + label + ".html").write_text(html)
    print("  raw HTML: peek_" + label + ".html (" + str(len(html)) + " bytes)")

    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()

    # ── every link, with text ──
    print(chr(10) + "  --- ALL LINKS (non-nav) ---")
    shown = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)[:90]
        # skip obvious chrome
        if not text:
            continue
        if re.search(r"^(Home|Shop|Support|Sign In|Cart|Menu|Search|Learn|About|Privacy|Terms|Contact Us)$", text, re.I):
            continue
        if href.startswith("#") or href.startswith("javascript"):
            continue
        # highlight likely download links
        flag = ""
        if re.search(r"c-wss|WWUFORedirect|\.zip|\.fir|gdl/", href, re.I):
            flag = "  <== FILE?"
        if re.search(r"download", text, re.I):
            flag = flag + "  <== TEXT SAYS DOWNLOAD"
        if flag or shown < 25:
            print("    [" + text + "] -> " + href[:120] + flag)
            shown += 1

    # ── text windows ──
    flat = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    for kw in ["Download Firmware", "incorporates", "Caution", "Preparations for"]:
        i = flat.lower().find(kw.lower())
        print(chr(10) + "  --- around '" + kw + "' ---")
        if i == -1:
            print("    NOT FOUND")
        else:
            print("    ..." + flat[max(0, i - 120): i + 500] + "...")

print(chr(10) + "=" * 70)
print("Done. Paste the output back.")
