#!/usr/bin/env python3
"""
sg_crawl.py  -  walk Canon SG's 0401 issue bucket and keep the Cinema EOS
firmware pages, with their install blocks and version history.

Why this way
------------
Canon US publishes no Caution / Preparations / Procedure block for 13 of the 22
Cinema EOS bodies. Canon SG does, in English, and adds a History section with
per-version changelogs. Its URLs are opaque issue numbers.

The model pages that would list those issues load them with JavaScript, and the
endpoints behind that are Disallowed in sg.canon/robots.txt
(/support/get-search-result-content, /support/download?). The issue pages and
the sitemaps are not disallowed. So we enumerate what SG publishes rather than
calling an API we are asked not to call.

sitemap-sims-contents/1..6.xml list 25,807 /support/<10-digit> pages. 258 of
them start 0401, the prefix of the known C50 firmware page. This walks those
258 at the 30 second Crawl-delay in robots.txt, roughly 2.2 hours, once.
Output is committed so daily runs never crawl.

Confirmed on a 5-page sample
----------------------------
  - Cinema pages say "Canon Digital Cinema Camera" in the h1, e.g.
    "Canon Digital Cinema Camera EOS C50 Firmware Version 1.0.3.1 [Windows]".
    Consumer bodies read "EOS R7 Firmware Update, Version 1.8.0", printers
    read "MF284dw Firmware Update Tool", so the phrase is an exact filter.
  - Windows and macOS are separate issues for the same firmware
    (0401135602 and 0401135702). Both are kept, keyed by platform.
  - Install blocks and History were present on both cinema pages sampled.
  - A file name and size are published; the download href itself is not in the
    HTML, so nothing is claimed about a direct file.

Resumable: every page is cached as sgpage_<issue>.html and progress is written
after each fetch, so an interrupted run continues where it stopped. Re-running
costs nothing for pages already on disk.

Output: sg_issues.json
Flags:
  --limit N     stop after N new fetches, for a short trial
  --delay S     seconds between requests, default 30 per robots.txt
  --prefix P    which bucket to walk, default 0401
  --offline     parse only what is already cached, no network
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

BASE = "https://sg.canon"
ISSUES_FILE = "peeksm_issues.txt"
OUT = Path("sg_issues.json")
STATE = Path("sg_crawl_state.json")

CINEMA_MARK = "Canon Digital Cinema Camera"

DELAY = 30
LIMIT = None
PREFIX = "0401"
OFFLINE = "--offline" in sys.argv
for flag in ("--limit", "--delay", "--prefix"):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            v = sys.argv[i + 1]
            if flag == "--prefix":
                PREFIX = v
            else:
                try:
                    if flag == "--limit":
                        LIMIT = int(v)
                    else:
                        DELAY = int(v)
                except ValueError:
                    pass

# Canon SG's own labels, verbatim from 6 cinema pages. Longest first so
# "Preparations for a firmware update" is not truncated to "Preparations".
# There is no "Procedures:" section: SG puts the step-by-step in a PDF inside
# the downloaded folder, and says so in the Preparations text.
HEADINGS = ["Preparations for a firmware update",
            "How to check the firmware version", "How to update",
            "Preparations", "Preparation", "Required items", "Items required",
            "Procedures", "Procedure", "Cautions", "Caution",
            "Notes", "Note", "History"]

# Boilerplate that follows the useful text on every page. Used as a stop
# boundary and never kept as an install block: it is licence text, not steps.
# Only licence sections, and only ever cut AFTER the install text begins:
# "Disclaimer" and "File information" also appear in the tab strip at the top
# of the page, so an unanchored cut would remove the whole body.
BOILERPLATE = ["Regarding the Software Included in this Firmware",
               "Software Developed by Canon and Free Software",
               "Obtaining Source Codes of Free Software"]


def sh(args, timeout=80):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, b"", b"timeout"


def squash(t):
    return " ".join(str(t).split())


def strip_tags(t):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", str(t))
    t = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", NL, t)
    t = re.sub(r"(?i)<br\s*/?>", NL, t)
    t = re.sub(r"<[^>]+>", " ", t)
    import html as h
    t = h.unescape(t)
    lines = [squash(x) for x in t.split(NL)]
    return NL.join(x for x in lines if x)


def issues_in_bucket():
    p = Path(ISSUES_FILE)
    if not p.exists():
        sys.exit(ISSUES_FILE + " not found. Run peek_sitemap.py --all first.")
    nums = []
    for line in p.read_text(encoding="utf-8").split(NL):
        m = re.match(r"(\d{10})", line.strip())
        if m and m.group(1).startswith(PREFIX):
            nums.append(m.group(1))
    return sorted(set(nums))


def page_path(issue):
    return Path("sgpage_" + issue + ".html")


def fetch(issue):
    p = page_path(issue)
    if p.exists() and p.stat().st_size > 1200:
        return p.read_text(encoding="utf-8", errors="replace"), "cached"
    if OFFLINE:
        return "", "not cached"
    url = BASE + "/en/support/" + issue
    code, out, err = sh(["curl", "-sL", "--compressed", "--max-time", "60",
                         "-w", "%{http_code}"] + FULL + [url])
    if code != 0 or len(out) < 4:
        return "", "curl rc=" + str(code)
    body = out.decode("utf-8", errors="replace")
    status, body = body[-3:], body[:-3]
    if status != "200" or len(body) < 2000:
        return "", "http " + status
    p.write_text(body, encoding="utf-8")
    return body, "fetched"


def h1_of(page):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    return squash(strip_tags(m.group(1))) if m else ""


def parse(issue, page):
    """A cinema firmware record, or None. Every field is Canon's own text."""
    h1 = h1_of(page)
    if CINEMA_MARK.lower() not in h1.lower():
        return None

    mm = re.search(r"(EOS\s+C\d{2,3}(?:\s+Mark\s+[IVX]+)?(?:\s+(?:GS\s+PL|PL|EF|FF))?)",
                   h1)
    model = squash(mm.group(1)) if mm else ""
    vm = re.search(r"Firmware\s+Version\s+(\d+(?:\.\d+){1,3})", h1, re.I)
    version = vm.group(1) if vm else ""
    pm = re.search(r"\[([^\]]+)\]\s*$", h1)
    platform = squash(pm.group(1)) if pm else ""
    if not model or not version:
        return None

    full = strip_tags(page)
    body = full

    # The licence sections sit BETWEEN Preparations and History on SG's pages,
    # so they cannot be a truncation point: they are split out as sections
    # below and skipped by name, which keeps History intact.

    # the text between the last "Detail" heading and the first Caution is the
    # current version's changelog, Canon's own wording
    changelog = []
    dm = None
    for dm in re.finditer(r"(?im)^Detail$", body):
        pass
    if dm:
        after = body[dm.end():]
        stop = re.search(r"(?im)^(?:Cautions?|Preparations?[^:]*)\s*:", after)
        head = after[:stop.start()] if stop else after
        for line in head.split(NL):
            line = squash(line)
            if not line or re.match(r"(?i)^(file information|disclaimer|"
                                    r"operating system|language\(s\)|"
                                    r"software information|english|"
                                    r"windows|mac ?os)", line):
                continue
            changelog.append(line)

    # split the detail text on Canon's own headings
    rx = re.compile("(" + "|".join(re.escape(h) for h in HEADINGS + BOILERPLATE)
                    + r")\s*:", re.I)
    skip = set(b.lower() for b in BOILERPLATE)
    marks = list(rx.finditer(body))
    blocks = []
    history_text = ""
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        head = squash(m.group(1))
        chunk = body[m.end():end]
        items = []
        for raw in chunk.split(NL):
            line = squash(raw).lstrip("-").strip()
            if line:
                items.append(line)
        if head.lower() in skip:
            continue
        if head.lower() == "history":
            # the File information block follows the detail text and is not
            # part of any version's changelog
            cut = re.split(r"(?i)\bFile (?:information|name)\b",
                           NL.join(items))[0]
            history_text = cut.rstrip()
            continue
        if items:
            blocks.append({"heading": head, "items": items})

    # History: one entry per version, changelog verbatim
    history = []
    if history_text:
        hm = list(re.finditer(r"Firmware\s+Version\s+(\d+(?:\.\d+){1,3})",
                              history_text, re.I))
        for i, m in enumerate(hm):
            end = hm[i + 1].start() if i + 1 < len(hm) else len(history_text)
            body2 = history_text[m.end():end]
            items = [squash(x) for x in body2.split(NL) if squash(x)]
            if items:
                history.append({"version": m.group(1), "changelog": items})

    fname = ""
    fm = re.search(r"File name\s*:?\s*([A-Za-z0-9._\-]+)", full)
    if fm:
        fname = fm.group(1)
    fsize = ""
    sm = re.search(r"File size\s*:?\s*([\d.]+\s*[KMGkmg]B)", full)
    if sm:
        fsize = squash(sm.group(1))
    langs = ""
    lm = re.search(r"File language\s*:?\s*([A-Za-z,]+(?:\s*,\s*[A-Za-z]+)*)", full)
    if lm:
        langs = squash(lm.group(1)).rstrip(",")[:60]

    return {
        "issue": issue,
        "url": BASE + "/en/support/" + issue,
        "model": model,
        "version": version,
        "platform": platform,
        "title": h1,
        "changelog": changelog,
        "install": blocks,
        # SG can lag Canon US: it documented C500 Mark II 1.1.3.1 while US had
        # 1.1.5.1. The steps are still Canon's, so name the version they cover.
        "install_version": version,
        "install_source": BASE + "/en/support/" + issue,
        "history": history,
        "file_name": fname,
        "file_size": fsize,
        "file_languages": langs,
    }


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": [], "found": []}


