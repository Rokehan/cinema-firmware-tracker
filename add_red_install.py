"""Capture RED's install instructions and let them reach the site.

RED prints the update procedure on the firmware page itself, under a heading
like "UPGRADE V-RAPTOR FIRMWARE", alongside "IMPORTANT" and "OPERATIONAL
NOTES". Those are quoted verbatim, the same treatment Sony's English pages
get.

Patches three files:
  red_cameras.py  capture the instruction sections per camera
  build_feed.py   carry install / install_version through to feed.json
  build_site.py   allow a bench line with no card slot, since RED cameras
                  have one media bay and never name a slot

Writes a .bak for each. Refuses to save a file that will not parse.

Run once:  python3 add_red_install.py
"""

import ast
import shutil

RED_HELPER = '''
# RED's own section names. SIGNIFICANT CHANGES is the changelog and is
# handled separately; the rest is the update procedure.
INSTALL_HEADS = ("upgrade", "important", "operational notes")
CHANGE_HEAD = "significant changes"


def looks_like_heading(piece):
    letters = [c for c in piece if c.isalpha()]
    if not letters or len(piece) > 70:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) > 0.85


def install_sections(block):
    """RED's update procedure, grouped under RED's own headings."""
    sections = []
    current = None
    for raw in block.split(BREAK.strip()):
        piece = raw.strip().strip("|").strip()
        if not piece:
            continue
        if re.match(r"(?i)copyright|^\\(c\\) 20|^\\u00a9|^&copy;|^login$", piece):
            current = None
            continue
        if looks_like_heading(piece):
            low = piece.lower()
            if low.startswith(CHANGE_HEAD):
                current = None
                continue
            if any(word in low for word in INSTALL_HEADS):
                current = {"heading": piece, "items": []}
                sections.append(current)
            else:
                current = None
            continue
        if current is None:
            continue
        item = re.sub(r"^\\d+\\.\\s*", "", piece).strip()
        item = re.sub(r"^\\d+\\.\\s*", "", item).strip()
        if 3 < len(item) < 420 and item not in current["items"]:
            current["items"].append(item)

    return [s for s in sections if s["items"]]

'''

RED_CALL_OLD = '''    return {
        "version": version,
        "release_date": date,
        "size": size,
        "features": features[:12],
        "history_count": len(blocks),
    }'''

RED_CALL_NEW = '''    return {
        "version": version,
        "release_date": date,
        "size": size,
        "features": features[:12],
        "install": install_sections(block),
        "history_count": len(blocks),
    }'''

RED_ROW_OLD = '''            "features": release["features"],
            "file_size": release["size"],
        })'''

RED_ROW_NEW = '''            "features": release["features"],
            "file_size": release["size"],
            "install": release["install"],
            "install_version": release["version"],
            "install_source": url,
            "file_name": "upgrade.bin",
        })'''

RED_PRINT_OLD = '''        print("  Changes captured: " + str(len(release["features"])))'''
RED_PRINT_NEW = '''        print("  Changes captured: " + str(len(release["features"])))
        print("  Install sections: " + str(len(release["install"])))
        for block in release["install"]:
            print("    [" + block["heading"][:40] + "] "
                  + str(len(block["items"])) + " lines")'''

FEED_OLD = '''                "summary": row.get("summary"),
                "features": row.get("features") or [],
            })
except FileNotFoundError:
    print("red_cameras.json not found, skipping RED")'''

FEED_NEW = '''                "summary": row.get("summary"),
                "features": row.get("features") or [],
                "install": row.get("install") or [],
                "install_version": row.get("install_version"),
                "install_source": row.get("install_source"),
                "file_name": row.get("file_name"),
                "file_size": row.get("file_size"),
            })
except FileNotFoundError:
    print("red_cameras.json not found, skipping RED")'''

SITE_OLD = '''    if not (file_name and slot and menu):
        return None

    return {
        "file": file_name,
        "where": "card root" if ROOT_RE.search(joined) else "card",
        "slot": "slot " + slot,
        "menu": menu,
    }'''

