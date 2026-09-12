"""Read-only look at RED's download site. Writes nothing.

RED's structure, as far as can be seen from outside:
  - an index at red.com/downloads listing every product
  - one page per camera at red.com/download/<slug>-firmware, plain HTML,
    holding the full release history (newest version first)

This prints (1) every /download/ link the index exposes, so the real slugs
come from RED rather than from guesswork, and (2) for a few known camera
pages, the first version block it can see, so we can judge the markup before
writing a scraper.

Run:  python3 red_peek.py
"""

import re
import urllib.request

INDEX = "https://www.red.com/downloads"

KNOWN = [
    "https://www.red.com/download/v-raptor-firmware",
    "https://www.red.com/download/v-raptor-x-firmware",
    "https://www.red.com/download/v-raptor-xe-firmware",
]

VERSION_RE = re.compile(r"VERSION\s+([0-9]+(?:\.[0-9]+)*)", re.I)
DATE_RE = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
SIZE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*MB", re.I)
ZIP_RE = re.compile(r'href="([^"]+\.(?:zip|bin))"', re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode("utf-8", "replace")


def flat(fragment):
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", fragment).strip()


def show_index():
    print("=" * 60)
    print("INDEX: " + INDEX)
    print("=" * 60)
    try:
        html = fetch(INDEX)
    except Exception as err:
        print("fetch failed: " + str(err))
        return

    print("bytes: " + str(len(html)))

    links = re.findall(r'href="([^"]*/download[s]?/[^"]*)"', html)
    seen = []
    for link in links:
        if link not in seen:
            seen.append(link)

    firmware = [l for l in seen if "firmware" in l.lower()]
    print("total /download links: " + str(len(seen)))
    print("with 'firmware' in the url: " + str(len(firmware)))
    print("")
    for link in firmware:
        print("  FW  " + link)
    print("")
    others = [l for l in seen if l not in firmware][:25]
    print("other /download links (first 25):")
    for link in others:
        print("  --  " + link)

    if not seen:
        print("")
        print("No /download links in the HTML. The index is probably")
        print("JavaScript-rendered, so slugs must come from elsewhere.")


def show_page(url):
    print("")
    print("=" * 60)
    print("PAGE: " + url)
    print("=" * 60)
    try:
        html = fetch(url)
    except Exception as err:
        print("fetch failed: " + str(err))
        return

    print("bytes: " + str(len(html)))

    heads = re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    print("h1: " + (flat(heads[0]) if heads else "(none)"))

    text = flat(html)

    versions = VERSION_RE.findall(text)
    dates = DATE_RE.findall(text)
    sizes = SIZE_RE.findall(text)
    print("versions seen: " + str(len(versions)) + " -> " + str(versions[:6]))
    print("dates seen:    " + str(len(dates)) + " -> "
          + str(["/".join(d) for d in dates[:6]]))
    print("sizes seen:    " + str(len(sizes)) + " -> " + str(sizes[:4]))

    zips = ZIP_RE.findall(html)
    print("zip/bin hrefs: " + str(len(zips)))
    for href in zips[:3]:
        print("  " + href[:110])
    if not zips:
        print("  none in the HTML (RED may gate the file behind a login)")

    login = text.lower().count("login")
    print("the word 'login' appears " + str(login) + " times")

    first = VERSION_RE.search(text)
    if first:
        window = text[first.start():first.start() + 320]
        print("")
        print("first version block, as text:")
        print("  " + window)


def main():
    show_index()
    for url in KNOWN:
        show_page(url)
    print("")
    print("Nothing was written. Paste this output.")


if __name__ == "__main__":
    main()
