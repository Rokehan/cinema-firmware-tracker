"""Inspect the JSON that sony.com bakes into its downloads pages.

The downloads pages carry window.__PRELOADED_STATE__.downloads with a
searchResults array listing every download for that model. That is a far
better discovery source than the HTML.

This prints the field names of a result, the entries that look like body
firmware, and then the section headings of one Alpha firmware page, to check
they match the FX page's headings.

Writes nothing. Read-only.

Run:  python3 sony_en_json.py
"""

import json
import re
import time
import urllib.request

SITE = "https://www.sony.com"

PAGES = [
    ("a7 IV", "/electronics/support/e-mount-body-ilce-7-series/ilce-7m4/downloads"),
    ("FX6", "/electronics/support/interchangeable-lens-camcorders-ilme-series/ilme-fx6v/downloads"),
]

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

HEADING_RE = re.compile(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>")


def fetch(url, tries=3):
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers=dict(BROWSER))
            return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")
        except Exception as err:
            last = err
            print("    attempt " + str(attempt) + ": " + str(err))
            time.sleep(3)
    raise last


def flat(fragment):
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", fragment).strip()


def preloaded(html):
    """The downloads slice of window.__PRELOADED_STATE__, as a dict."""
    marker = "__PRELOADED_STATE__.downloads"
    start = html.find(marker)
    if start < 0:
        return None
    start = html.find("{", start)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(html)):
        char = html[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except Exception as err:
                    print("    json parse failed: " + str(err))
                    return None
    return None


def main():
    for label, path in PAGES:
        print("=" * 68)
        print(label)
        print("=" * 68)
        try:
            html = fetch(SITE + path)
        except Exception as err:
            print("  gave up: " + str(err))
            print("")
            continue

        data = preloaded(html)
        if not data:
            print("  no __PRELOADED_STATE__.downloads found")
            print("")
            continue

        results = (data.get("searchResults") or {}).get("results") or []
        print("  results: " + str(len(results)))
        if results:
            print("  fields on a result: " + str(sorted(results[0].keys())))
            print("")
            print("  first result, in full:")
            print("   " + json.dumps(results[0], indent=1)[:700].replace(chr(10), chr(10) + "   "))
            print("")

        firmware = []
        for item in results:
            blob = json.dumps(item).lower()
            if "system software" in blob or "firmware" in blob:
                firmware.append(item)
        print("  firmware-looking results: " + str(len(firmware)))
        for item in firmware[:4]:
            title = item.get("title") or item.get("name") or item.get("headline")
            url = item.get("url") or item.get("uri") or item.get("link")
            print("   - " + str(title)[:82])
            print("     " + str(url)[:96])
            for key in ("releaseDate", "date", "type", "category", "os"):
                if item.get(key):
                    print("     " + key + ": " + str(item[key])[:60])
        print("")

        if firmware and label.startswith("a7"):
            url = firmware[0].get("url") or ""
            if url and not url.startswith("http"):
                url = SITE + url
            if url:
                print("  ALPHA FIRMWARE PAGE: " + url)
                try:
                    page = fetch(url)
                except Exception as err:
                    print("    fetch failed: " + str(err))
                else:
                    page = page.replace("\\/", "/")
                    heads = []
                    for level, raw in HEADING_RE.findall(page):
                        title = flat(raw)
                        if title and title not in heads:
                            heads.append("h" + level + " " + title)
                    print("    unique headings: " + str(len(heads)))
                    for head in heads[:26]:
                        print("      " + head[:76])
                    text = flat(page)
                    for field, pattern in (
                        ("name", r"Name:\s*([A-Za-z0-9._-]+)"),
                        ("version", r"Version:\s*([0-9][0-9.]*)"),
                        ("size", r"Size:\s*([0-9][0-9 ,]*)\s*bytes"),
                        ("date", r"Release Date:\s*([0-9]{2}-[0-9]{2}-[0-9]{4})"),
                    ):
                        hit = re.search(pattern, text, re.I)
                        print("    " + field.ljust(8) + ": "
                              + (hit.group(1) if hit else "NOT FOUND"))
        print("")

    print("Nothing was written. Paste this output.")


if __name__ == "__main__":
    main()
