"""Attach Sony's English changelogs and install steps to the feed.

sony_english.py writes sony_english.json keyed by product name. This patches
build_feed.py to join it onto the Sony rows, filling in:

  changelog       Sony's own "Benefits and Improvements" lines
  install         install steps grouped under Sony's own headings
  install_version the version those steps were published for
  guides          linked PDFs where Sony publishes steps only as a document

The Japanese pages stay the authority for version, date and file URL, since
they have consistently been ahead. The English data is additive: when the
English version differs, install_version records what Sony's steps describe
so the site can say so rather than implying they match.

Writes build_feed.py.bak. Refuses to save if the result does not parse.

Run once:  python3 use_sony_english.py
"""

import ast
import shutil

TARGET = "build_feed.py"

LOADER = '''EN_DETAILS = {}
try:
    with open("sony_english.json") as f:
        for row in json.load(f):
            EN_DETAILS[row["product"]] = row
except FileNotFoundError:
    pass


# feed product name -> sony_english.json key. Explicit, because loose
# matching once gave the FX3A the FX3's changelog: they are separate bodies
# on separate firmware tracks.
EN_ALIASES = {
    "FX3(ILME-FX3)": "FX3",
    "FX3 (ILME-FX3)": "FX3",
    "\u03b17 V (ILCE-7M5)": "a7 V",
    "\u03b17 IV (ILCE-7M4)": "a7 IV",
    "\u03b17R V (ILCE-7RM5)": "a7R V",
    "\u03b17S III (ILCE-7SM3)": "a7S III",
}


def english_extras(product):
    """Sony's English changelog and install steps for this body, if any.

    Only an exact name or a declared alias counts. An unmatched body gets
    nothing rather than a neighbour's instructions.
    """
    row = EN_DETAILS.get(product)
    if row is None:
        alias = EN_ALIASES.get(product)
        if alias:
            row = EN_DETAILS.get(alias)
    if row is None:
        return {}
    return {
        "changelog": row.get("changelog") or [],
        "install": row.get("install") or [],
        "file_name": row.get("file_name"),
        "install_version": row.get("version"),
        "install_source": row.get("source_url"),
        "guides": row.get("guides") or [],
    }

'''

ANCHOR = "feed = []"

OLD_SONY = '''            "notes_url": row.get("notes_url"),
            "archive_url": None,
        })'''
NEW_SONY = '''            "notes_url": row.get("notes_url"),
            "archive_url": None,
            **english_extras(row["product"]),
        })'''

OLD_ALPHA = '''                "features": row.get("features") or [],
                "file_size": row.get("file_size"),
            })
except FileNotFoundError:
    print("sony_alpha.json not found, skipping Sony Alpha bodies")'''
NEW_ALPHA = '''                "features": row.get("features") or [],
                "file_size": row.get("file_size"),
                **english_extras(row["product"]),
            })
except FileNotFoundError:
    print("sony_alpha.json not found, skipping Sony Alpha bodies")'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "english_extras" in text:
        print("Already patched. Nothing to do.")
        return

    if ANCHOR not in text:
        print("Could not find the feed list in " + TARGET)
        return
    text = text.replace(ANCHOR, LOADER + ANCHOR, 1)

    if OLD_SONY not in text:
        print("Could not find the Sony index row.")
        return
    text = text.replace(OLD_SONY, NEW_SONY, 1)

    if OLD_ALPHA in text:
        text = text.replace(OLD_ALPHA, NEW_ALPHA, 1)
    else:
        print("Note: Alpha section not joined (pattern not found).")

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
    print("Next: python3 build_feed.py")


if __name__ == "__main__":
    main()
