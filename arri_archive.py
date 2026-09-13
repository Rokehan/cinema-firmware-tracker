#!/usr/bin/env python3
"""
arri_archive.py  -  previous ARRI SUP versions from each camera's own
SUP archive page.

Why this exists: previous ARRI versions used to come from release-notes labels
in all_downloads, so every entry had an empty changelog and linked to a PDF
instead of the firmware package. ARRI publishes a per-camera archive with the
real thing.

Pages are found, never constructed:
  1. slug + source_url from arri_cameras.json
  2. fetch the camera page, read the archive link OFF it (href with
     "sup-archive")
  3. fetch the archive page

Structure, confirmed against live HTML on 6 cameras:
  <h2 class="ci-section-title"> SUP 6.0.2 </h2>   per version, then
  <div class="ci-dl-teaser"><a href="..."> with a title span, a footer date
  and a footer filetype.
  data-visible-entries="1000", so the load-more control is display only and
  every version is already in the HTML. No extra requests.

Heading wording varies and both shapes are real:
  "SUP 6.0.2"                      ALEXA 35, 265, Mini, AMIRA, SXT
  "LF SUP 4.2"                     ALEXA LF prefixes the camera name
  "SUP 5.0.1 (ALEXA 35 Xtreme only)"   trailing qualifier
  "SUP 1.0.3 Revision 7"           trailing revision
  "SUP1.2.1"                       no space
So the version is matched anywhere in the heading and any trailing text is
kept verbatim as "note" rather than dropped.

Downloads are classified, not assumed. A canto.de link can be a zip package,
a PDF, or a short /b/ album page, so content-type and file extension decide.
Where ARRI publishes no package at all (LF SUP 3.0: "not available for
download on the ARRI website. Please contact ARRI Service") the record keeps
its release notes and carries no package. That is rule 7, not a gap.

Output: arri_archive.json
Flags:  --debug  save fetched HTML as debug_arri_*.html
        --only <slug>
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
DELAY = 0.6

MONTHS = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
          "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
          "Nov": "11", "Dec": "12"}

SECTION_RX = re.compile(
    r'<h2[^>]*class="[^"]*ci-section-title[^"]*"[^>]*>(.*?)</h2>', re.S | re.I)

# version anywhere in the heading, with whatever follows kept as a note
VERSION_RX = re.compile(r"SUP\s*([0-9]+(?:\.[0-9]+){0,3})\s*(.*)$", re.I)


def curl(url, timeout=45):
    """Fetch a URL with curl. Returns (body, ok)."""
    cmd = ["curl", "-s", "-L", "--compressed", "--max-time", str(timeout),
           "-w", "%{http_code}"] + HEADERS + [url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout + 10)
        b = r.stdout
        if len(b) >= 3:
            code, body = b[-3:], b[:-3]
            return body, (code == "200" and len(body) > 1000)
        return "", False
    except Exception as exc:
        print("    curl error: " + str(exc))
        return "", False


def squash(t):
    return " ".join(str(t).split())


def strip_tags(t):
    return squash(re.sub(r"<[^>]+>", " ", str(t)))


def absolute(u):
    u = htmlmod.unescape(str(u)).strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return BASE + u
    return u


def iso_date(s):
    """ARRI writes 'Jul. 7, 2026'. Returns 2026-07-07, or "" if unparsed."""
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", squash(s))
    if not m:
        return ""
    mon = MONTHS.get(m.group(1).title())
    if not mon:
        return ""
    return m.group(3) + "-" + mon + "-" + m.group(2).zfill(2)


def find_archive_url(html):
    """The archive link as published on the camera page. Never constructed."""
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html):
        u = htmlmod.unescape(m.group(1))
        low = u.lower()
        if "sup-archive" in low or ("firmware" in low and "archive" in low
                                   and "archive-technologies" not in low):
            return absolute(u)
    return ""


def canto_name(href):
    m = re.search(r"[?&]name=([^&]+)", href)
    if not m:
        return ""
    return htmlmod.unescape(m.group(1)).replace("+", " ")


def kind_of(href, title):
    """package / pdf / page. Decided from the URL, never from position.

    A canto.de link is a zip package, a PDF, or a short /b/ album page, so
    content-type and extension decide. ARRI ships .pkg for ALEXA LF.
    """
    low = htmlmod.unescape(href).lower()
    name = canto_name(low)
    if "content-type=application%2fzip" in low or "content-type=application/zip" in low:
        return "package"
    if "content-type=application%2fpdf" in low or "content-type=application/pdf" in low:
        return "pdf"
    if re.search(r"\.(zip|pkg|tar\.gz|tgz)(\?|&|$)", name or low):
        return "package"
    if re.search(r"\.pdf(\?|&|$)", name or low):
        return "pdf"
    if "canto.de/b/" in low:
        return "page"
    if "canto.de" in low:
        return "page"
    return ""


def is_notes(href, title):
    low = (htmlmod.unescape(href) + " " + title).lower()
    return "release-notes" in low or "release notes" in low


def dashed(version):
    return version.replace(".", "-")


def teasers(chunk):
    """Every ci-dl-teaser in this chunk as href/title/date/filetype."""
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


def sections(html):
    """(version, note, chunk) per SUP section, in ARRI's own page order."""
    marks = []
    for m in SECTION_RX.finditer(html):
        title = strip_tags(m.group(1))
        vm = VERSION_RX.search(title)
        if not vm:
            continue
        note = squash(vm.group(2)).strip(" -")
        marks.append((vm.group(1), note, m.end(), title))
    out = []
    for i, (ver, note, end, title) in enumerate(marks):
        stop = marks[i + 1][2] if i + 1 < len(marks) else len(html)
        # cut back to the start of the next heading, not past its end
        chunk = html[end:stop]
        nxt = SECTION_RX.search(chunk)
        if nxt:
            chunk = chunk[:nxt.start()]
        out.append((ver, note, chunk, title))
    return out


