#!/usr/bin/env python3
"""
sg_sample.py  -  validate the Canon SG crawl plan on a few pages before
committing two hours to it. Read-only, polite, caches everything.

The plan under test
-------------------
Canon SG's model pages load their download list with JavaScript, and the
endpoints that serve it (/support/get-search-result-content,
/support/download?) are Disallowed in sg.canon/robots.txt. The issue pages
themselves are NOT disallowed, and neither are the sitemaps.

So instead of calling a disallowed API we enumerate what SG publishes:
sitemap-sims-contents/1..6.xml list 25,807 /support/<10-digit> pages, of which
258 begin 0401, the prefix our known C50 firmware page uses. Fetch those 258
once, read model and version off each page, and keep the resulting
model+version -> issue map. Daily runs then only touch the handful of pages
that matter.

robots.txt also sets Crawl-delay: 30, so this waits 30 seconds between
requests. 258 pages is a bit over two hours, unattended, once.

What this script checks
-----------------------
  1. Can model and version be read reliably off an issue page? The C50 seed h1
     was "Canon Digital Cinema Camera EOS C50 Firmware Version 1.0.3.1 [Wi...".
  2. Do the install blocks (Caution / Preparations / Procedures) and the
     History section appear consistently?
  3. Is there a real file download, unlike Canon US? The seed named
     c50-v1031-win.zip, 142.11 MB.
  4. How many of the sampled pages are cinema firmware at all, which tells us
     the hit rate to expect across 258.

Run:  python sg_sample.py                 5 pages around the seed
      python sg_sample.py --n 12          more pages
      python sg_sample.py --delay 30      honour crawl-delay (default)
      python sg_sample.py --list          just show what it would fetch
"""
from pathlib import Path
import html as htmlmod
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

BASE = "https://sg.canon"
SEED_ISSUE = "0401135602"
ISSUES_FILE = "peeksm_issues.txt"

DELAY = 30
N = 5
LIST_ONLY = "--list" in sys.argv
for flag, cast in (("--n", int), ("--delay", int)):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            try:
                v = cast(sys.argv[i + 1])
                if flag == "--n":
                    N = v
                else:
                    DELAY = v
            except ValueError:
                pass

BLOCKS = ["Caution", "Cautions", "Preparation", "Preparations",
          "Required items", "Items required", "Procedure", "Procedures",
          "How to update", "History"]


def sh(args, timeout=80):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, b"", b"timeout"


def squash(t):
    return " ".join(str(t).split())


def strip_tags(t):
    return squash(re.sub(r"<[^>]+>", " ", str(t)))


def fetch(issue):
    """One issue page. Cached, so a re-run costs nothing."""
    p = Path("sgpage_" + issue + ".html")
    if p.exists() and p.stat().st_size > 1000:
        return p.read_text(encoding="utf-8", errors="replace"), True, "cached"
    url = BASE + "/en/support/" + issue
    code, out, err = sh(["curl", "-sL", "--compressed", "--max-time", "60",
                         "-w", "%{http_code}"] + FULL + [url])
    if code != 0 or len(out) < 4:
        return "", False, "curl rc=" + str(code)
    body = out.decode("utf-8", errors="replace")
    status, body = body[-3:], body[:-3]
    if status != "200" or len(body) < 2000:
        return "", False, "http " + status + " size " + str(len(body))
    p.write_text(body, encoding="utf-8")
    return body, True, "fetched " + str(len(body))


def candidates():
    """Issues to sample: the seed first, then its nearest numeric neighbours.

    Neighbours come from the sitemap list, never invented, so every URL here
    is one SG publishes.
    """
    p = Path(ISSUES_FILE)
    if not p.exists():
        print("!! " + ISSUES_FILE + " not found. Run peek_sitemap.py --all first.")
        return []
    nums = []
    for line in p.read_text(encoding="utf-8").split(NL):
        m = re.match(r"(\d{10})", line.strip())
        if m:
            nums.append(m.group(1))
    bucket = sorted(set(n for n in nums if n.startswith("0401")))
    if SEED_ISSUE not in bucket:
        print("!! the seed is not in the 0401 bucket, check the list")
    seed_at = bucket.index(SEED_ISSUE) if SEED_ISSUE in bucket else 0
    order = [SEED_ISSUE] if SEED_ISSUE in bucket else []
    step = 1
    while len(order) < N and step < len(bucket):
        for j in (seed_at - step, seed_at + step):
            if 0 <= j < len(bucket) and bucket[j] not in order:
                order.append(bucket[j])
                if len(order) >= N:
                    break
        step += 1
    return order, len(bucket)