def save(state, records):
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    OUT.write_text(json.dumps(records, indent=2, ensure_ascii=False),
                   encoding="utf-8")


def main():
    bucket = issues_in_bucket()
    state = load_state()
    done = set(state.get("done") or [])
    records = []
    if OUT.exists():
        try:
            records = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            records = []
    have = {r["issue"] for r in records}

    todo = [i for i in bucket if i not in done]
    print("Canon SG crawl, bucket " + PREFIX)
    print("  issues in bucket: " + str(len(bucket)))
    print("  already processed: " + str(len(done)))
    print("  remaining: " + str(len(todo)))
    if OFFLINE:
        print("  offline: parsing cached pages only")
    else:
        print("  delay: " + str(DELAY) + "s, so about "
              + str(round(len(todo) * DELAY / 3600.0, 1)) + " hours"
              + ("" if LIMIT is None else ", limited to " + str(LIMIT) + " fetches"))
    print()

    fetched = 0
    for issue in todo:
        if LIMIT is not None and fetched >= LIMIT:
            print("  limit reached, stopping cleanly")
            break
        page, how = fetch(issue)
        if how == "fetched":
            fetched += 1
        if not page:
            print("  %s  %s" % (issue, how))
            if how.startswith("http") or how.startswith("curl"):
                done.add(issue)
            state["done"] = sorted(done)
            save(state, records)
            if how != "not cached" and not OFFLINE:
                time.sleep(DELAY)
            continue

        rec = parse(issue, page)
        done.add(issue)
        if rec:
            if rec["issue"] not in have:
                records.append(rec)
                have.add(rec["issue"])
            print("  %s  %-22s %-9s %-8s cl=%-3d install=%d history=%d  %s"
                  % (issue, rec["model"], rec["version"], rec["platform"],
                     len(rec["changelog"]), len(rec["install"]),
                     len(rec["history"]), how))
        else:
            print("  %s  -  %s" % (issue, how))
        state["done"] = sorted(done)
        save(state, records)
        if how == "fetched" and not OFFLINE:
            time.sleep(DELAY)

    print()
    print("=" * 66)
    print("cinema firmware pages found: " + str(len(records)))
    models = {}
    for r in records:
        models.setdefault(r["model"], []).append(r)
    print("distinct bodies: " + str(len(models)))
    for m in sorted(models):
        rs = models[m]
        vers = sorted({x["version"] for x in rs})
        inst = sum(1 for x in rs if x["install"])
        hist = sum(1 for x in rs if x["history"])
        cl = sum(1 for x in rs if x["changelog"])
        print("  %-24s %d page(s), v %s, changelog %d, install %d, history %d"
              % (m, len(rs), ", ".join(vers), cl, inst, hist))
    print()
    print("Wrote " + str(OUT) + " and " + str(STATE))
    print("Re-run to continue. Cached pages are never re-fetched.")


if __name__ == "__main__":
    main()
