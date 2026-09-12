"""Find the real firmware file URL for each Sony body.

Sony's support pages come in two shapes:

  1. A download page. The file URL sits in escaped JSON in the markup, e.g.
     https:\\/\\/support.d-imaging.sony.co.jp\\/download\\/NEX\\/Dobb4b83c7\\/BODYDATA.DAT?fm=jp
  2. A version-chooser page ("which version are you on?"), which links to
     the real download page for the latest version.

This reads sony_fx.json, resolves shape 2 to shape 1 where needed, extracts
the BODYDATA.DAT URL and the file size Sony states, and writes both back
into sony_fx.json as firmware_url / file_size / download_page.

Nothing is invented: a row with no file URL found is left without one.
No firmware is downloaded, only the pages are read.

Run:  python3 sony_files.py
"""

import json
import re
import time
import urllib.request

SOURCE = "sony_fx.json"

# Sony embeds the link inside inline JSON, so slashes arrive escaped as
# \/. The page is unescaped first, then this matches a plain URL.
FILE_RE = re.compile(
    r"https://support\.d-imaging\.sony\.co\.jp/download/"
    r"[A-Za-z0-9._~/-]*BODYDATA\.DAT(?:\?fm=jp)?",
    re.I,
)

SIZE_RE = re.compile(r"([\d,]{6,})\s*(?:bytes|バイト)", re.I)

# "Ver. 7.02（最新版）のダウンロードページに進んでください。"
LATEST_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>(?:(?!</a>).){0,120}'
    r'(?:最新版|最新バージョン)(?:(?!</a>).){0,120}</a>',
    re.I | re.S,
)

SITE = "https://support.sony.jp"


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
    """Turn inline-JSON escapes back into ordinary characters."""
    return html.replace("\\/", "/").replace("\\u002F", "/")


def file_from_page(html):
    """The BODYDATA.DAT URL and stated size, or (None, None)."""
    plain = unescape(html)
    hit = FILE_RE.search(plain)
    url = hit.group(0) if hit else None

    size = None
    size_hit = SIZE_RE.search(plain)
    if size_hit:
        digits = size_hit.group(1).replace(",", "")
        if digits.isdigit():
            megabytes = int(digits) / 1000000.0
            size = str(round(megabytes, 1)) + " MB"

    return url, size


def latest_page(html):
    """Where a version-chooser page sends you for the newest version."""
    hit = LATEST_RE.search(html)
    if not hit:
        return None
    href = hit.group(1)
    if href.startswith("http"):
        return href
    return SITE + href


def resolve(page_url):
    """Return (file_url, size, download_page). Follows one hop at most."""
    html = fetch(page_url)

    url, size = file_from_page(html)
    if url:
        return url, size, page_url

    hop = latest_page(html)
    if not hop or hop == page_url:
        return None, None, None

    html = fetch(hop)
    url, size = file_from_page(html)
    if url:
        return url, size, hop
    return None, None, hop


def main():
    with open(SOURCE, encoding="utf-8") as fh:
        rows = json.load(fh)

    found = 0
    for row in rows:
        page = row.get("page_url")
        label = str(row.get("product"))
        if not page:
            print(label + ": no page_url, skipped")
            continue

        print("Resolving: " + label)
        try:
            url, size, download_page = resolve(page)
        except Exception as err:
            print("  failed: " + str(err))
            continue

        if url:
            row["firmware_url"] = url
            row["firmware_kind"] = "file"
            if size:
                row["file_size"] = size
            if download_page and download_page != page:
                row["download_page"] = download_page
                print("  via chooser -> " + download_page)
            found += 1
            print("  FILE " + url)
            print("  size " + str(size))
        else:
            row.pop("firmware_url", None)
            print("  no file URL found")
            if download_page:
                print("  chooser led to " + download_page)
        print("")
        time.sleep(1)

    with open(SOURCE, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)

    print("Updated " + SOURCE + ": " + str(found) + " of "
          + str(len(rows)) + " with a real file URL")


if __name__ == "__main__":
    main()
