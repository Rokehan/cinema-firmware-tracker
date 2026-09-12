#!/usr/bin/env python3
"""Patcher: pass firmware_url from sony_english.json through to feed.

english_extras() now returns firmware_url. Since **english_extras() is
spread last in the Sony feed entries, the EN download URL fills in when
no other source (sony_files.py, sony_fx.py) provides one.

For cameras that already have a direct file URL, we avoid overwriting
it with the EN page URL by only including firmware_url when it's truthy.

Safe to run twice.
"""
import ast, shutil, sys

TARGET = "build_feed.py"
BACKUP = TARGET + ".bak"

with open(TARGET) as f:
    original = f.read()

try:
    ast.parse(original)
except SyntaxError as e:
    print("Original has a syntax error: %s" % e)
    sys.exit(1)

# Add firmware_url to english_extras return dict
OLD = '''        "source_url": row.get("source_url"),
    }'''

NEW = '''        "source_url": row.get("source_url"),
        "firmware_url": row.get("firmware_url"),
        "firmware_kind": "file" if row.get("firmware_url") else None,
    }'''

if '"firmware_url": row.get("firmware_url"),' in original:
    print("Already patched. Nothing to do.")
    sys.exit(0)

if OLD not in original:
    print("Cannot find anchor in %s" % TARGET)
    sys.exit(1)

patched = original.replace(OLD, NEW, 1)

# The **english_extras() spread will set firmware_url and firmware_kind,
# but only when the EN data has a value. None values won't overwrite
# existing truthy values because dict.update replaces unconditionally.
# So we need to filter Nones out of the return dict.
# Replace the return to filter None values.
OLD_RETURN = '''    return {
        "changelog": row.get("changelog") or [],
        "install": row.get("install") or [],
        "file_name": row.get("file_name"),
        "install_version": row.get("version"),
        "install_source": row.get("source_url"),
        "guides": row.get("guides") or [],
        "source_url": row.get("source_url"),
        "firmware_url": row.get("firmware_url"),
        "firmware_kind": "file" if row.get("firmware_url") else None,
    }'''

NEW_RETURN = '''    extras = {
        "changelog": row.get("changelog") or [],
        "install": row.get("install") or [],
        "file_name": row.get("file_name"),
        "install_version": row.get("version"),
        "install_source": row.get("source_url"),
        "guides": row.get("guides") or [],
        "source_url": row.get("source_url"),
    }
    if row.get("firmware_url"):
        extras["firmware_url"] = row["firmware_url"]
        extras["firmware_kind"] = "file"
    return extras'''

patched = patched.replace(OLD_RETURN, NEW_RETURN, 1)

try:
    ast.parse(patched)
except SyntaxError as e:
    print("Patched version has a syntax error: %s" % e)
    sys.exit(1)

shutil.copy2(TARGET, BACKUP)
with open(TARGET, "w") as f:
    f.write(patched)

print("Patched %s (backup: %s)" % (TARGET, BACKUP))
print("Next: python3 build_feed.py && python3 build_site.py")
