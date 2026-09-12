"""Accept Sony's cinema-camera firmware titles, and retry harder.

Two problems from the last run:

  1. VENICE 2 fetched fine but nothing matched. The filter required
     "system software" in the title, and the cinema bodies title theirs
     "Firmware: VENICE 2 (MPC-3628 MPC-3626) V5.00" or "Firmware:MPC-2610
     V2.10". Now any entry Sony tags downloadType=Firmware counts, with
     apps still excluded by that tag.
  2. BURANO returned HTTP 500 twice on a path that is correct
     (professional-cameras-digital-cinema-cameras/mpc-2610). Sony throws
     intermittent 500s, so fetch waits longer between attempts.

Also picks the newest entry rather than the first, since the cinema pages
list every historical firmware.

Patches sony_english.py. Writes a .bak, refuses to save if it will not parse.

Run once:  python3 fix_en_titles.py
"""

import ast
import shutil

TARGET = "sony_english.py"

OLD_FILTER = '''    out = []
    for item in results:
        if str(item.get("downloadType", "")).lower() != "firmware":
            continue
        title = str(item.get("title") or "")
        if "system software" not in title.lower():
            continue
        url = item.get("url") or ""
        if url and not url.startswith("http"):
            url = SITE + url
        if not url:
            continue
        out.append({"title": title, "url": url})
    return out'''

NEW_FILTER = '''    out = []
    for item in results:
        # Sony's own downloadType tag is the reliable filter. Titles vary:
        # "ILME-FX6 System Software (Firmware) Update Ver. 6.00" for the
        # hybrid bodies, "Firmware: VENICE 2 (MPC-3628 MPC-3626) V5.00" or
        # "Firmware:MPC-2610 V2.10" for the cinema bodies.
        if str(item.get("downloadType", "")).lower() != "firmware":
            continue
        title = str(item.get("title") or "")
        low = title.lower()
        if "system software" not in low and "firmware" not in low:
            continue
        url = item.get("url") or ""
        if url and not url.startswith("http"):
            url = SITE + url
        if not url:
            continue
        out.append({
            "title": title,
            "url": url,
            "published": str(item.get("publicationDate") or ""),
            "index": item.get("index", 0),
        })

    # The cinema pages list every historical release, so prefer the newest
    # version number and fall back to Sony's own ordering.
    def version_key(entry):
        import re as _re
        hit = _re.findall(r"(?:Ver\\.?\\s*|V)([0-9]+(?:\\.[0-9]+)+)", entry["title"])
        if not hit:
            return (0,)
        return tuple(int(part) for part in hit[-1].split("."))

    out.sort(key=lambda e: (version_key(e), -e["index"]), reverse=True)
    return out'''

OLD_FETCH = '''def fetch(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict(BROWSER))
            body = urllib.request.urlopen(req, timeout=90).read()
            body = body.decode("utf-8", "replace")
            return body.replace("\\\\/", "/").replace("\\\\u002F", "/")
        except Exception as err:
            last = err
            time.sleep(3)
    raise last'''

NEW_FETCH = '''def fetch(url, tries=3):
    """Fetch with retries. sony.com throws intermittent 500s."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict(BROWSER))
            body = urllib.request.urlopen(req, timeout=90).read()
            body = body.decode("utf-8", "replace")
            return body.replace("\\\\/", "/").replace("\\\\u002F", "/")
        except Exception as err:
            last = err
            time.sleep(4 + attempt * 4)
    raise last'''

OLD_TRIES = '                listing = fetch(SITE + candidate, tries=2)'
NEW_TRIES = '                listing = fetch(SITE + candidate, tries=3)'


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "Sony's own downloadType tag is the reliable filter" in text:
        print("Already patched. Nothing to do.")
        return

    steps = (
        (OLD_FILTER, NEW_FILTER, "firmware_entries filter"),
        (OLD_FETCH, NEW_FETCH, "fetch backoff"),
        (OLD_TRIES, NEW_TRIES, "candidate retries"),
    )

    for old, new, label in steps:
        if old not in text:
            print("Could not find the " + label + " in " + TARGET)
            print("Nothing written.")
            return
        text = text.replace(old, new, 1)

    try:
        ast.parse(text)
    except SyntaxError as err:
        print("Refusing to write: result would not parse.")
        print("  line " + str(err.lineno) + ": " + str(err.msg))
        return

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Patched " + TARGET + " (backup: " + TARGET + ".bak)")
    print("Next: python3 sony_english.py")


if __name__ == "__main__":
    main()
