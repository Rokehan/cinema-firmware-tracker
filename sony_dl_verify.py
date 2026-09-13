#!/usr/bin/env python3
"""
sony_dl_verify.py  -  what do Sony's Download links actually serve?
Diagnosis only. Patches nothing. One HEAD, and a small ranged GET, per row.

The symptom: the Download button for the FX bodies (except FX9) and the alpha
bodies opens a page of CSS, starting
    #software_details-container .article-details-inner-content em {
That is a stylesheet from Sony's article-details template, not firmware. Sony
serves everything through Salesforce FileDownload URLs that all look alike, so
whatever resolves those links is picking an asset off the page rather than the
firmware file.

For every Sony row in feed.json this reports:
  - the URL the site currently offers
  - HTTP status, content-type, content-length, content-disposition
  - the first bytes of the body, so a stylesheet or an HTML page is obvious
  - a verdict: firmware file, stylesheet, html page, or unreachable

It also groups by URL, because if many bodies share one URL that is itself the
bug, and prints which source field the URL came from so the fix can be aimed at
the right scraper.

Run:  python sony_dl_verify.py > peek_sony_dl.txt
      python sony_dl_verify.py --all       every make, not just Sony
      python sony_dl_verify.py --delay 1   seconds between requests
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import time

NL = chr(10)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

FULL = [
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

ALL = "--all" in sys.argv
DELAY = 1
if "--delay" in sys.argv:
    i = sys.argv.index("--delay")
    if i + 1 < len(sys.argv):
        try:
            DELAY = int(sys.argv[i + 1])
        except ValueError:
            pass


def sh(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, b"", b"timeout"


def squash(t):
    return " ".join(str(t).split())


def head(url):
    code, out, err = sh(["curl", "-sIL", "--max-time", "40"] + FULL + [url])
    info = {"status": "", "type": "", "length": "", "disp": "", "final": url}
    if code != 0:
        info["status"] = "curl rc=" + str(code)
        return info
    for line in out.decode("utf-8", errors="replace").split(NL):
        low = line.lower()
        if low.startswith("http/"):
            info["status"] = line.strip()
        elif low.startswith("content-type:"):
            info["type"] = line.split(":", 1)[1].strip()
        elif low.startswith("content-length:"):
            info["length"] = line.split(":", 1)[1].strip()
        elif low.startswith("content-disposition:"):
            info["disp"] = line.split(":", 1)[1].strip()
        elif low.startswith("location:"):
            info["final"] = line.split(":", 1)[1].strip()
    return info


def peek_body(url, nbytes=600):
    """First bytes only: enough to identify the content, cheap on bandwidth."""
    code, out, err = sh(["curl", "-sL", "--max-time", "40",
                         "-r", "0-" + str(nbytes)] + FULL + [url])
    if code != 0:
        return ""
    return out.decode("utf-8", errors="replace")


def verdict(info, body):
    t = (info.get("type") or "").lower()
    b = body.lstrip()[:400]
    low = b.lower()
    if "css" in t or b.startswith(("#", ".", "@media", "/*")) \
            or "article-details-inner-content" in b:
        return "STYLESHEET, not firmware"
    if "javascript" in t or low.startswith(("function", "var ", "(function")):
        return "JAVASCRIPT, not firmware"
    if "html" in t or low.startswith(("<!doctype", "<html")):
        return "HTML page"
    if "json" in t or low.startswith(("{", "[")):
        return "JSON"
    if any(k in t for k in ("octet-stream", "zip", "download", "binary",
                            "x-msdownload", "dat")):
        size = info.get("length")
        if size and size.isdigit() and int(size) > 100000:
            return "FIRMWARE FILE, " + str(round(int(size) / 1048576.0, 1)) + " MB"
        return "binary, but small (" + str(size or "?") + " bytes)"
    if not info.get("status", "").endswith("200"):
        return "unreachable: " + (info.get("status") or "?")
    return "unclear, type " + (t or "none")


def main():
    p = Path("feed.json")
    if not p.exists():
        sys.exit("feed.json not found")
    rows = json.loads(p.read_text(encoding="utf-8"))
    if not ALL:
        rows = [r for r in rows if (r.get("manufacturer") or "") == "Sony"]
    rows = [r for r in rows if r.get("firmware_url")]

    print("rows to check: " + str(len(rows)))
    print("delay: " + str(DELAY) + "s")
    print()

    byurl = {}
    for r in rows:
        byurl.setdefault(r["firmware_url"], []).append(r)

    print("=" * 70)
    print("distinct download urls: " + str(len(byurl)))
    print("=" * 70)
    for u, rs in sorted(byurl.items(), key=lambda kv: -len(kv[1])):
        if len(rs) > 1:
            print("  shared by " + str(len(rs)) + " items: "
                  + ", ".join(str(x.get("product")) for x in rs)[:90])
            print("    " + u[:120])
    print()

    results = []
    checked = {}
    for r in rows:
        url = r["firmware_url"]
        product = str(r.get("product"))
        kind = r.get("firmware_kind")
        if url in checked:
            info, body = checked[url]
            note = " (same url as an earlier row)"
        else:
            info = head(url)
            body = peek_body(url) if info.get("status", "").endswith(("200", "206")) else ""
            checked[url] = (info, body)
            note = ""
            time.sleep(DELAY)
        v = verdict(info, body)
        print("-" * 70)
        print("  " + product + "   v" + str(r.get("version"))
              + "   kind=" + str(kind) + note)
        print("    url:    " + url[:112])
        print("    status: " + (info.get("status") or "?")
              + "   type: " + (info.get("type") or "?")
              + "   len: " + (info.get("length") or "?"))
        if info.get("disp"):
            print("    disp:   " + info["disp"][:90])
        if body:
            print("    body:   " + squash(body)[:150])
        print("    VERDICT: " + v)
        results.append((product, kind, url, v))

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    groups = {}
    for product, kind, url, v in results:
        key = v.split(",")[0]
        groups.setdefault(key, []).append(product)
    for k in sorted(groups):
        print("  %-28s %d: %s" % (k, len(groups[k]),
                                  ", ".join(groups[k])[:80]))
    print()
    bad = [r for r in results if "not firmware" in r[3] or "HTML" in r[3]
           or "unreachable" in r[3]]
    print("  rows whose Download button does not deliver firmware: "
          + str(len(bad)) + "/" + str(len(results)))
    for product, kind, url, v in bad:
        print("    %-28s %s" % (product[:28], v))
    print()
    print("Nothing was modified.")


if __name__ == "__main__":
    main()
