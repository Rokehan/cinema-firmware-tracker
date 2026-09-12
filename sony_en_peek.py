"""Read-only look at Sony's English (sony.com) firmware pages.

Goal: confirm the page structure is consistent enough to parse before any
scraper is written. Checks, per model:

  1. the model's downloads page -> does it link a "System Software (Firmware)
     Update" page in plain HTML?
  2. that firmware page -> File Info (name/version/size/date), the
     "Benefits and Improvements" changelog, and the instruction headings.

Writes nothing and downloads no firmware.

Run:  python3 sony_en_peek.py
"""

import re
import urllib.request

SITE = "https://www.sony.com"

# Each model's English downloads page. Paths differ by product family, so
# they are listed rather than guessed.
MODELS = [
    ("FX6", "/electronics/support/interchangeable-lens-camcorders-ilme-series/ilme-fx6v/downloads"),
    ("FX3", "/electronics/support/interchangeable-lens-camcorders-ilme-series/ilme-fx3/downloads"),
    ("FX30", "/electronics/support/interchangeable-lens-camcorders-ilme-series/ilme-fx30/downloads"),
    ("a7 IV", "/electronics/support/e-mount-body-ilce-7-series/ilce-7m4/downloads"),
    ("a7R V", "/electronics/support/e-mount-body-ilce-7-series/ilce-7rm5/downloads"),
    ("a7S III", "/electronics/support/e-mount-body-ilce-7-series/ilce-7sm3/downloads"),
]

# A known-good firmware page, as a control.
CONTROL = "/electronics/support/software/00259043"

FW_LINK_RE = re.compile(
    r'href="([^"]*/support/software/\d+)"[^>]*>((?:(?!</a>).){0,220})</a>',
    re.I | re.S,
)

HEADING_RE = re.compile(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>")

FIELD_RE = {
    "name": re.compile(r"Name:\s*([A-Za-z0-9._-]+)", re.I),
    "version": re.compile(r"Version:\s*([0-9][0-9.]*)", re.I),
    "size": re.compile(r"Size:\s*([0-9][0-9 ,]*)\s*bytes", re.I),
    "date": re.compile(r"Release Date:\s*([0-9]{2}-[0-9]{2}-[0-9]{4})", re.I),
}

WANTED_SECTIONS = (
    "benefits and improvements",
    "file info",
    "software update preparation",
    "notes about updating",
    "saving the",
    "updating the system software",
    "check the system software version",
    "step 1",
    "step 2",
    "before you start",
)


# sony.com refuses requests without a full browser header set (403).
BROWSER = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/127.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="127", "Not)A;Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Connection": "keep-alive",
}


def fetch(url):
    req = urllib.request.Request(url, headers=dict(BROWSER))
    body = urllib.request.urlopen(req, timeout=45).read()
    body = body.decode("utf-8", "replace")
    # Content arrives as escaped JSON, e.g. Version:<\/b> 6.01
    return body.replace("\\/", "/").replace("\\u002F", "/")


def flat(fragment):
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    fragment = fragment.replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\s+", " ", fragment).strip()


def show_firmware_page(label, url):
    print("  PAGE " + url)
    try:
        html = fetch(url)
    except Exception as err:
        print("    fetch failed: " + str(err))
        return

    print("    bytes: " + str(len(html)))
    text = flat(html)

    for field, pattern in FIELD_RE.items():
        hit = pattern.search(text)
        print("    " + field.ljust(8) + ": "
              + (hit.group(1) if hit else "NOT FOUND"))

    heads = []
    for level, raw in HEADING_RE.findall(html):
        title = flat(raw)
        if title and title not in heads:
            heads.append("h" + level + " " + title)
    print("    headings: " + str(len(heads)))
    for head in heads[:22]:
        mark = "  *" if any(w in head.lower() for w in WANTED_SECTIONS) else "   "
        print("     " + mark + " " + head[:78])

    lists = re.findall(r"(?is)<(ol|ul)[^>]*>(.*?)</\1>", html)
    numbered = 0
    for kind, body in lists:
        items = re.findall(r"(?is)<li[^>]*>(.*?)</li>", body)
        if kind.lower() == "ol" and len(items) >= 3:
            numbered += 1
    print("    ordered lists with 3+ steps: " + str(numbered))

    step_hit = re.search(r"(?is)Insert the (?:SDXC|memory)[^<]{0,120}", text)
    if step_hit:
        print("    slot line: " + flat(step_hit.group(0))[:100])


def main():
    print("CONTROL PAGE")
    print("=" * 68)
    show_firmware_page("control", SITE + CONTROL)
    print("")

    for label, path in MODELS:
        print("=" * 68)
        print(label + "  " + path)
        print("=" * 68)
        try:
            listing = fetch(SITE + path)
        except Exception as err:
            print("  downloads page failed: " + str(err))
            print("")
            continue

        print("  bytes: " + str(len(listing)))
        hits = []
        for href, raw in FW_LINK_RE.findall(listing):
            title = flat(raw)
            if "system software" not in title.lower():
                continue
            if "firmware" not in title.lower():
                continue
            full = href if href.startswith("http") else SITE + href
            if (full, title) not in hits:
                hits.append((full, title))

        print("  firmware links found: " + str(len(hits)))
        for full, title in hits[:3]:
            print("   - " + title[:84])
            print("     " + full)

        if hits:
            show_firmware_page(label, hits[0][0])
        else:
            print("  no plain-HTML firmware link (page may be JS-rendered)")
        print("")

    print("Nothing was written. Paste this output.")


if __name__ == "__main__":
    main()
