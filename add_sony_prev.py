#!/usr/bin/env python3
"""Patcher: capture previous firmware versions from Sony EN pages.

sony_english.py currently only takes entries[0] (the newest firmware).
This patch makes it capture up to 5 previous versions with their
changelogs, storing them as previous_versions on each row.

Also patches build_feed.py to pass previous_versions through
english_extras() into the feed.

Safe to run twice.
"""
import ast, shutil, sys

# ---- 1. Patch sony_english.py ----
TARGET1 = "sony_english.py"
with open(TARGET1) as f:
    orig1 = f.read()

try:
    ast.parse(orig1)
except SyntaxError as e:
    print("sony_english.py has a syntax error: %s" % e)
    sys.exit(1)

if "previous_versions" in orig1:
    print("sony_english.py already patched, skipping.")
    patched1 = None
else:
    # Find where the main row is built, after the primary entry processing.
    # Add previous version scraping after the main row is appended to results.
    ANCHOR1 = '        results.append(row)'

    # We insert code before results.append that scrapes previous versions
    INSERT1 = '''        # ---- Previous versions (up to 5) ----
        prev = []
        for prev_entry in entries[1:6]:
            pv = {"v": None, "d": None, "cl": [], "dl": None}
            # Extract version from title
            pv_ver = re.search(r"(?:Ver\\.?\\s*|V)([0-9]+(?:\\.[0-9]+)+)", prev_entry["title"])
            if pv_ver:
                pv["v"] = "V" + pv_ver.group(1)
            try:
                prev_page = fetch(prev_entry["url"], tries=1)
                prev_info = file_info(flat(prev_page))
                if prev_info.get("version"):
                    pv["v"] = prev_info["version"]
                if prev_info.get("release_date"):
                    pv["d"] = prev_info["release_date"]
                prev_cl, _ = split_sections(blocks(prev_page))
                pv["cl"] = prev_cl[:10]
                prev_dl = DOWNLOAD_RE.search(prev_page) if "DOWNLOAD_RE" in dir() else None
                if prev_dl:
                    pv["dl"] = prev_dl.group(1)
            except Exception:
                pass
            if pv["v"]:
                prev.append(pv)
            time.sleep(0.5)
        row["previous_versions"] = prev

        results.append(row)'''

    if ANCHOR1 not in orig1:
        print("Cannot find results.append anchor in sony_english.py")
        sys.exit(1)

    patched1 = orig1.replace(ANCHOR1, INSERT1, 1)

    # Also add previous versions count to the print output
    OLD_PRINT = '        print("  Install sections: " + str(len(install)))'
    NEW_PRINT = ('        print("  Install sections: " + str(len(install)))\n'
                 '        print("  Previous versions: " + str(len(prev)))')
    patched1 = patched1.replace(OLD_PRINT, NEW_PRINT, 1)

    # Fix the DOWNLOAD_RE reference to not use dir()
    patched1 = patched1.replace(
        'prev_dl = DOWNLOAD_RE.search(prev_page) if "DOWNLOAD_RE" in dir() else None',
        'try:\n                    prev_dl = DOWNLOAD_RE.search(prev_page)\n                except NameError:\n                    prev_dl = None'
    )

    try:
        ast.parse(patched1)
    except SyntaxError as e:
        print("Patched sony_english.py has a syntax error: %s" % e)
        sys.exit(1)

    shutil.copy2(TARGET1, TARGET1 + ".bak")
    with open(TARGET1, "w") as f:
        f.write(patched1)
    print("Patched sony_english.py")

# ---- 2. Patch build_feed.py ----
TARGET2 = "build_feed.py"
with open(TARGET2) as f:
    orig2 = f.read()

try:
    ast.parse(orig2)
except SyntaxError as e:
    print("build_feed.py has a syntax error: %s" % e)
    sys.exit(1)

if "previous_versions" in orig2:
    print("build_feed.py already has previous_versions, skipping.")
else:
    # Add previous_versions to english_extras return
    OLD_EXTRAS = '    if row.get("firmware_url"):\n        extras["firmware_url"] = row["firmware_url"]\n        extras["firmware_kind"] = "file"\n    return extras'
    NEW_EXTRAS = ('    if row.get("firmware_url"):\n'
                  '        extras["firmware_url"] = row["firmware_url"]\n'
                  '        extras["firmware_kind"] = "file"\n'
                  '    if row.get("previous_versions"):\n'
                  '        extras["previous_versions"] = row["previous_versions"]\n'
                  '    return extras')

    if OLD_EXTRAS in orig2:
        patched2 = orig2.replace(OLD_EXTRAS, NEW_EXTRAS, 1)
        try:
            ast.parse(patched2)
        except SyntaxError as e:
            print("Patched build_feed.py has a syntax error: %s" % e)
            sys.exit(1)
        shutil.copy2(TARGET2, TARGET2 + ".bak")
        with open(TARGET2, "w") as f:
            f.write(patched2)
        print("Patched build_feed.py")
    else:
        print("Cannot find english_extras return anchor in build_feed.py")

print()
print("Next steps:")
print("  1. python3 add_prev_versions.py   (UI patcher)")
print("  2. python3 sony_english.py        (re-scrape with prev versions)")
print("  3. python3 build_feed.py && python3 build_site.py")
