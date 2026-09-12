"""Scrape RED camera firmware from red.com.

RED's download index is plain HTML, so the camera list is discovered live
every run (same approach as ARRI). Each camera has one page holding its full
release history, newest version first:

    VERSION 2.2.4 | 183.6 MB  Release Date: 5/18/2026
    ... SIGNIFICANT CHANGES SINCE V-RAPTOR 2.1.1
    - Added ...

Only the newest block is recorded as current. The h1 is the authority for the
product name. RED puts the actual file behind a login, so no direct download
URL is claimed: firmware_kind is "page" and the link points at RED's own
page. Nothing is invented.

Writes red_cameras.json.
"""

import json
import re
import time
import urllib.request

INDEX = "https://www.red.com/downloads"
SITE = "https://www.red.com"

# Firmware pages that are not camera bodies. RED lists monitor and media
# firmware in the same section.
NOT_A_CAMERA = ("red-touch", "cfexpress", "connect", "redcine", "lcd")

VERSION_RE = re.compile(r"VERSION\s+(\d+(?:\.\d+)+)", re.I)
DATE_RE = re.compile(
    r"Release\s*Date:?[\s|]*(\d{1,2})/(\d{1,2})/(\d{4})", re.I)
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*MB", re.I)
BREAK = " ||| "


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode("utf-8", "replace")


def flat(fragment, keep_items=False):
    """Tags out. With keep_items, list items stay separable."""
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    if keep_items:
        # Headings and list items become separable, so a bullet list can be
        # read back as a list rather than one run-on sentence.
        fragment = re.sub(r"(?i)</(li|p|h[1-6])\s*>", BREAK, fragment)
        fragment = re.sub(r"(?i)<br\s*/?>", BREAK, fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    fragment = fragment.replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"[ \t]+", " ", fragment).strip()


def discover_camera_pages():
    """Read RED's own download index for camera firmware slugs."""
    html = fetch(INDEX)
    found = re.findall(r'href="([^"]*/download/[^"]*firmware[^"]*)"', html)
    slugs = []
    for href in found:
        slug = href.rstrip("/").split("/")[-1]
        if slug in slugs:
            continue
        if any(word in slug.lower() for word in NOT_A_CAMERA):
            continue
        slugs.append(slug)
    return slugs


def product_name(html, slug):
    """RED's own heading, minus the trailing FIRMWARE."""
    heads = re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if heads:
        name = flat(heads[0])
        name = re.sub(r"(?i)\s*firmware\s*$", "", name).strip()
        if name:
            return name
    return slug.replace("-firmware", "").replace("-", " ").upper()


def newest_release(html):
    """Version, ISO date, size and change list from the newest block."""
    text = flat(html, keep_items=True)
    blocks = list(VERSION_RE.finditer(text))
    if not blocks:
        return None

    first = blocks[0]
    stop = blocks[1].start() if len(blocks) > 1 else len(text)
    block = text[first.start():stop]

    version = "V" + first.group(1)

    date = None
    hit = DATE_RE.search(block)
    if hit:
        month, day, year = hit.group(1), hit.group(2), hit.group(3)
        date = year + "-" + month.zfill(2) + "-" + day.zfill(2)

    size = None
    size_hit = SIZE_RE.search(block)
    if size_hit:
        size = size_hit.group(1) + " MB"

    features = []
    pieces = [p.strip(" |") for p in block.split(BREAK.strip())]
    collecting = False
    for piece in pieces:
        if re.match(r"(?i)SIGNIFICANT CHANGES", piece):
            collecting = True
            continue
        if not collecting:
            continue
        if re.match(r"(?i)OPERATIONAL NOTES|copyright|\(c\) 20|© 20|login", piece):
            break
        item = re.sub(r"^\d+\.\s*", "", piece).strip()
        if 3 < len(item) < 120:
            features.append(item)

    return {
        "version": version,
        "release_date": date,
        "size": size,
        "features": features[:12],
        "history_count": len(blocks),
    }


def main():
    slugs = discover_camera_pages()
    print("Discovered " + str(len(slugs)) + " camera firmware pages")
    print("")

    results = []
    for slug in slugs:
        url = SITE + "/download/" + slug
        print("Fetching: " + slug)
        try:
            html = fetch(url)
        except Exception as err:
            print("  fetch failed: " + str(err))
            print("")
            continue

        name = product_name(html, slug)
        release = newest_release(html)

        if release is None:
            print("  " + name + ": no version block found, skipped")
            print("")
            continue

        results.append({
            "manufacturer": "RED",
            "product": name,
            "slug": slug,
            "version": release["version"],
            "release_date": release["release_date"],
            "release_precision": "day",
            "status": "firmware_available",
            "source_url": url,
            "firmware_url": url,
            "firmware_kind": "page",
            "notes_url": url,
            "archive_url": None,
            "summary": None,
            "features": release["features"],
            "file_size": release["size"],
        })

        print("  " + name)
        print("  Version: " + release["version"]
              + "   Date: " + str(release["release_date"])
              + "   Size: " + str(release["size"]))
        print("  Releases on page: " + str(release["history_count"]))
        print("  Changes captured: " + str(len(release["features"])))
        for item in release["features"][:4]:
            print("    " + item[:66])
        print("")
        time.sleep(1)

    with open("red_cameras.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    missing = [r["product"] for r in results if not r["release_date"]]
    print("Saved " + str(len(results)) + " cameras to red_cameras.json")
    if missing:
        print("No date found for: " + ", ".join(missing))


if __name__ == "__main__":
    main()
