"""Wire ARRI's install steps into the feed, the site and the daily run.

Three edits:
  build_feed.py   read arri_install.json and attach it to the ARRI rows
  build_site.py   teach the bench line ARRI's shapes: a *.SWU/*.SUP file, a
                  folder path like ARRI/A-Mini/SUP, and a menu path that
                  performs the update rather than the one that prepares the
                  stick
  daily.yml       run arri_install.py after the ARRI scrape, installing
                  pypdf first, and commit arri_install.json

Writes a .bak for each file. Any file that does not match is left untouched.

Run once:  python3 add_arri_install.py
"""

import ast
import re
import shutil

FEED_LOADER = '''ARRI_INSTALL = {}
try:
    with open("arri_install.json") as f:
        for row in json.load(f):
            ARRI_INSTALL[row["slug"]] = row
except FileNotFoundError:
    pass


'''

FEED_OLD = '''            "summary": (ARRI_DETAILS.get(row["slug"]) or {}).get("summary"),
            "features": (ARRI_DETAILS.get(row["slug"]) or {}).get("features") or [],
        })'''

FEED_NEW = '''            "summary": (ARRI_DETAILS.get(row["slug"]) or {}).get("summary"),
            "features": (ARRI_DETAILS.get(row["slug"]) or {}).get("features") or [],
            "install": (ARRI_INSTALL.get(row["slug"]) or {}).get("install") or [],
            "install_version": (ARRI_INSTALL.get(row["slug"]) or {}).get("install_version"),
            "install_source": (ARRI_INSTALL.get(row["slug"]) or {}).get("install_source"),
            "file_name": (ARRI_INSTALL.get(row["slug"]) or {}).get("file_name"),
        })'''

SITE_RE_OLD = '''TOP_LEVEL_RE = re.compile(r"\\btop level directory\\b", re.I)'''
SITE_RE_NEW = '''TOP_LEVEL_RE = re.compile(r"\\btop level directory\\b", re.I)
# ARRI names a folder on the stick, e.g. ARRI/A-Mini/SUP or ARRI/ALEXA265/SUP.
FOLDER_RE = re.compile(r"\\b(ARRI/[A-Za-z0-9-]+/(?:SUP|LICENSES))\\b")
# ARRI's file is a *.SUP or *.SWU package rather than a fixed filename.
PKG_RE = re.compile(r"(\\*\\.(?:SUP|SWU))\\b", re.I)'''

SITE_GOTO_OLD = '''MENU_GOTO_RE = re.compile(
    r"((?:Menu|MENU)\\s*>\\s*[A-Za-z ]{2,20}\\s*>\\s*[A-Za-z ]{2,24})")'''
SITE_GOTO_NEW = '''# Must name the update itself, so ARRI's "MENU > Media > Prepare USB
# Medium" does not win over "Menu > System > Update Camera".
MENU_GOTO_RE = re.compile(
    r"((?:Menu|MENU)\\s*>\\s*[A-Za-z ]{2,20}\\s*>\\s*"
    r"[A-Za-z ]{0,20}(?:Update|Upgrade)[A-Za-z .]{0,18})")'''

SITE_FILE_OLD = '''    file_name = cam.get("file_name")
    if not file_name:
        hit = FILE_RE.search(joined)
        file_name = hit.group(1) if hit else None'''

SITE_FILE_NEW = '''    file_name = cam.get("file_name")
    if not file_name:
        hit = FILE_RE.search(joined) or PKG_RE.search(joined)
        file_name = hit.group(1) if hit else None
    if file_name:
        file_name = file_name.upper() if file_name.startswith("*") else file_name'''

SITE_WHERE_OLD = '''    if ROOT_RE.search(joined):
        where = "card root"
    elif TOP_LEVEL_RE.search(joined):
        where = "card top level"
    else:
        where = "card"'''

SITE_WHERE_NEW = '''    folder = FOLDER_RE.search(joined)
    if folder:
        where = folder.group(1)
    elif ROOT_RE.search(joined):
        where = "card root"
    elif TOP_LEVEL_RE.search(joined):
        where = "card top level"
    else:
        where = "card"'''

WORKFLOW = ".github/workflows/daily.yml"
NL = chr(10)


def patch_py(path, steps, guard):
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


def patch_workflow():
    with open(WORKFLOW, encoding="utf-8") as fh:
        text = fh.read()

    if "arri_install.py" in text:
        print(WORKFLOW + ": already wired up")
        return True

    lines = text.split(NL)
    after = "Fetch ARRI details"
    idx = None
    for i, line in enumerate(lines):
        if re.match(r"\s*-\s+name:\s*" + re.escape(after) + r"\s*$", line):
            idx = i
            break
    if idx is None:
        print(WORKFLOW + ": could not find the '" + after + "' step")
        return False

    dash = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
    key = dash + "  "

    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if not lines[j].strip():
            continue
        if len(lines[j]) - len(lines[j].lstrip()) <= len(dash):
            end = j
            break
    at = end
    while at > idx and not lines[at - 1].strip():
        at -= 1

    step = [
        "",
        dash + "- name: Extract ARRI install steps",
        key + "run: |",
        key + "  pip install --quiet pypdf",
        key + "  python arri_install.py",
    ]
    lines = lines[:at] + step + lines[at:]
    text = NL.join(lines)

    marker = "git add feed.json snapshot.json"
    if marker in text:
        text = text.replace(marker, marker + " arri_install.json", 1)
    else:
        print(WORKFLOW + ": add arri_install.json to the git add line by hand")

    order = [n.strip() for n in re.findall(r"-\s+name:\s*(.+)", text)]
    try:
        if not (order.index(after) < order.index("Extract ARRI install steps")
                < order.index("Build feed")):
            print(WORKFLOW + ": step landed in the wrong place, not written")
            return False
    except ValueError:
        print(WORKFLOW + ": could not confirm step order, not written")
        return False

    shutil.copyfile(WORKFLOW, WORKFLOW + ".bak")
    with open(WORKFLOW, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(WORKFLOW + ": patched")
    print("  steps: " + ", ".join(order))
    return True


def main():
    ok = True

    ok = patch_py("build_feed.py", [
        ("ARRI_DETAILS = {}", FEED_LOADER + "ARRI_DETAILS = {}",
         "the ARRI details loader"),
        (FEED_OLD, FEED_NEW, "the ARRI feed row"),
    ], "ARRI_INSTALL") and ok

    ok = patch_py("build_site.py", [
        (SITE_RE_OLD, SITE_RE_NEW, "the where patterns"),
        (SITE_GOTO_OLD, SITE_GOTO_NEW, "the goto menu pattern"),
        (SITE_FILE_OLD, SITE_FILE_NEW, "the file lookup"),
        (SITE_WHERE_OLD, SITE_WHERE_NEW, "the where lookup"),
    ], "FOLDER_RE") and ok

    ok = patch_workflow() and ok

    print("")
    if ok:
        print("Next: python3 arri_install.py && python3 build_feed.py"
              " && python3 build_site.py")
    else:
        print("Something did not match. Each file is either fully patched")
        print("or untouched.")


if __name__ == "__main__":
    main()
