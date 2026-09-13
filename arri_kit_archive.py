#!/usr/bin/env python3
"""
arri_kit_archive.py  -  previous versions for ARRI's non-camera kit.

arri_kit.py already records each product's own SUP archive url, e.g.
    .../software-updates-ecs/ria-1-software-update/ria-1-sup-archive
for 18 of the 33 items, but nothing fetched them, so every accessory showed
"no earlier versions" while ARRI publishes a full history.

The archive pages use the same structure as the camera ones, which
arri_archive.py already parses: a per-version <h2 class="ci-section-title">
followed by ci-dl-teaser rows carrying the package, the release notes, a date
and a stated filetype.

Two differences from the camera archives, both handled:
  - headings are worded per product, "RIA-1 SUP 2.4.0" or plain "SUP 2.4.0", so
    the version is matched anywhere in the heading and any trailing qualifier
    is kept
  - ECS firmware is a .cmf file that ARRI's CMS renames to -data.txt, so the
    teaser's stated filetype decides what is a file, exactly as in arri_kit.py

Reads arri_kit.json, writes arri_kit_archive.json keyed by slug. Products with
no archive url are skipped and reported.

Output: arri_kit_archive.json
Flags:  --debug  save each archive page
        --only <text>
"""
from pathlib import Path
import html as htmlmod
import json
import re
import subprocess
import sys
import time

NL = chr(10)
DEBUG = "--debug" in sys.argv
ONLY = None
if "--only" in sys.argv:
    i = sys.argv.index("--only")
    if i + 1 < len(sys.argv):
        ONLY = sys.argv[i + 1]

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

BASE = "https://www.arri.com"
DELAY = 0.8

MONTHS = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
          "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
          "Nov": "11", "Dec": "12"}

SECTION_RX = re.compile(
    r'<h2[^>]*class="[^"]*ci-section-title[^"]*"[^>]*>(.*?)</h2>', re.S | re.I)

VERSION_RX = re.compile(r"(?:SUP|Version|Ver\.?|Firmware)?\s*"
                        r"([0-9]+(?:\.[0-9]+){1,3})\s*(.*)$", re.I)


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
    except Exception as exc:
        print("    curl error: " + str(exc))
        return "", False


def squash(t):
    return " ".join(str(t).split())


def strip_tags(t):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", str(t))
    t = re.sub(r"<[^>]+>", " ", t)
    return squash(htmlmod.unescape(t))


def absolute(u):
    u = htmlmod.unescape(str(u)).strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE + u
    return u


def iso_date(s):
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", squash(s))
    if not m:
        return ""
    mon = MONTHS.get(m.group(1).title())
    if not mon:
        return ""
    return m.group(3) + "-" + mon + "-" + m.group(2).zfill(2)


def teasers(chunk):
    out = []
    for part in chunk.split('class="ci-dl-teaser"')[1:]:
        hm = re.search(r'href=["\']([^"\']+)["\']', part)
        if not hm:
            continue
        tm = re.search(r'ci-dl-teaser-title["\'][^>]*>\s*<span>(.*?)</span>',
                       part, re.S)
        dm = re.search(r'ci-dl-teaser-footer-date["\']?[^>]*>(.*?)</span>',
                       part, re.S)
        fm = re.search(r'ci-dl-teaser-footer-filetype["\']?[^>]*>(.*?)</span>',
                       part, re.S)
        out.append({
            "href": absolute(hm.group(1)),
            "title": strip_tags(tm.group(1)) if tm else "",
            "date": strip_tags(dm.group(1)) if dm else "",
            "filetype": strip_tags(fm.group(1)) if fm else "",
        })
    return out


def kind_of(href, filetype="", title=""):
    """file, pdf or page. ARRI's stated filetype beats the url extension."""
    low = htmlmod.unescape(href).lower()
    name = ""
    nm = re.search(r"[?&]name=([^&]+)", low)
    if nm:
        name = nm.group(1)
    ftype = squash(filetype).lower().split("|", 1)[0].strip()
    if ftype in ("cmf", "zip", "pkg", "bin", "fir", "tgz"):
        return "file"
    if ftype == "pdf":
        return "pdf"
    if "content-type=application%2fzip" in low:
        return "file"
    if re.search(r"\.(zip|pkg|tar\.gz|tgz|fir|bin|cmf)(\?|&|$)", name or low):
        return "file"
    if re.search(r"\.pdf(\?|&|$)", name or low):
        return "pdf"
    if "canto.de" in low:
        return "page"
    if low.endswith(".txt") or ftype == "txt":
        hay = (title + " " + href).lower()
        if re.search(r"\d+[-.]\d+[-.]\d+|sup\s*\d|\.cmf", hay):
            return "file"
    return ""


