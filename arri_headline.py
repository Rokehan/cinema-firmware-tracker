"""Diagnostic: show what each ARRI camera page says in its own headline.

Reads the slug list from arri_cameras.json and prints, per page, the <h1>
text and the first few hundred characters of visible text after it. That is
where ARRI states the real version and release date, e.g.

    ALEXA Mini SUP 6.1.2
    February 7, 2022

Nothing is written. Read-only.

Run:  python3 arri_headline.py
"""

import json
import re
import urllib.request

BASE = "https://www.arri.com/en/technical-service/firmware/"
BASE = BASE + "software-and-firmware-updates-for-cameras/"

MONTHS = ("January|February|March|April|May|June|July|August|"
          "September|October|November|December")

LONG_DATE = re.compile(r"(" + MONTHS + r")\s+(\d{1,2})(?:st|nd|rd|th)?,\s+(\d{4})")
VERSION = re.compile(r"SUP\s+(\d+(?:\.\d+)*)")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode("utf-8", "replace")


def strip_tags(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", html).strip()


def slugs():
    with open("arri_cameras.json", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("cameras", list(data.values()))
    out = []
    for item in data:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for key in ("slug", "page", "id", "url"):
                if item.get(key):
                    out.append(str(item[key]).rstrip("/").split("/")[-1])
                    break
    return out


def main():
    found = slugs()
    print("Slugs in arri_cameras.json: " + str(len(found)))
    print("")
    for slug in found:
        print("=== " + slug)
        try:
            html = fetch(BASE + slug)
        except Exception as err:
            print("  fetch failed: " + str(err))
            print("")
            continue

        h1s = re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", html)
        h1 = strip_tags(h1s[0]) if h1s else ""
        print("  h1:      " + (h1 if h1 else "(no h1 found)"))

        after = ""
        if h1s:
            cut = html.split(h1s[0], 1)
            if len(cut) > 1:
                after = strip_tags(cut[1])[:220]
        print("  after:   " + (after if after else "(nothing after h1)"))

        vm = VERSION.search(h1) or VERSION.search(after)
        dm = LONG_DATE.search(h1 + " " + after)
        print("  version: " + (("SUP " + vm.group(1)) if vm else "NOT FOUND"))
        print("  date:    " + (dm.group(0) if dm else "NOT FOUND"))
        print("")


if __name__ == "__main__":
    main()
