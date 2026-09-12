"""Merge the Sony Alpha bodies into feed.json.

Adds a section to build_feed.py that reads sony_alpha.json, the same way the
ARRI, Sony index and RED sections read theirs. sony_alpha.py already writes
feed-shaped rows.

Tolerates the file not existing yet, like the other optional inputs.

Writes build_feed.py.bak. Refuses to save if the result does not parse.

Run once:  python3 use_sony_alpha.py
"""

import ast
import shutil

TARGET = "build_feed.py"

SECTION = '''# ---- Sony Alpha bodies ----
# Stills-hybrid bodies that get used on cinema jobs. sony_alpha.py writes
# feed-shaped rows, including the real BODYDATA.DAT file URL where Sony
# publishes one.
try:
    with open("sony_alpha.json") as f:
        for row in json.load(f):
            feed.append({
                "manufacturer": "Sony",
                "product": row["product"],
                "version": row["version"],
                "release_date": row["release_date"],
                "release_precision": row.get("release_precision") or "day",
                "status": row["status"],
                "source_url": row["source_url"],
                "firmware_url": row.get("firmware_url"),
                "firmware_kind": row.get("firmware_kind") or "file",
                "notes_url": row.get("notes_url"),
                "archive_url": None,
                "summary": row.get("summary"),
                "features": row.get("features") or [],
                "file_size": row.get("file_size"),
            })
except FileNotFoundError:
    print("sony_alpha.json not found, skipping Sony Alpha bodies")

'''

SORT_LINE = 'feed.sort(key=lambda r: (r["release_date"] or ""), reverse=True)'


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "sony_alpha.json" in text:
        print("Already merged. Nothing to do.")
        return

    if SORT_LINE not in text:
        print("Could not find the feed.sort line in " + TARGET)
        print("Nothing written.")
        return

    text = text.replace(SORT_LINE, SECTION + SORT_LINE, 1)

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
    print("Next: python3 sony_alpha.py && python3 build_feed.py")


if __name__ == "__main__":
    main()