def sections(html):
    """(version, note, chunk) per version, in ARRI's own page order."""
    marks = []
    for m in SECTION_RX.finditer(html):
        title = strip_tags(m.group(1))
        vm = VERSION_RX.search(title)
        if not vm:
            continue
        marks.append((vm.group(1), squash(vm.group(2)).strip(" -"),
                      m.end(), title))
    out = []
    for i, (ver, note, end, title) in enumerate(marks):
        stop = marks[i + 1][2] if i + 1 < len(marks) else len(html)
        chunk = html[end:stop]
        nxt = SECTION_RX.search(chunk)
        if nxt:
            chunk = chunk[:nxt.start()]
        out.append((ver, note, chunk, title))
    return out


def parse_archive(html):
    versions = []
    for ver, note, chunk, title in sections(html):
        pkgs, pdfs, pages = [], [], []
        for t in teasers(chunk):
            k = kind_of(t["href"], t["filetype"], t["title"])
            if k == "file":
                pkgs.append(t)
            elif k == "pdf":
                pdfs.append(t)
            elif k == "page":
                pages.append(t)
        notes = [p for p in pdfs
                 if re.search(r"release[ -]note", (p["href"] + " " + p["title"]),
                              re.I)]
        pkg = pkgs[0] if pkgs else (pages[0] if pages else None)
        pkg_kind = "file" if pkgs else ("page" if pages else "")
        note_pdf = notes[0] if notes else None
        if pkg is None and note_pdf is None:
            continue
        stamp = (pkg or note_pdf)["date"]
        size = ""
        if note_pdf and "|" in (note_pdf.get("filetype") or ""):
            size = squash(note_pdf["filetype"].split("|", 1)[1])
        versions.append({
            "version": "SUP " + ver if re.search(r"SUP", title, re.I) else ver,
            "note": note,
            "date": iso_date(stamp),
            "date_text": stamp,
            "package_url": pkg["href"] if pkg else "",
            "package_kind": pkg_kind,
            "package_label": (pkg["title"] if pkg else ""),
            "notes_url": note_pdf["href"] if note_pdf else "",
            "notes_label": note_pdf["title"] if note_pdf else "",
            "notes_size": size,
        })
    return versions


def main():
    src = Path("arri_kit.json")
    if not src.exists():
        sys.exit("arri_kit.json not found. Run arri_kit.py first.")
    rows = json.loads(src.read_text(encoding="utf-8"))
    if ONLY:
        rows = [r for r in rows if ONLY.lower() in
                (str(r.get("slug", "")) + str(r.get("product", ""))).lower()]

    print("ARRI kit archives")
    print("items: " + str(len(rows)))
    print()

    out = {}
    no_arc = []
    for r in rows:
        product = r.get("product") or "?"
        arc = r.get("archive_url")
        if not arc:
            no_arc.append(product)
            continue
        print("=" * 62)
        print(product)
        print("  " + arc)
        html, ok = curl(arc)
        time.sleep(DELAY)
        if not ok:
            print("  fetch failed")
            no_arc.append(product)
            continue
        if DEBUG:
            Path("debug_kitarc_" + re.sub(r"\W+", "_", product) + ".html").write_text(
                html, encoding="utf-8")
        versions = parse_archive(html)
        if not versions:
            heads = [strip_tags(m.group(1)) for m in SECTION_RX.finditer(html)]
            print("  no versions parsed. headings seen: "
                  + (", ".join(h[:30] for h in heads[:6]) or "none"))
            no_arc.append(product)
            continue
        # drop the current version, it is not a previous one
        cur = str(r.get("version") or "")
        cur_num = re.sub(r"[^0-9.]", "", cur)
        kept = [v for v in versions
                if re.sub(r"[^0-9.]", "", v["version"]) != cur_num]
        print("  versions: " + str(len(versions))
              + ", previous: " + str(len(kept)))
        for v in kept:
            print("    %-14s %-11s %-5s %s"
                  % (v["version"], v["date"] or "no date",
                     v["package_kind"] or "-",
                     "notes" if v["notes_url"] else ""))
        out[r.get("slug") or product] = {
            "product": product,
            "archive_url": arc,
            "versions": kept,
        }
        print()

    Path("arri_kit_archive.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(len(v["versions"]) for v in out.values())
    print("=" * 62)
    print("Wrote " + str(len(out)) + " products, " + str(total)
          + " previous versions to arri_kit_archive.json")
    if no_arc:
        print("no archive: " + ", ".join(no_arc[:14]))


if __name__ == "__main__":
    main()
