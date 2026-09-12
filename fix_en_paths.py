"""Correct the sony.com download paths and try alternates.

Four models returned HTTP 500 because Sony files products under different
family folders than guessed. Confirmed paths:

  FX30      camcorders-and-video-cameras-interchangeable-lens-camcorders
  VENICE 2  professional-cameras-digital-cinema-cameras/mpc-3628

Sony is inconsistent about which family folder a model lives in (FX3 sits
under two different ones), so MODELS now holds a list of candidate paths per
model and the scraper tries each until one answers with firmware entries.

Patches sony_english.py. Writes a .bak, refuses to save if it will not parse.

Run once:  python3 fix_en_paths.py
"""

import ast
import re
import shutil

TARGET = "sony_english.py"

ILME = "/electronics/support/interchangeable-lens-camcorders-ilme-series/"
CAMC = ("/electronics/support/camcorders-and-video-cameras-"
        "interchangeable-lens-camcorders/")
CINE = "/electronics/support/professional-cameras-digital-cinema-cameras/"
ALPHA = "/electronics/support/e-mount-body-ilce-7-series/"

NEW_MODELS = '''# model key -> candidate download paths, tried in order. The key matches the
# product name used in feed.json so build_feed.py can join the two.
# Sony files the same kind of camera under different family folders, and a
# wrong folder returns HTTP 500, so each model lists its alternatives.
ILME = "/electronics/support/interchangeable-lens-camcorders-ilme-series/"
CAMC = ("/electronics/support/camcorders-and-video-cameras-"
        "interchangeable-lens-camcorders/")
CINE = "/electronics/support/professional-cameras-digital-cinema-cameras/"
ALPHA = "/electronics/support/e-mount-body-ilce-7-series/"

MODELS = {
    "FX6": [ILME + "ilme-fx6v/downloads", CAMC + "ilme-fx6v/downloads"],
    "FX3": [CAMC + "ilme-fx3/downloads", ILME + "ilme-fx3/downloads"],
    "FX30": [CAMC + "ilme-fx30/downloads", ILME + "ilme-fx30/downloads"],
    "FX2": [CAMC + "ilme-fx2/downloads", ILME + "ilme-fx2/downloads"],
    "VENICE 2": [CINE + "mpc-3628/downloads", CINE + "mpc-3626/downloads"],
    "BURANO": [CINE + "mpc-2610/downloads", CINE + "burano/downloads"],
    "a7 V": [ALPHA + "ilce-7m5/downloads"],
    "a7 IV": [ALPHA + "ilce-7m4/downloads"],
    "a7R V": [ALPHA + "ilce-7rm5/downloads"],
    "a7S III": [ALPHA + "ilce-7sm3/downloads"],
}'''

