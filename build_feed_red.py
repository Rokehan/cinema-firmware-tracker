"""Merge RED into feed.json.

Adds a RED section to build_feed.py, reading red_cameras.json the same way
the ARRI and Sony sections read theirs. RED already emits feed-shaped rows,
so the section is a straight copy with the keys build_feed.py uses.

Also sets firmware_kind on ARRI rows (they had none, so the site had to
guess) and tolerates red_cameras.json not existing yet, matching how
sony_fx.json and arri_details.json are handled.

Writes build_feed.py.bak. Refuses to save if the result does not parse.

Run once:  python3 build_feed_red.py
"""

import ast
import shutil

TARGET = "build_feed.py"

RED_SECTION = '''# ---- RED ----
# red_cameras.py already writes feed-shaped rows. RED gates the file behind
# a login, so firmware_url points at RED's own page, not a direct download.
try:
    with open("red_cameras.json") as f:
        for row in json.load(f):
            feed.append({
                "manufacturer": "RED",
                "product": row["product"],
                "version": row["version"],
                "release_date": row["release_date"],
                "release_precision": row.get("release_precision") or "day",
                "status": row["status"],
                "source_url": row["source_url"],
                "firmware_url": row.get("firmware_url"),
                "firmware_kind": row.get("firmware_kind") or "page",
                "notes_url": row.get("notes_url"),
                "archive_url": None,
                "summary": row.get("summary"),
                "features": row.get("features") or [],
            })
except FileNotFoundError:
    print("red_cameras.json not found, skipping RED")

'''

SORT_LINE = 'feed.sort(key=lambda r: (r["release_date"] or ""), reverse=True)'

ARRI_OLD = '''            "firmware_url": row.get("firmware_download"),'''
ARRI_NEW = '''            "firmware_url": row.get("firmware_download"),
            "firmware_kind": "file",'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "red_cameras.json" in text:
        print("RED is already merged. Nothing to do.")
        return

    if SORT_LINE not in text:
        print("Could not find the feed.sort line in " + TARGET)
        print("Nothing written.")
        return

    text = text.replace(SORT_LINE, RED_SECTION + SORT_LINE, 1)

    if ARRI_OLD in text and '"firmware_kind": "file"' not in text.split("# ---- Sony")[0]:
        text = text.replace(ARRI_OLD, ARRI_NEW, 1)
        print("Also set firmware_kind on ARRI rows.")

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