def analyse(issue, page):
    text = strip_tags(page)

    h1 = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    if m:
        h1 = strip_tags(m.group(1))

    model = ""
    mm = re.search(r"(EOS\s+C\d{2,3}(?:\s+Mark\s+[IVX]+)?(?:\s+(?:PL|EF|FF|GS PL))?)",
                   h1 or text)
    if mm:
        model = squash(mm.group(1))

    version = ""
    vm = re.search(r"Firmware\s+Version\s+(\d+(?:\.\d+){1,3})", h1 or text, re.I)
    if vm:
        version = vm.group(1)

    present = [b for b in BLOCKS
               if re.search(r"\b" + re.escape(b) + r"\b", text, re.I)]

    hist = []
    hm = re.search(r"\bHistory\b", text, re.I)
    if hm:
        for v in re.finditer(r"(\d+\.\d+\.\d+\.\d+)",
                             text[hm.start():hm.start() + 2500]):
            if v.group(1) not in hist:
                hist.append(v.group(1))

    fname = ""
    fm = re.search(r"File name\s*:?\s*([A-Za-z0-9._\-]+)", text)
    if fm:
        fname = fm.group(1)
    fsize = ""
    sm = re.search(r"File size\s*:?\s*([\d.]+\s*[KMG]B)", text)
    if sm:
        fsize = squash(sm.group(1))

    dl = ""
    for m2 in re.finditer(r'href="([^"]*(?:download|c-wss|\.zip|\.exe|\.dmg)[^"]*)"',
                          page, re.I):
        u = htmlmod.unescape(m2.group(1))
        if "search" in u.lower():
            continue
        dl = u if u.startswith("http") else BASE + u
        break

    kind = "cinema firmware" if (model and version) else (
        "firmware, other product" if version else "not firmware")

    print("  issue " + issue + "   [" + kind + "]")
    print("    h1:       " + (h1[:96] or "(none)"))
    print("    model:    " + (model or "-") + "    version: " + (version or "-"))
    print("    blocks:   " + (", ".join(present) or "none"))
    print("    history:  " + (", ".join(hist[:8]) or "none"))
    print("    file:     " + (fname or "-") + "   " + (fsize or ""))
    print("    download: " + (dl[:104] or "-"))
    return {"issue": issue, "model": model, "version": version,
            "blocks": present, "history": hist, "file": fname, "dl": dl,
            "kind": kind}


def main():
    print("Canon SG sample")
    print("crawl-delay honoured: " + str(DELAY) + "s between requests")
    print()
    got = candidates()
    if not got:
        return
    order, bucket_size = got
    print("0401 bucket size: " + str(bucket_size)
          + "   (a full pass would take about "
          + str(round(bucket_size * DELAY / 3600.0, 1)) + " hours)")
    print("sampling " + str(len(order)) + ": " + ", ".join(order))
    print()
    if LIST_ONLY:
        print("--list given, nothing fetched.")
        return

    out = []
    for n, issue in enumerate(order):
        page, ok, how = fetch(issue)
        if not ok:
            print("  issue " + issue + "   " + how)
            print()
        else:
            print("  (" + how + ")")
            out.append(analyse(issue, page))
            print()
        if n + 1 < len(order) and "cached" not in how:
            time.sleep(DELAY)

    print("=" * 62)
    cine = [r for r in out if r["kind"] == "cinema firmware"]
    print("pages read: " + str(len(out)))
    print("cinema firmware pages: " + str(len(cine)) + "/" + str(len(out)))
    if out:
        rate = len(cine) / float(len(out))
        print("at that rate, %d of the %d in the bucket would be cinema"
              % (round(rate * bucket_size), bucket_size))
    withblocks = [r for r in cine if r["blocks"]]
    withhist = [r for r in cine if r["history"]]
    withfile = [r for r in cine if r["file"]]
    print("cinema pages with install blocks: %d/%d" % (len(withblocks), len(cine)))
    print("cinema pages with a History list: %d/%d" % (len(withhist), len(cine)))
    print("cinema pages naming a real file:  %d/%d" % (len(withfile), len(cine)))
    print()
    if cine:
        print("model + version -> issue, the map we would build:")
        for r in cine:
            print("  %-22s %-10s %s" % (r["model"], r["version"], r["issue"]))
    print()
    print("Nothing was modified. Pages cached as sgpage_<issue>.html")


if __name__ == "__main__":
    main()
