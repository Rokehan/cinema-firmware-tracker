"""Use the real Sony file URLs in the feed.

sony_files.py adds firmware_url (a BODYDATA.DAT link) to the FX rows in
sony_fx.json. This patches build_feed.py so those rows carry the file as a
real download instead of falling back to the support page.

A row that still has no file URL keeps the old page-style link, so nothing
is claimed that Sony has not published.

Writes build_feed.py.bak. Refuses to save if the result does not parse.

Run once:  python3 use_sony_files.py
"""

import ast
import shutil

TARGET = "build_feed.py"

OLD = '''            "firmware_url": row.get("firmware_url") or (fx["page_url"] if fx else None),
            "firmware_kind": "page" if (fx and not row.get("firmware_url")) else "file",'''

NEW = '''            "firmware_url": row.get("firmware_url") or fx_file
            or (fx["page_url"] if fx else None),
            "firmware_kind": "file"
            if (row.get("firmware_url") or fx_file)
            else ("page" if fx else "file"),
            "file_size": (fx or {}).get("file_size"),'''

OLD_FX = '        fx = FX_OVERRIDE.get(row["product"])'
NEW_FX = '''        fx = FX_OVERRIDE.get(row["product"])
        # sony_files.py resolves the real BODYDATA.DAT URL where Sony
        # publishes one. Absent, the support page stands in as before.
        fx_file = (fx or {}).get("firmware_url")'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "fx_file" in text:
        print("Already patched. Nothing to do.")
        return

    for needle, label in ((OLD, "Sony firmware_url block"), (OLD_FX, "fx lookup line")):
        if needle not in text:
            print("Could not find the " + label + " in " + TARGET)
            print("Nothing written.")
            return

    text = text.replace(OLD_FX, NEW_FX, 1)
    text = text.replace(OLD, NEW, 1)

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
    print("Next: python3 sony_files.py && python3 build_feed.py")


if __name__ == "__main__":
    main()
