#!/usr/bin/env python3
"""
teradek.py  -  Teradek firmware, from their own downloads API.

Source, found in the downloads page's theme bundle:
    https://update.teradek.com/wares.php                  41 product slugs
    https://update.teradek.com/wares.php?product=<slug>   that product's wares

Each ware carries everything the site needs, so one request per product covers
all four requirements:
    version   e.g. "4.4.10", "2.2.20260204"
    pubdate   ISO already, e.g. "2025-08-18"
    notes     markdown changelog, "New Features", "Bug Fixes" and so on
    inotes    install notes, when Teradek publishes them
    filename  a real download.php link to a file on cdn.teradek.com
    platform  "Firmware", "Mac OSX", "Windows"
    part      "firmware", "update tool", "ctrl5" and similar
    title     Teradek's own product name, e.g. "CTRL.5 Firmware"

Because several wares share a product slug, the newest firmware becomes the
entry and the older ones become its previous versions. That is the whole
version history, free.

Choices, and why:
  - Only firmware is listed as an item. A ware whose part or title says update
    tool, manager, app or utility is a companion program, not device firmware,
    so it is attached to the entry as a guide rather than shown as a release.
  - Windows and Mac builds of the same version are one release. The file for
    the platform Teradek published first is used and the other is kept as an
    extra download.
  - A whitelist keeps the list to kit a rental house actually tracks. The API
    also serves discontinued 2012 gear, and listing it would bury the useful
    rows. Slugs are Teradek's own; nothing is renamed.
  - Categories match the site's existing facets.

Output: teradek.json
Flags:  --all     ignore the whitelist and take every product
        --only <slug>
        --debug   save each response
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import time

NL = chr(10)
DEBUG = "--debug" in sys.argv
TAKE_ALL = "--all" in sys.argv
ONLY = None
if "--only" in sys.argv:
    i = sys.argv.index("--only")
    if i + 1 < len(sys.argv):
        ONLY = sys.argv[i + 1]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = [
    "-H", "User-Agent: " + UA,
    "-H", "Accept: application/json, text/javascript, */*; q=0.01",
    "-H", "X-Requested-With: XMLHttpRequest",
    "-H", "Accept-Language: en-US,en;q=0.9",
    "-H", "Accept-Encoding: gzip, deflate, br",
    "-H", "Referer: https://teradek.com/pages/downloads",
]

API = "https://update.teradek.com/wares.php"
PAGE = "https://teradek.com/pages/downloads#"
DELAY = 0.7

# kit a rental house tracks, mapped to the site's categories.
# slug -> (category, display name). Teradek's own naming, tidied only.
KEEP = {
    "bolt6": ("Wireless Video", "Bolt 6"),
    "bolt4k": ("Wireless Video", "Bolt 4K"),
    "bolt": ("Wireless Video", "Bolt"),
    "ranger": ("Wireless Video", "Ranger"),
    "node": ("Wireless Video", "Node"),
    "link-ax": ("Wireless Video", "Link AX"),
    "link": ("Wireless Video", "Link / Link Pro"),
    "prism": ("Wireless Video", "Prism Rack v1"),
    "prism-v2": ("Wireless Video", "Prism Rack v2"),
    "prism-mobile": ("Wireless Video", "Prism Flex"),
    "prism-bond": ("Wireless Video", "Prism Mobile"),
    "prism-jetpack": ("Wireless Video", "Prism Jetpack"),
    "serv-pro": ("Wireless Video", "Serv Pro"),
    "serv-4k": ("Wireless Video", "Serv 4K"),
    "serv-micro": ("Wireless Video", "Serv Micro"),
    "teradekrt": ("Lens Control", "Teradek RT"),
    "sphere": ("Wireless Video", "Sphere"),
    "cube": ("Wireless Video", "Cube"),
    "cubepro": ("Wireless Video", "Cube Pro"),
    "vidiu-go": ("Wireless Video", "VidiU Go"),
    "vidiu-x": ("Wireless Video", "VidiU X"),
    "vidiu-pro": ("Wireless Video", "VidiU Pro"),
    "colr": ("Monitors", "Colr"),
    "vuer": ("Monitors", "VUER"),
    "ace750": ("Wireless Video", "Ace 750"),
    "art": ("Wireless Video", "ART"),
}

# a ware that is a companion program, not device firmware
TOOL_RX = re.compile(
    r"(?i)\b(manager|update tool|utility|app|assistant|client|"
    r"software|installer|driver|discovery|core)\b")

# platforms that mean a desktop program rather than firmware
DESKTOP = re.compile(r"(?i)mac ?os|windows|win32|win64|linux")


def sh(args, timeout=50):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, b"", b"timeout"


def curl_json(url):
    code, out, err = sh(["curl", "-s", "-L", "--compressed", "--max-time", "35",
                         "-w", "%{http_code}"] + HEADERS + [url])
    if code != 0 or len(out) < 4:
        return None, "curl rc=" + str(code)
    body = out.decode("utf-8", errors="replace")
    status, body = body[-3:], body[:-3]
    if status != "200":
        return None, "http " + status
    try:
        return json.loads(body), "ok"
    except Exception as exc:
        return None, "json: " + str(exc)[:60]


def squash(t):
    return " ".join(str(t).split())


def vtuple(v):
    parts = re.findall(r"\d+", str(v or ""))
    return tuple(int(p) for p in parts[:6]) or (0,)


def https(url):
    """Teradek publishes some links as http. Their own page rewrites them."""
    u = squash(url)
    if u.startswith("http://update.teradek.com"):
        u = "https://" + u[len("http://"):]
    return u


def is_firmware(w):
    """Device firmware, as opposed to a desktop companion program."""
    part = squash(w.get("part") or "").lower()
    title = squash(w.get("title") or "")
    platform = squash(w.get("platform") or "")
    if "firmware" in part or "firmware" in title.lower():
        return True
    if TOOL_RX.search(title) or TOOL_RX.search(part):
        return False
    if DESKTOP.search(platform):
        return False
    return True


def changelog_of(notes):
    """Teradek's markdown notes as a list of items, verbatim.

    The notes open with a title line and use ==== and ---- underlines with
    "* " bullets. Underlines and the repeated title are dropped; every bullet
    and section heading is kept in Teradek's own words.
    """
    if not notes:
        return []
    out = []
    for raw in str(notes).split(NL):
        line = raw.rstrip()
        if not line.strip():
            continue
        if re.fullmatch(r"[=\-]{3,}", line.strip()):
            continue
        item = line.strip()
        if item.startswith(("* ", "- ", "+ ")):
            item = item[2:].strip()
        if not item:
            continue
        if out and item == out[0]:
            continue
        out.append(item)
        if len(out) >= 60:
            break
    # the first line is the document title, e.g.
    # "Teradek Bolt 6/Bolt 4K Firmware Version 4.4.10"
    if out and re.search(r"(?i)version\s+[\d.]+\s*$", out[0]):
        out = out[1:]
    return out


# Teradek usually leaves inotes empty and writes the procedure inside the
# release notes instead, under its own heading. These are the headings they use.
INSTALL_HEADS = re.compile(
    r"(?i)^\s*(upgrade instructions?|update instructions?|installation"
    r"|how to (?:update|upgrade|install)|upgrade procedure|updating"
    r"|before (?:you )?(?:update|upgrade)|important notes?)\s*:?\s*$")

# a heading that means we are back to describing changes
CHANGE_HEADS = re.compile(
    r"(?i)^\s*(new features?|bug fixes?|fixes|changes and improvements"
    r"|improvements|components|known issues?|notes?|compatibility)\s*:?\s*$")


def split_notes(notes):
    """(changelog items, install blocks) from one markdown notes field.

    Teradek's notes are a title line, then ==== and ---- underlined headings
    with "* " bullets. Where a heading names an install procedure, the lines
    under it are install steps rather than changes, so they are separated and
    both keep Teradek's own wording.
    """
    if not notes:
        return [], []
    lines = []
    for raw in str(notes).split(NL):
        line = raw.rstrip()
        if not line.strip():
            continue
        if re.fullmatch(r"[=\-]{3,}", line.strip()):
            continue
        lines.append(line.strip())

    # the first line is the document title
    if lines and re.search(r"(?i)version\s+[\d.]+\s*$", lines[0]):
        lines = lines[1:]

    changes = []
    blocks = []
    mode = "change"
    current = None
    for line in lines:
        if INSTALL_HEADS.match(line):
            mode = "install"
            current = {"heading": line.rstrip(":"), "items": []}
            blocks.append(current)
            continue
        if CHANGE_HEADS.match(line):
            mode = "change"
            current = None
            changes.append(line.rstrip(":"))
            continue
        item = line
        if item.startswith(("* ", "- ", "+ ")):
            item = item[2:].strip()
        if not item:
            continue
        if mode == "install" and current is not None:
            current["items"].append(item)
        else:
            if item not in changes:
                changes.append(item)
        if len(changes) >= 60:
            break
    blocks = [b for b in blocks if b["items"]]
    return changes, blocks


def install_of(w):
    """Install steps: inotes when present, else the notes' own procedure."""
    if squash(w.get("inotes") or ""):
        items = changelog_of(w.get("inotes"))
        if items:
            return [{"heading": "How to install", "items": items}]
    return split_notes(w.get("notes"))[1]


