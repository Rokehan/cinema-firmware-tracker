#!/usr/bin/env python3
"""
arri_kit.py  -  firmware for ARRI kit that is not a camera.

Why ARRI first: arri_cameras.py already reads their firmware index and
arri_archive.py already reads their per-product archives, so the page shape is
known. The accessories live in the same firmware section, which makes them the
cheapest non-camera category to add.

Sections read, each discovered from its own index page the same way
arri_cameras.py discovers bodies. No URL is constructed.

    software-updates-ecs                  Electronic Control System:
                                          Hi-5, WCU-4, cforce motors, ZMU-4,
                                          master grips, RIA-1, SXU-1, EMC-1,
                                          UMC-4, AMC-1, CUB-1/2, WVR-1,
                                          SMC-1, OCU-1, NIA-1
    software-and-firmware-updates-for-monitors    CCM-1
    software-updates-css                  Camera Stabilizer Systems: Trinity

Page shape, confirmed on the Hi-5 page:
    <h1>Hi-5 & Hi-5 SX SUP 3.5.2</h1>     product and version together
    ci-dl-teaser rows                     downloads, with a footer date
    arri.canto.de/b/XXXXX                 album page, not a direct file, so
                                          firmware_kind is "page" and the site
                                          renders rule 3's arrow
    an "SUP Download Archive" link        previous versions, same as cameras

Category is set per section, so the feed's equipment filter works without any
guessing at render time. Nothing is invented: version, date and links all come
from ARRI's own page, and a product with no version found is skipped rather
than filled in.

Output: arri_kit.json
Flags:  --debug   save each page as debug_arrikit_<slug>.html
        --only <text>   restrict to matching slugs
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
FW = "/en/technical-service/firmware/"
DELAY = 0.8

# section slug -> (category, human name)
SECTIONS = [
    ("software-updates-ecs", "Lens Control", "Electronic Control System"),
    ("software-and-firmware-updates-for-monitors", "Monitors", "Monitors"),
    ("software-updates-css", "Stabilizers", "Camera Stabilizer Systems"),
]

# a few ECS products are not lens control. Category is per product where the
# name makes the type clear, otherwise it falls back to the section default.
BY_NAME = [
    (r"\bevf\b|viewfinder|\bmvf\b", "Viewfinders"),
    (r"\bwvr\b|video receiver|transmitter|\bwvt\b", "Wireless Video"),
    (r"\bbhm\b|battery|charger|power", "Power & Media"),
    (r"\bccm\b|monitor", "Monitors"),
    (r"trinity|stabili", "Stabilizers"),
    (r"hi-?5|wcu|cforce|zmu|master grip|\bsxu\b|\bemc\b|\bumc\b|\bamc\b|"
     r"\bcub\b|\bsmc\b|\bocu\b|\bria\b|\bnia\b|\blcube\b", "Lens Control"),
]

MONTHS = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
          "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
          "Nov": "11", "Dec": "12"}


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


def category_for(name, default):
    low = " " + name.lower() + " "
    for pat, cat in BY_NAME:
        if re.search(pat, low):
            return cat
    return default


def discover(section):
    """Product pages inside one section index, from the index itself."""
    html, ok = curl(BASE + FW + section)
    time.sleep(DELAY)
    if not ok:
        return [], "index fetch failed"
    pat = r'href="' + re.escape(FW + section) + r'/([^"/?#]+)"'
    slugs = []
    for slug in re.findall(pat, html):
        low = slug.lower()
        if "archive" in low or slug in slugs:
            continue
        slugs.append(slug)
    return slugs, "ok"


def teasers(html):
    out = []
    for part in html.split('class="ci-dl-teaser"')[1:]:
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
    """file, pdf or page. ARRI's own filetype label wins over the extension.

    ARRI's CMS renames every asset it serves to "-data.txt", so the ECS
    firmware for the cforce motors, master grips, OCU-1, the LCUBEs and the
    BHM-2 all arrive as .txt urls. The teaser states the real type next to the
    size, "cmf | 1.2 MB" or "txt | 1.5 MB", and .cmf is ARRI's firmware format
    for those devices. A 1.2 MB text file is not text, so the label is trusted
    and the extension is not.
    """
    low = htmlmod.unescape(href).lower()
    name = ""
    nm = re.search(r"[?&]name=([^&]+)", low)
    if nm:
        name = nm.group(1)

    label = squash(filetype).lower()
    ftype = label.split("|", 1)[0].strip() if label else ""
    if ftype in ("cmf", "zip", "pkg", "bin", "fir", "tgz"):
        return "file"
    if ftype == "pdf":
        return "pdf"

    if "content-type=application%2fzip" in low or "content-type=application/zip" in low:
        return "file"
    if re.search(r"\.(zip|pkg|tar\.gz|tgz|fir|bin|cmf)(\?|&|$)", name or low):
        return "file"
    if re.search(r"\.pdf(\?|&|$)", name or low):
        return "pdf"
    if "canto.de" in low:
        return "page"

    # ARRI serves firmware as -data.txt. Only treat it as a file when the
    # title or url names a version, so a genuine text document is not claimed.
    if low.endswith(".txt") or ftype == "txt":
        hay = (title + " " + href).lower()
        if re.search(r"\d+[-.]\d+[-.]\d+|sup\s*\d|\.cmf", hay):
            return "file"
    return ""


def content_lines(html):
    """Page lines from the h1 to the footer, so ARRI's nav is never scanned.

    ARRI's mega-menu and footer are enormous: on the CCM-1 page the real text
    starts at line 2,895 of 3,364. Counting lines from the top of the document
    therefore reads navigation, which is why an earlier version of this
    scraper found nothing at all. Anchor on the h1 instead.
    """
    body = html
    hm = re.search(r"<h1[^>]*>", body, re.I)
    if hm:
        body = body[hm.start():]
    foot = re.search(r"(?i)<footer|footer__|ci-footer", body)
    if foot:
        body = body[:foot.start()]
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", NL, body)
    body = re.sub(r"(?i)<br\s*/?>", NL, body)
    body = re.sub(r"<[^>]+>", " ", body)
    out = [squash(x) for x in htmlmod.unescape(body).split(NL)]
    return [x for x in out if x]


CHANGELOG_HEADS = ("overview of new features", "overview of new feature",
                   "new features", "what's new", "highlights")

CHANGELOG_STOP = ("end user license agreement", "end user licence agreement",
                  "notice to user", "please take your time",
                  "for more information", "sup download archive",
                  "list of all current software", "downloads", "disclaimer")


def changelog_from(html):
    """The page's own new-features list, verbatim. Empty when absent.

    ARRI writes the changelog as page text under "Overview of new features",
    e.g. Hi-5 lists "Camera Control License for Hi-5 & Hi-5 SX" and "Bug fix for
    focus distance display on the SmallHD Lens Overlay". Sub-headings like
    "Improvements for TRINITY 2 and the TRINITY 2 Pan Axis Module" are kept as
    items because they are ARRI's own wording.
    """
    lines = content_lines(html)

    at = None
    for i, line in enumerate(lines):
        low = line.lower().rstrip(":")
        if any(low.startswith(h) for h in CHANGELOG_HEADS):
            at = i
            break
    if at is None:
        return []

    out = []
    for line in lines[at + 1:at + 40]:
        low = line.lower()
        if any(low.startswith(s) for s in CHANGELOG_STOP):
            break
        # The feature list ends where ARRI's announcement prose starts, and
        # before the download rows, whose lines are a bare date or a filetype
        # and size such as "cmf | 3 MB".
        if ANNOUNCE_RX.match(line):
            break
        if re.match(r"(?i)^(?:cmf|pdf|txt|zip|download)\s*(?:\||$)", line):
            break
        if re.match(r"(?i)^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                    r"[a-z]*\.?\s+\d{1,2},?\s+\d{4}$", line):
            break
        item = line.lstrip("-\u2013\u2022 ").strip()
        if not item or len(item) < 3:
            continue
        if item in out:
            continue
        out.append(item)
        if len(out) >= 24:
            break
    return out


# ARRI's own sentence shapes on these pages, verbatim:
#   "We hereby announce the release of the Software Update Package SUP 3.2.2..."
#   "We highly recommend that you take your time to go through the release
#    notes and the user manual before operating the device."
ANNOUNCE_RX = re.compile(
    r"(?i)^\s*(?:we\s+(?:hereby|highly|are|would|announce|recommend)"
    r"|arri\s+(?:is\s+pleased|announces|recommends)"
    r"|this\s+(?:software\s+)?update"
    r"|the\s+(?:software\s+)?update\s+package"
    r"|with\s+(?:this\s+)?sup"
    r"|please\s+note)")


def summary_from(html, product, version):
    """ARRI's own announcement sentences, when there is no feature list.

    Most accessory pages carry prose rather than bullets, e.g. the EJW-1:
    "We hereby announce the release of the Software Update Package SUP 3.2.2
    for the External Jog-Wheels EJW-1. We highly recommend updating your EJW-1
    to this Software Update Package." That is ARRI's wording and it is more
    use than an empty section, so it becomes the summary. It is never mixed
    with the changelog, which stays reserved for a real feature list.
    """
    lines = content_lines(html)

    picked = []
    for line in lines:
        low = line.lower()
        if low.startswith("end user licen") or low.startswith("notice to user"):
            break
        if len(line) < 30:
            continue
        if ANNOUNCE_RX.match(line):
            if line not in picked:
                picked.append(line)
        if len(picked) >= 3:
            break
    return " ".join(picked)


def parse(slug, html, section, default_cat):
    """One kit record, or None when ARRI publishes no version on the page."""
    hm = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    h1 = strip_tags(hm.group(1)) if hm else ""
    if not h1:
        return None

    # "Hi-5 & Hi-5 SX SUP 3.5.2" -> product "Hi-5 & Hi-5 SX", version "SUP 3.5.2"
    vm = re.search(r"\b(?:SUP|Version|Ver\.?|Firmware)\s*"
                   r"([0-9]+(?:\.[0-9]+){1,3})\b", h1, re.I)
    if not vm:
        vm = re.search(r"\b([0-9]+\.[0-9]+(?:\.[0-9]+){0,2})\b", h1)
    if not vm:
        return None
    version = "SUP " + vm.group(1) if re.search(r"SUP", h1, re.I) else vm.group(1)
    product = squash(h1[:vm.start()]).rstrip(" -&,")
    product = re.sub(r"\b(?:SUP|Software Update|Firmware Update|Update)\s*$",
                     "", product, flags=re.I).strip()
    if not product:
        product = squash(slug.replace("-", " ")).title()

    rows = teasers(html)
    pkg = None
    notes = None
    guides = []
    for t in rows:
        k = kind_of(t["href"], t.get("filetype"), t.get("title"))
        if k in ("file", "page") and pkg is None:
            pkg = t
            pkg_kind = k
        elif k == "pdf":
            low = (t["href"] + " " + t["title"]).lower()
            if notes is None and ("release" in low or "notes" in low):
                notes = t
            else:
                guides.append({"label": t["title"] or "Document",
                               "url": t["href"]})
    pkg_kind = kind_of(pkg["href"], pkg.get("filetype"),
                       pkg.get("title")) if pkg else ""

    date = ""
    for t in ([pkg] if pkg else []) + ([notes] if notes else []) + rows:
        if t and t.get("date"):
            date = iso_date(t["date"])
            if date:
                break
    if not date:
        date = iso_date(strip_tags(html))

    # Only a real per-product SUP archive counts. ARRI also links a generic
    # "discontinued products" archive at learn-help/config-overview/archive and
    # an archive-technologies page; both are site furniture, not this product's
    # version history, and recording them would promise previous versions the
    # page does not have.
    archive = ""
    for m in re.finditer(r'href=["\']([^"\']*archive[^"\']*)["\']', html, re.I):
        u = absolute(m.group(1))
        low = u.lower()
        if "archive-technologies" in low or "config-overview" in low \
                or "learn-help" in low:
            continue
        if "/firmware/" not in low:
            continue
        archive = u
        break

    size = ""
    if notes and "|" in (notes.get("filetype") or ""):
        size = squash(notes["filetype"].split("|", 1)[1])

    return {
        "manufacturer": "ARRI",
        "changelog": changelog_from(html),
        "summary": summary_from(html, product, version),
        "category": category_for(product + " " + slug, default_cat),
        "product": product,
        "version": version,
        "release_date": date,
        "release_precision": "day" if len(date) == 10 else "month",
        "status": "firmware_available" if pkg else "documentation_only",
        "source_url": BASE + FW + section + "/" + slug,
        "firmware_url": pkg["href"] if pkg else "",
        "firmware_kind": pkg_kind or None,
        "notes_url": notes["href"] if notes else "",
        "archive_url": archive,
        "guides": guides,
        "file_size": size,
        "file_type": (squash(pkg.get("filetype")).split("|", 1)[0].strip()
                      if pkg else ""),
        "section": section,
        "slug": slug,
    }


def main():
    out = []
    skipped = []
    for section, default_cat, label in SECTIONS:
        print("=" * 64)
        print(label + "   (" + section + ")")
        print("=" * 64)
        slugs, how = discover(section)
        if how != "ok":
            print("  " + how)
            print()
            continue
        print("  products found: " + str(len(slugs)))
        if ONLY:
            slugs = [s for s in slugs if ONLY.lower() in s.lower()]
            print("  filtered to: " + str(len(slugs)))
        print()
        for slug in slugs:
            url = BASE + FW + section + "/" + slug
            html, ok = curl(url)
            time.sleep(DELAY)
            if not ok:
                print("  %-46s fetch failed" % slug[:46])
                skipped.append(slug)
                continue
            if DEBUG:
                Path("debug_arrikit_" + slug + ".html").write_text(
                    html, encoding="utf-8")
            rec = parse(slug, html, section, default_cat)
            if rec is None:
                print("  %-46s no version on the page, skipped" % slug[:46])
                skipped.append(slug)
                continue
            out.append(rec)
            print("  %-28s %-11s %-11s %-14s %-5s cl=%d%s"
                  % (rec["product"][:28], rec["version"][:11],
                     rec["release_date"] or "no date", rec["category"],
                     rec["firmware_kind"] or "-", len(rec["changelog"]),
                     ("  summary" if rec["summary"] else "")
                     + ("  archive" if rec["archive_url"] else "")))
        print()

    Path("arri_kit.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 64)
    print("Wrote " + str(len(out)) + " items to arri_kit.json")
    cats = {}
    for r in out:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    for c in sorted(cats):
        print("  %-16s %d" % (c, cats[c]))
    withfile = sum(1 for r in out if r["firmware_kind"] == "file")
    withpage = sum(1 for r in out if r["firmware_kind"] == "page")
    withnotes = sum(1 for r in out if r["notes_url"])
    withdate = sum(1 for r in out if r["release_date"])
    withcl = sum(1 for r in out if r.get("changelog"))
    witharc = sum(1 for r in out if r.get("archive_url"))
    print()
    print("  direct file:   %d/%d" % (withfile, len(out)))
    print("  page download: %d/%d" % (withpage, len(out)))
    print("  release notes: %d/%d" % (withnotes, len(out)))
    print("  dated:         %d/%d" % (withdate, len(out)))
    withsum = sum(1 for r in out if r.get("summary"))
    print("  changelog:     %d/%d" % (withcl, len(out)))
    print("  summary:       %d/%d" % (withsum, len(out)))
    print("  neither:       %d/%d"
          % (sum(1 for r in out if not r.get("changelog")
                 and not r.get("summary")), len(out)))
    print("  SUP archive:   %d/%d" % (witharc, len(out)))
    if skipped:
        print("  skipped: " + ", ".join(skipped[:12]))


if __name__ == "__main__":
    main()
