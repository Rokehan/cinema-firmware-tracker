#!/usr/bin/env python3
"""
arri_kit_gaps.py  -  why do seven ARRI kit items have no download link?
Diagnosis only. Fetches only the pages in question, caches them, writes nothing.

arri_kit.py produced 33 items, all dated, 24 with a direct file. Seven show no
firmware_kind at all:

    Master Grips, CUB-1, cforce mini, cforce plus, OCU-1, LCUBE CUB-2, BHM-2

They have a version and a date, so the page exists and parses. Either their
download sits in a link shape kind_of() does not recognise, or ARRI genuinely
publishes no package for them, which happens when an update ships through
another device (a cforce motor updated over LBUS from the hand unit, for
instance) or through a Windows updater tool.

For each of the seven this prints:
  - every ci-dl-teaser row with its href, title and filetype
  - every canto.de, .zip, .pkg, .exe and resource/blob link on the page
  - any sentence mentioning how the update is applied, so a page that says
    "update via the Hi-5" can be recorded honestly rather than left blank

Run:  python arri_kit_gaps.py > peek_arri_gaps.txt
"""
from pathlib import Path
import html as htmlmod
import json
import re
import subprocess
import sys
import time

NL = chr(10)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = [
    "-H", "User-Agent: " + UA,
    "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "-H", "Accept-Language: en-US,en;q=0.9",
    "-H", "Accept-Encoding: gzip, deflate, br",
    "-H", "Connection: keep-alive",
    "-H", "Upgrade-Insecure-Requests: 1",
    "-H", "Sec-Fetch-Dest: document",
    "-H", "Sec-Fetch-Mode: navigate",
    "-H", "Sec-Fetch-Site: none",
]

DELAY = 1.0

HOWTO = re.compile(
    r"(?i)[^.]*\b(?:update(?:d|s)? (?:via|through|using|with|from)|"
    r"can only be updated|is updated by|via LBUS|via the|"
    r"using the|updater|update tool|connect(?:ed)? to|"
    r"no separate|not available for download|please contact)\b[^.]*\.")


def sh(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, b"", b"timeout"


def curl(url, timeout=50):
    cmd = ["curl", "-s", "-L", "--compressed", "--max-time", str(timeout),
           "-w", "%{http_code}"] + HEADERS + [url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout + 10)
        body = r.stdout
        if len(body) >= 3:
            code, body = body[-3:], body[:-3]
            return body, (code == "200" and len(body) > 2000)
        return "", False
    except Exception:
        return "", False


def squash(t):
    return " ".join(str(t).split())


def strip_tags(t):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", str(t))
    t = re.sub(r"(?i)</(p|div|li|h[1-6])>", NL, t)
    t = re.sub(r"<[^>]+>", " ", t)
    lines = [squash(x) for x in htmlmod.unescape(t).split(NL)]
    return NL.join(x for x in lines if x)


def get(url, dest):
    p = Path(dest)
    if p.exists() and p.stat().st_size > 4000:
        return p.read_text(encoding="utf-8", errors="replace"), "cached"
    body, ok = curl(url)
    if not ok:
        return "", "fetch failed"
    p.write_text(body, encoding="utf-8")
    time.sleep(DELAY)
    return body, "fetched " + str(len(body))


def main():
    src = Path("arri_kit.json")
    if not src.exists():
        sys.exit("arri_kit.json not found. Run arri_kit.py first.")
    rows = json.loads(src.read_text(encoding="utf-8"))
    gaps = [r for r in rows if not r.get("firmware_kind")]

    print("items with no download: " + str(len(gaps)) + " of " + str(len(rows)))
    print()
    for r in gaps:
        print("=" * 70)
        print(r.get("product") + "   " + str(r.get("version")))
        print(r.get("source_url"))
        print("=" * 70)
        page, how = get(r["source_url"],
                        "peekgap_" + re.sub(r"\W+", "_", r.get("slug") or "x") + ".html")
        print("  " + how)
        if not page:
            print()
            continue

        parts = page.split('class="ci-dl-teaser"')
        print("  ci-dl-teaser rows: " + str(len(parts) - 1))
        for part in parts[1:]:
            hm = re.search(r'href=["\']([^"\']+)["\']', part)
            tm = re.search(r'ci-dl-teaser-title["\'][^>]*>\s*<span>(.*?)</span>',
                           part, re.S)
            fm = re.search(r'ci-dl-teaser-footer-filetype["\']?[^>]*>(.*?)</span>',
                           part, re.S)
            print("    href: " + (htmlmod.unescape(hm.group(1))[:104] if hm else "-"))
            print("      title: " + (squash(strip_tags(tm.group(1)))[:70] if tm else "-")
                  + "   type: " + (squash(strip_tags(fm.group(1)))[:24] if fm else "-"))
        print()

        print("  download-ish links anywhere on the page:")
        n = 0
        for m in re.finditer(r'href=["\']([^"\']+)["\']', page):
            u = htmlmod.unescape(m.group(1))
            if not re.search(r"canto\.de|\.zip|\.pkg|\.exe|\.dmg|resource/blob|"
                             r"\.tar\.gz|\.bin|\.fir", u, re.I):
                continue
            n += 1
            if n <= 10:
                print("    " + u[:112])
        print("    total: " + str(n))
        print()

        text = strip_tags(page)
        print("  sentences about how the update is applied:")
        said = []
        for m in HOWTO.finditer(text):
            s = squash(m.group(0))
            if len(s) > 24 and s not in said:
                said.append(s)
        for s in said[:6]:
            print("    " + s[:190])
        if not said:
            print("    none found")
        print()
    print("=" * 70)
    print("Nothing was modified. Cached as peekgap_*.html")


if __name__ == "__main__":
    main()
