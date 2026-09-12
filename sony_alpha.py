"""Scrape Sony Alpha body firmware (the current a7 line).

These bodies live on a different URL shape from the FX line:

    support.sony.jp/electronics/support/e-mount-body-ilce-7-series/
        <model>/downloads          -> lists the firmware page
        <model>/software/<id>      -> version, date, BODYDATA.DAT file

The model list is a whitelist, because Sony's series index is not readable
as plain HTML. Adding a body is one line in CAMERAS. Anything Sony lists
that is not body software (audio readout data, apps) is ignored.

Nothing is invented. A body whose firmware page cannot be found is reported
and left out rather than guessed at.

Writes sony_alpha.json.
"""

import json
import re
import time
import urllib.request

SITE = "https://support.sony.jp"
BASE = SITE + "/electronics/support/e-mount-body-ilce-7-series/"

# model slug -> the name Sony markets it under
CAMERAS = {
    "ilce-7m5": "\u03b17 V (ILCE-7M5)",
    "ilce-7m4": "\u03b17 IV (ILCE-7M4)",
    "ilce-7rm5": "\u03b17R V (ILCE-7RM5)",
    "ilce-7sm3": "\u03b17S III (ILCE-7SM3)",
}

# Links on the downloads page that are body software, not an app or extra.
FIRMWARE_LINK_RE = re.compile(
    r'href="([^"]*/software/\d+)"[^>]*>((?:(?!</a>).){0,200})</a>',
    re.I | re.S,
)
NOT_FIRMWARE = ("音声読み上げ", "Creators", "Imaging Edge", "Monitor", "Catalyst")

VERSION_RE = re.compile(r"Ver\.?\s*([0-9]+(?:\.[0-9]+)+)", re.I)

# 公開日：2026年5月14日  /  公開日：2026-03-18  /  2026/05/14
DATE_JP_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
DATE_ISO_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")

FILE_RE = re.compile(
    r"https://support\.d-imaging\.sony\.co\.jp/download/"
    r"[A-Za-z0-9._~/-]*BODYDATA\.DAT(?:\?fm=jp)?",
    re.I,
)
SIZE_RE = re.compile(r"([\d,]{6,})\s*(?:bytes|バイト)", re.I)

LATEST_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>(?:(?!</a>).){0,120}'
    r'(?:最新版|最新バージョン)(?:(?!</a>).){0,120}</a>',
    re.I | re.S,
)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req).read()
    for encoding in ("utf-8", "shift_jis", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def unescape(html):
    return html.replace("\\/", "/").replace("\\u002F", "/")


def flat(fragment):
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", fragment).strip()


def iso_date(text):
    hit = DATE_JP_RE.search(text)
    if hit:
        return (hit.group(1) + "-" + hit.group(2).zfill(2)
                + "-" + hit.group(3).zfill(2))
    hit = DATE_ISO_RE.search(text)
    if hit:
        return (hit.group(1) + "-" + hit.group(2).zfill(2)
                + "-" + hit.group(3).zfill(2))
    return None


def firmware_page(html):
    """The body-software page this downloads page points at."""
    best = None
    for href, raw in FIRMWARE_LINK_RE.findall(html):
        label = flat(raw)
        if "本体ソフトウェア" not in label:
            continue
        if any(word in label for word in NOT_FIRMWARE):
            continue
        version = VERSION_RE.search(label)
        candidate = {
            "url": href if href.startswith("http") else SITE + href,
            "label": label,
            "version": ("V" + version.group(1)) if version else None,
            "date": iso_date(label),
        }
        # Prefer the highest version when Sony lists several.
        if best is None:
            best = candidate
        elif candidate["version"] and best["version"]:
            new = [int(p) for p in candidate["version"][1:].split(".")]
            old = [int(p) for p in best["version"][1:].split(".")]
            if new > old:
                best = candidate
    return best


def page_details(html):
    """Version, date, file URL and size as the software page states them."""
    plain = unescape(html)
    text = flat(plain)

    version = None
    heads = re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", plain)
    for head in heads:
        hit = VERSION_RE.search(flat(head))
        if hit:
            version = "V" + hit.group(1)
            break
    if version is None:
        hit = VERSION_RE.search(text)
        if hit:
            version = "V" + hit.group(1)

    date = None
    window = re.search(r"公開日[^0-9]{0,4}([^）)]{0,24})", text)
    if window:
        date = iso_date(window.group(1))
    if date is None:
        date = iso_date(text)

    file_hit = FILE_RE.search(plain)
    file_url = file_hit.group(0) if file_hit else None

    size = None
    size_hit = SIZE_RE.search(text)
    if size_hit:
        digits = size_hit.group(1).replace(",", "")
        if digits.isdigit():
            size = str(round(int(digits) / 1000000.0, 1)) + " MB"

    return version, date, file_url, size


def main():
    results = []
    print("Bodies in CAMERAS: " + str(len(CAMERAS)))
    print("")

    for slug, product in CAMERAS.items():
        print("Fetching: " + slug)
        try:
            listing = fetch(BASE + slug + "/downloads")
        except Exception as err:
            print("  downloads page failed: " + str(err))
            print("")
            continue

        found = firmware_page(listing)
        if not found:
            print("  no body-software link on the downloads page, skipped")
            print("  (Sony may list it only on the model's support page)")
            print("")
            continue

        print("  listed as: " + found["label"][:74])

        try:
            html = fetch(found["url"])
        except Exception as err:
            print("  software page failed: " + str(err))
            print("")
            continue

        version, date, file_url, size = page_details(html)
        source = found["url"]

        if not file_url:
            hop = LATEST_RE.search(unescape(html))
            if hop:
                target = hop.group(1)
                if not target.startswith("http"):
                    target = SITE + target
                print("  via chooser -> " + target)
                try:
                    html = fetch(target)
                    v2, d2, file_url, size = page_details(html)
                    version = version or v2
                    date = date or d2
                    source = target
                except Exception as err:
                    print("  chooser page failed: " + str(err))

        version = version or found["version"]
        date = date or found["date"]

        results.append({
            "manufacturer": "Sony",
            "product": product,
            "slug": slug,
            "version": version,
            "release_date": date,
            "release_precision": "day",
            "status": "firmware_available" if file_url else "documentation_only",
            "source_url": source,
            "firmware_url": file_url,
            "firmware_kind": "file" if file_url else None,
            "notes_url": None,
            "archive_url": None,
            "summary": None,
            "features": [],
            "file_size": size,
        })

        print("  Version: " + str(version) + "   Date: " + str(date)
              + "   Size: " + str(size))
        print("  File: " + (file_url[:78] if file_url else "NOT FOUND"))
        print("")
        time.sleep(1)

    with open("sony_alpha.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    missing = [r["product"] for r in results if not r["firmware_url"]]
    print("Saved " + str(len(results)) + " of " + str(len(CAMERAS))
          + " bodies to sony_alpha.json")
    if missing:
        print("No file URL for: " + ", ".join(missing))


if __name__ == "__main__":
    main()