SITE_NEW = '''    # A slot is only quoted when the manufacturer names one. RED bodies
    # have a single media bay and never do, so that step is left out
    # rather than invented.
    if not (file_name and menu):
        return None

    if ROOT_RE.search(joined):
        where = "card root"
    elif TOP_LEVEL_RE.search(joined):
        where = "card top level"
    else:
        where = "card"

    strip = {"file": file_name, "where": where, "menu": menu}
    if slot:
        strip["slot"] = "slot " + slot
    return strip'''

SITE_RE_OLD = '''ROOT_RE = re.compile(r"\\broot directory\\b", re.I)'''
SITE_RE_NEW = '''ROOT_RE = re.compile(r"\\broot directory\\b", re.I)
TOP_LEVEL_RE = re.compile(r"\\btop level directory\\b", re.I)'''

SITE_MENU_OLD = '''MENU_SENTENCE_RE = re.compile(
    r"((?:Version Up|Software Update|Update Camera|Version Number)"
    r"\\s+in the\\s+[A-Za-z ]{2,24}\\s+menu)", re.I)'''
SITE_MENU_NEW = '''MENU_SENTENCE_RE = re.compile(
    r"((?:Version Up|Software Update|Update Camera|Version Number)"
    r"\\s+in the\\s+[A-Za-z ]{2,24}\\s+menu)", re.I)
# RED writes its path as "Go to Menu > Maintenance > Upgrade and select
# Camera Upgrade."
MENU_GOTO_RE = re.compile(
    r"((?:Menu|MENU)\\s*>\\s*[A-Za-z ]{2,20}\\s*>\\s*[A-Za-z ]{2,24})")'''

SITE_MENU_USE_OLD = '''    menu = None
    hit = MENU_PATH_RE.search(joined)
    if hit is None:'''
SITE_MENU_USE_NEW = '''    menu = None
    hit = MENU_PATH_RE.search(joined) or MENU_GOTO_RE.search(joined)
    if hit is None:'''

PANEL_BENCH_OLD = '''      + "<li>" + esc(data.bench.where) + "</li>"
      + "<li>" + esc(data.bench.slot) + "</li>"
      + "<li>" + esc(data.bench.menu) + "</li></ol></div>";'''
PANEL_BENCH_NEW = '''      + "<li>" + esc(data.bench.where) + "</li>"
      + (data.bench.slot ? "<li>" + esc(data.bench.slot) + "</li>" : "")
      + "<li>" + esc(data.bench.menu) + "</li></ol></div>";'''


def patch(path, steps, guard):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    if guard in text:
        print(path + ": already patched")
        return True

    for old, new, label in steps:
        if old not in text:
            print(path + ": could not find " + label)
            print("  nothing written to this file")
            return False
        text = text.replace(old, new, 1)

    try:
        ast.parse(text)
    except SyntaxError as err:
        print(path + ": refusing to write, result would not parse")
        print("  line " + str(err.lineno) + ": " + str(err.msg))
        return False

    shutil.copyfile(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(path + ": patched (backup written)")
    return True


def main():
    ok = True

    ok = patch("red_cameras.py", [
        ("def newest_release(html):", RED_HELPER.lstrip(chr(10))
         + "def newest_release(html):", "newest_release()"),
        (RED_CALL_OLD, RED_CALL_NEW, "the release dict"),
        (RED_ROW_OLD, RED_ROW_NEW, "the results row"),
        (RED_PRINT_OLD, RED_PRINT_NEW, "the progress print"),
    ], "install_sections") and ok

    ok = patch("build_feed.py", [
        (FEED_OLD, FEED_NEW, "the RED feed row"),
    ], '"install_source": row.get("install_source")') and ok

    ok = patch("build_site.py", [
        (SITE_RE_OLD, SITE_RE_NEW, "the root-directory pattern"),
        (SITE_MENU_OLD, SITE_MENU_NEW, "the menu patterns"),
        (SITE_MENU_USE_OLD, SITE_MENU_USE_NEW, "the menu lookup"),
        (SITE_OLD, SITE_NEW, "the bench line"),
        (PANEL_BENCH_OLD, PANEL_BENCH_NEW, "the panel bench markup"),
    ], "TOP_LEVEL_RE") and ok

    print("")
    if ok:
        print("Next: python3 red_cameras.py && python3 build_feed.py"
              " && python3 build_site.py")
    else:
        print("Something did not match. Nothing half-written: each file is")
        print("either fully patched or untouched.")


if __name__ == "__main__":
    main()