def pick(items, version):
    """Prefer the item naming this version, else the first. Never invents."""
    if not items:
        return None
    want = dashed(version)
    for it in items:
        hay = (htmlmod.unescape(it["href"]) + " " + it["title"]).lower()
        if want in hay.lower() or version in it["title"]:
            return it
    return items[0]


def parse_archive(html):
    """One record per SUP version, in ARRI's page order (true release order)."""
    versions = []
    for ver, note, chunk, title in sections(html):
        pkgs = []
        pdfs = []
        pages = []
        for t in teasers(chunk):
            kind = kind_of(t["href"], t["title"])
            if kind == "package":
                pkgs.append(t)
            elif kind == "pdf" or t["href"].lower().endswith(".pdf"):
                pdfs.append(t)
            elif kind == "page":
                pages.append(t)
        notes = [p for p in pdfs if is_notes(p["href"], p["title"])]
        pkg = pick(pkgs, ver)
        # a short canto.de /b/ album link is the download for some versions.
        # Keep it rather than dropping it, flagged as page-style so the site
        # shows rule 3's arrow instead of promising a file.
        pkg_kind = "file" if pkg else ""
        if pkg is None and pages:
            pkg = pick(pages, ver)
            pkg_kind = "page"
        note_pdf = pick(notes, ver) or None
        if pkg is None and note_pdf is None and not pages:
            continue
        stamp = (pkg or note_pdf or pages[0])["date"]
        size = ""
        if note_pdf and "|" in note_pdf["filetype"]:
            size = squash(note_pdf["filetype"].split("|", 1)[1])
        versions.append({
            "version": "SUP " + ver,
            "note": note,
            "heading": title,
            "date": iso_date(stamp),
            "date_text": stamp,
            "package_url": pkg["href"] if pkg else "",
            "package_kind": pkg_kind,
            "package_label": (pkg["title"] if pkg else "")
                             or (canto_name(pkg["href"]) if pkg else ""),
            "notes_url": note_pdf["href"] if note_pdf else "",
            "notes_label": note_pdf["title"] if note_pdf else "",
            "notes_size": size,
            "extra_pdfs": len(pdfs) - len(notes),
        })
    return versions


def main():
    src = Path("arri_cameras.json")
    if not src.exists():
        sys.exit("arri_cameras.json not found. Run arri_cameras.py first.")
    cams = json.loads(src.read_text(encoding="utf-8"))
    if ONLY:
        cams = [c for c in cams if ONLY in str(c.get("slug"))]

    print("ARRI SUP archives")
    print("cameras: " + str(len(cams)))
    print()

    out = []
    no_archive = []
    for cam in cams:
        slug = cam.get("slug") or "?"
        page_url = cam.get("source_url")
        print("=" * 62)
        print(slug)
        if not page_url:
            print("  no source_url, skipped")
            no_archive.append(slug)
            continue

        html, ok = curl(page_url)
        time.sleep(DELAY)
        if not ok:
            print("  camera page fetch failed")
            no_archive.append(slug)
            continue
        if DEBUG:
            Path("debug_arri_cam_" + slug + ".html").write_text(
                html, encoding="utf-8")

        archive_url = find_archive_url(html)
        if not archive_url:
            print("  no SUP archive published for this camera, skipped")
            no_archive.append(slug)
            continue
        print("  archive: " + archive_url)

        ahtml, ok = curl(archive_url)
        time.sleep(DELAY)
        if not ok:
            print("  archive fetch failed")
            no_archive.append(slug)
            continue
        if DEBUG:
            Path("debug_arri_arc_" + slug + ".html").write_text(
                ahtml, encoding="utf-8")

        versions = parse_archive(ahtml)
        if not versions:
            heads = [strip_tags(m.group(1)) for m in SECTION_RX.finditer(ahtml)]
            print("  no SUP sections parsed. Section titles seen: "
                  + (", ".join(h[:34] for h in heads[:6]) or "none"))
            no_archive.append(slug)
            continue

        pkgs = sum(1 for v in versions if v["package_url"])
        nts = sum(1 for v in versions if v["notes_url"])
        print("  versions: %d   packages: %d   release notes: %d"
              % (len(versions), pkgs, nts))
        for v in versions:
            print("    %-12s %-11s %-4s %-6s %s"
                  % (v["version"], v["date"] or "no date",
                     ("pkg" if v["package_kind"] == "file"
                      else ("pg" if v["package_url"] else "---")),
                     "notes" if v["notes_url"] else "-----",
                     v["note"][:34]))
        out.append({
            "slug": slug,
            "camera_url": page_url,
            "archive_url": archive_url,
            "versions": versions,
        })

    Path("arri_archive.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(len(r["versions"]) for r in out)
    pkgs = sum(1 for r in out for v in r["versions"]
               if v["package_kind"] == "file")
    pgs = sum(1 for r in out for v in r["versions"]
              if v["package_kind"] == "page")
    nts = sum(1 for r in out for v in r["versions"] if v["notes_url"])
    print()
    print("=" * 62)
    print("Wrote %d cameras, %d archived versions to arri_archive.json"
          % (len(out), total))
    print("with a firmware file:    %d/%d" % (pkgs, total))
    print("page-style download:     %d/%d" % (pgs, total))
    print("with release notes:      %d/%d" % (nts, total))
    if no_archive:
        print("no archive: " + ", ".join(no_archive))


if __name__ == "__main__":
    main()