# The cinema bodies use a different page template: no File Info block, and
# the steps live in a multilingual UPDATE GUIDE pdf rather than on the page.
CINEMA_HELPERS = '''
CONTENTS_RE = re.compile(
    r"(?:\\[|<)\\s*Contents of V([0-9.]+)\\s*(?:\\]|>)(.{0,900})", re.I | re.S)
ZIP_RE = re.compile(r'href="([^"]+\\.zip)"', re.I)
GUIDE_RE = re.compile(
    r'href="([^"]+\\.pdf)"[^>]*>((?:(?!</a>).){0,160})</a>', re.I | re.S)
TITLE_VERSION_RE = re.compile(r"V([0-9]+\\.[0-9]+)")


def cinema_details(html, title):
    """Firmware details from the professional-cinema page template.

    These pages state the version in their heading and list changes under
    "[Contents of Vx.xx]". The install steps are published as a separate
    UPDATE GUIDE pdf, so that is linked rather than invented.
    """
    text = flat(html)
    found = {}

    hit = TITLE_VERSION_RE.search(title)
    if hit:
        found["version"] = "V" + hit.group(1)

    changes = []
    block = CONTENTS_RE.search(text)
    if block:
        found.setdefault("version", "V" + block.group(1))
        tail = block.group(2)
        tail = re.split(r"IMPORTANT|Please accept|Downloads", tail)[0]
        for piece in re.split(r"(?:(?<=[a-z.)])\\s+(?=\\d+\\.[A-Z])|\\u2022)", tail):
            line = re.sub(r"^\\s*\\d+\\s*\\.\\s*", "", piece).strip(" .;")
            if 3 < len(line) < 200:
                changes.append(line)
    found["changelog"] = changes[:14]

    zip_hit = ZIP_RE.search(html)
    if zip_hit:
        url = zip_hit.group(1)
        found["firmware_url"] = url if url.startswith("http") else SITE + url

    guides = []
    for href, label in GUIDE_RE.findall(html):
        name = flat(label)
        if "update guide" in name.lower() or "release note" in name.lower():
            url = href if href.startswith("http") else SITE + href
            guides.append({"label": name, "url": url})
    found["guides"] = guides[:3]
    return found

'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "cinema_details" in text:
        print("Already patched. Nothing to do.")
        return

    # 1. replace the MODELS block
    start = text.find("# model key -> downloads path.")
    if start < 0:
        print("Could not find the MODELS block in " + TARGET)
        return
    end = text.find("}", text.find("MODELS = {", start))
    if end < 0:
        print("Could not find the end of MODELS.")
        return
    text = text[:start] + NEW_MODELS + text[end + 1:]

    # 2. add the cinema-template helpers before main()
    anchor = "def main():"
    if anchor not in text:
        print("Could not find main().")
        return
    text = text.replace(anchor, CINEMA_HELPERS.lstrip(chr(10)) + chr(10) + anchor, 1)

    # 3. try each candidate path, and use the cinema parser when File Info
    #    is absent
    old_loop = '''    for product, path in MODELS.items():
        print("=" * 60)
        print(product)
        try:
            listing = fetch(SITE + path)
        except Exception as err:
            print("  downloads page failed: " + str(err))
            print("")
            continue

        entries = firmware_entries(listing)'''
    new_loop = '''    for product, paths in MODELS.items():
        print("=" * 60)
        print(product)
        entries = []
        for candidate in paths:
            try:
                listing = fetch(SITE + candidate, tries=2)
            except Exception as err:
                print("  " + candidate.split("/")[-2] + " path failed: "
                      + str(err)[:44])
                continue
            entries = firmware_entries(listing)
            if entries:
                break
            print("  no firmware listed under "
                  + candidate.split("/support/")[1].split("/")[0])'''
    if old_loop not in text:
        print("Could not find the model loop.")
        return
    text = text.replace(old_loop, new_loop, 1)

    old_info = '''        if "version" not in info:
            hop = latest_hop(page)'''
    new_info = '''        cinema = {}
        if "version" not in info:
            cinema = cinema_details(page, entry["title"])

        if "version" not in info and not cinema.get("version"):
            hop = latest_hop(page)'''
    if old_info not in text:
        print("Could not find the version fallback.")
        return
    text = text.replace(old_info, new_info, 1)

    old_row = '''        changelog, install = split_sections(blocks(page))'''
    new_row = '''        changelog, install = split_sections(blocks(page))
        if cinema.get("version"):
            info.setdefault("version", cinema["version"])
            changelog = changelog or cinema.get("changelog") or []'''
    if old_row not in text:
        print("Could not find the section split call.")
        return
    text = text.replace(old_row, new_row, 1)

    old_dict = '''            "changelog": changelog[:14],
            "install": install,'''
    new_dict = '''            "changelog": changelog[:14],
            "install": install,
            "firmware_url": cinema.get("firmware_url"),
            "guides": cinema.get("guides") or [],'''
    if old_dict not in text:
        print("Could not find the row dict.")
        return
    text = text.replace(old_dict, new_dict, 1)

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