def main():
    print("Teradek firmware")
    data, how = curl_json(API)
    if data is None:
        sys.exit("product list failed: " + how)
    slugs = [s for s in (data.get("products") or []) if isinstance(s, str)]
    print("  products offered by the api: " + str(len(slugs)))

    wanted = slugs if TAKE_ALL else [s for s in slugs if s in KEEP]
    if ONLY:
        wanted = [s for s in slugs if ONLY.lower() in s.lower()]
    print("  tracking: " + str(len(wanted)))
    print()

    out = []
    skipped = []
    for slug in wanted:
        payload, how = curl_json(API + "?product=" + slug)
        time.sleep(DELAY)
        if payload is None:
            print("  %-16s %s" % (slug, how))
            skipped.append(slug)
            continue
        if DEBUG:
            Path("debug_teradek_" + slug + ".json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8")
        wares = [w for w in (payload.get("wares") or []) if isinstance(w, dict)]
        fw = [w for w in wares if is_firmware(w)]
        tools = [w for w in wares if not is_firmware(w)]
        if not fw:
            print("  %-16s no device firmware, only companion software" % slug)
            skipped.append(slug)
            continue

        # group by version: Windows and Mac builds of one version are one release
        byver = {}
        for w in fw:
            byver.setdefault(squash(w.get("version") or "?"), []).append(w)
        order = sorted(byver, key=vtuple, reverse=True)
        newest = byver[order[0]]
        lead = newest[0]

        extra = []
        for w in newest[1:]:
            if w.get("filename"):
                extra.append({"label": squash(w.get("platform") or w.get("title")
                                              or "Download"),
                              "url": https(w["filename"])})
        for w in tools:
            if w.get("filename"):
                extra.append({"label": squash(w.get("title") or "Software")
                              + (" " + squash(w.get("version")) if w.get("version") else "")
                              + (" (" + squash(w.get("platform")) + ")"
                                 if w.get("platform") else ""),
                              "url": https(w["filename"])})

        prev = []
        for v in order[1:]:
            w = byver[v][0]
            prev.append({
                "v": v,
                "d": squash(w.get("pubdate") or "") or None,
                "cl": split_notes(w.get("notes"))[0],
                "dl": https(w["filename"]) if w.get("filename") else None,
                "dl_kind": "file" if w.get("filename") else "page",
            })

        cat, name = KEEP.get(slug, ("Wireless Video",
                                    squash(lead.get("title") or slug)))
        rec = {
            "manufacturer": "Teradek",
            "category": cat,
            "product": name,
            "version": squash(lead.get("version") or ""),
            "release_date": squash(lead.get("pubdate") or ""),
            "release_precision": "day",
            "status": "firmware_available" if lead.get("filename") else "documentation_only",
            "source_url": PAGE + slug,
            "firmware_url": https(lead["filename"]) if lead.get("filename") else PAGE + slug,
            "firmware_kind": "file" if lead.get("filename") else "page",
            "notes_url": None,
            "archive_url": None,
            "summary": None,
            "changelog": split_notes(lead.get("notes"))[0],
            "features": [],
            "install": install_of(lead),
            "install_version": squash(lead.get("version")) if install_of(lead) else None,
            "install_source": PAGE + slug if install_of(lead) else None,
            "previous_versions": prev,
            "guides": extra,
            "file_name": None,
            "file_size": None,
            "platform": squash(lead.get("platform") or ""),
            "slug": slug,
        }
        out.append(rec)
        print("  %-16s %-22s %-15s %-11s cl=%-3d prev=%-2d install=%d tools=%d"
              % (slug, name[:22], rec["version"][:15],
                 rec["release_date"] or "no date", len(rec["changelog"]),
                 len(prev), len(rec["install"]), len(extra)))

    Path("teradek.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("=" * 66)
    print("Wrote " + str(len(out)) + " items to teradek.json")
    cats = {}
    for r in out:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    for c in sorted(cats):
        print("  %-16s %d" % (c, cats[c]))
    print()
    print("  direct file:   %d/%d" % (sum(1 for r in out if r["firmware_kind"] == "file"), len(out)))
    print("  dated:         %d/%d" % (sum(1 for r in out if r["release_date"]), len(out)))
    print("  changelog:     %d/%d" % (sum(1 for r in out if r["changelog"]), len(out)))
    print("  install steps: %d/%d" % (sum(1 for r in out if r["install"]), len(out)))
    print("  prev versions: %d/%d" % (sum(1 for r in out if r["previous_versions"]), len(out)))
    print("  total prev:    %d" % sum(len(r["previous_versions"]) for r in out))
    if skipped:
        print("  skipped: " + ", ".join(skipped[:14]))


if __name__ == "__main__":
    main()
