"""Read-only: hunt for the real firmware file URL on Sony support pages.

The FX bodies currently link to their support page because sony_fx.py never
captured a file URL. Sony's pages do have a download button, and the file is
named BODYDATA.DAT, so the URL exists somewhere in the markup.

This prints every candidate link and any script/JSON field that looks like a
file reference, for the four FX pages plus one A7 page as a comparison. It
writes nothing and downloads no firmware.

Run:  python3 sony_dl_peek.py
"""

import re
import urllib.request

PAGES = [
    ("FX6", "https://support.sony.jp/electronics/support/software/00378932"),
    ("FX3", "https://support.sony.jp/electronics/support/software/00378858"),
    ("FX3A", "https://support.sony.jp/electronics/support/software/00378859"),
    ("FX30", "https://support.sony.jp/electronics/support/software/00378860"),
    ("a7 IV (compare)",
     "https://support.sony.jp/electronics/support/e-mount-body-ilce-7-series/ilce-7m4/software/00400195"),
]

FILE_HINTS = ("bodydata", ".dat", ".exe", ".dmg", ".zip", "firmware", "update")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req).read()
    for encoding in ("utf-8", "shift_jis", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def main():
    for label, url in PAGES:
        print("=" * 64)
        print(label + "  " + url)
        print("=" * 64)
        try:
            html = fetch(url)
        except Exception as err:
            print("fetch failed: " + str(err))
            print("")
            continue

        print("bytes: " + str(len(html)))

        hrefs = re.findall(r'href="([^"]+)"', html)
        hits = []
        for href in hrefs:
            low = href.lower()
            if any(hint in low for hint in FILE_HINTS) and href not in hits:
                hits.append(href)
        print("candidate hrefs: " + str(len(hits)))
        for href in hits[:12]:
            print("  H  " + href[:120])

        # Sony often puts the file behind a data attribute or inline JSON.
        others = re.findall(r'["\']([^"\']*(?:BODYDATA|\.DAT|\.dat)[^"\']*)["\']', html)
        seen = []
        for item in others:
            if item not in seen:
                seen.append(item)
        print("strings mentioning BODYDATA/.dat: " + str(len(seen)))
        for item in seen[:10]:
            print("  S  " + item[:120])

        buttons = re.findall(r'(?is)<a[^>]*>(?:(?!</a>).){0,60}(?:ダウンロード|Download)(?:(?!</a>).){0,60}</a>', html)
        print("download-looking anchors: " + str(len(buttons)))
        for tag in buttons[:4]:
            flat = re.sub(r"\s+", " ", tag)
            print("  A  " + flat[:170])

        print("")

    print("Nothing was written. Paste this output.")


if __name__ == "__main__":
    main()
