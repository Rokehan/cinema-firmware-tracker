"""Find how sony.com links a model's firmware page.

The downloads pages fetch fine (about 710 KB) but the earlier link pattern
matched nothing, so the links are shaped differently than assumed. This
dumps every candidate so the real pattern is visible rather than guessed.

Also retries slow pages, since three FX pages timed out at 45s.

Writes nothing. Read-only.

Run:  python3 sony_en_links.py
"""

import re
import time
import urllib.error
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


def fetch(url, tries=3):
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers=dict(BROWSER))
            body = urllib.request.urlopen(req, timeout=90).read()
            body = body.decode("utf-8", "replace")
            return body.replace("\\/", "/").replace("\\u002F", "/")
        except Exception as err:
            last = err
            print("    attempt " + str(attempt) + " failed: " + str(err))
            time.sleep(3)
    raise last


def flat(fragment):
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", fragment).strip()


def main():
    for label, path in PAGES:
        print("=" * 68)
        print(label + "  " + path)
        print("=" * 68)
        try:
            html = fetch(SITE + path)
        except Exception as err:
            print("  gave up: " + str(err))
            print("")
            continue

        print("  bytes: " + str(len(html)))

        # 1. Any /support/software/<digits> reference at all, however shaped.
        ids = []
        for hit in re.findall(r"/support/software/(\d+)", html):
            if hit not in ids:
                ids.append(hit)
        print("  software ids referenced: " + str(len(ids)) + " -> " + str(ids[:12]))

        # 2. Where does the phrase "System Software" appear, and what is near it?
        spots = [m.start() for m in re.finditer(r"System Software", html)]
        print("  'System Software' occurrences: " + str(len(spots)))
        for start in spots[:4]:
            window = html[max(0, start - 260):start + 200]
            print("   ...  " + " ".join(window.split())[:230])
            print("")

        # 3. Any anchor whose text mentions firmware, whatever the href.
        anchors = re.findall(r"(?is)<a[^>]*>(.{0,160}?)</a>", html)
        named = []
        for raw in anchors:
            text = flat(raw)
            if "firmware" in text.lower() or "system software" in text.lower():
                if text not in named:
                    named.append(text)
        print("  anchors mentioning firmware: " + str(len(named)))
        for text in named[:6]:
            print("   A  " + text[:96])

        # 4. JSON-ish keys that might carry the link.
        keys = []
        for hit in re.findall(r'"(\w{2,24})"\s*:\s*"[^"]*support/software/\d+', html):
            if hit not in keys:
                keys.append(hit)
        print("  json keys holding a software url: " + str(keys[:8]))
        print("")

    print("Nothing was written. Paste this output.")


if __name__ == "__main__":
    main()
