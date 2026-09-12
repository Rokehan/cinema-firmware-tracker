"""Add the legacy Sony bodies to the English scraper.

The remaining cameras without instructions are the older Sony line: VENICE,
FX9, FS7 II, PXW-FS7, PXW-FS5, PMW-F55, PMW-F5 and FR7. They have English
pages on sony.com like the rest, so they only need entries in MODELS plus a
name alias so build_feed.py can join them onto the feed rows.

Paths are candidates: Sony files these under several family folders and a
wrong one answers 500, so each model lists alternatives and the scraper
reports any that find nothing.

Patches sony_english.py and build_feed.py. Writes a .bak for each.

Run once:  python3 add_legacy_sony.py
"""

import ast
import shutil

NEW_ENTRIES = '''    "VENICE": [CINE + "mpc-3610/downloads", CINE + "venice/downloads"],
    "FX9": [CAMC + "pxw-fx9/downloads", ILME + "pxw-fx9/downloads"],
    "FR7": [CAMC + "ilme-fr7/downloads", ILME + "ilme-fr7/downloads"],
    "FS7 II": [CAMC + "pxw-fs7m2/downloads", CAMC + "pxw-fs7m2k/downloads"],
    "PXW-FS7": [CAMC + "pxw-fs7/downloads", CAMC + "pxw-fs7k/downloads"],
    "PXW-FS5": [CAMC + "pxw-fs5/downloads", CAMC + "pxw-fs5k/downloads"],
    "PMW-F55": [CINE + "pmw-f55/downloads", CAMC + "pmw-f55/downloads"],
    "PMW-F5": [CINE + "pmw-f5/downloads", CAMC + "pmw-f5/downloads"],
'''

MODELS_ANCHOR = '''    "a7 V": [ALPHA + "ilce-7m5/downloads"],'''

ALIAS_ANCHOR = '''EN_ALIASES = {
    "FX3(ILME-FX3)": "FX3",'''

ALIAS_NEW = '''EN_ALIASES = {
    "FX3(ILME-FX3)": "FX3",
    "PXW-FX9": "FX9",
    "PXW-FS7 II": "FS7 II",
    "FS7 II": "FS7 II",'''


def patch(path, steps, guard):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    if guard in text:
        print(path + ": already patched")
        return True

    for old, new, label in steps:
        if old not in text:
            print(path + ": could not find " + label)
            return False
        text = text.replace(old, new, 1)

    try:
        ast.parse(text)
    except SyntaxError as err:
        print(path + ": refusing to write, would not parse")
        print("  line " + str(err.lineno) + ": " + str(err.msg))
        return False

    shutil.copyfile(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(path + ": patched")
    return True


def main():
    ok = True

    ok = patch("sony_english.py", [
        (MODELS_ANCHOR, NEW_ENTRIES + MODELS_ANCHOR, "the MODELS block"),
    ], '"PMW-F55"') and ok

    ok = patch("build_feed.py", [
        (ALIAS_ANCHOR, ALIAS_NEW, "the alias map"),
    ], '"PXW-FX9": "FX9"') and ok

    print("")
    if ok:
        print("Next: python3 sony_english.py && python3 build_feed.py"
              " && python3 build_site.py")
        print("")
        print("Expect some models to report nothing found. Paste the output")
        print("and the paths get corrected, same as the FX line did.")


if __name__ == "__main__":
    main()
