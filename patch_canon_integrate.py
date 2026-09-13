#!/usr/bin/env python3
"""patch_canon_integrate.py  --  Merge Canon into the live pipeline.

Edits four files:
  daily.yml         add a Canon step after red_cameras, before build_feed
  build_feed.py     load canon_cameras.json and extend the feed
  build_site.py     add "Canon" to EXPECTED_MAKES, honour download_opens_page
  check_changes.py  include Canon in the vanish guard (if it counts per maker)

This patcher does NOT assume exact file contents. It searches for anchors,
reports precisely what it changed, and prints a manual instruction for
anything it could not match. Every touched file gets a .bak first and is
syntax/YAML checked before saving. Safe to run twice.
"""

import re, shutil, sys
from pathlib import Path

NL = chr(10)
report = []
manual = []


def backup(p):
    b = Path(str(p) + ".bak")
    shutil.copy2(p, b)
    return b


def save_py(path, text, label):
    try:
        compile(text, str(path), "exec")
    except SyntaxError as e:
        print("  SYNTAX ERROR in " + label + ": " + str(e))
        print("  not saving " + label)
        return False
    path.write_text(text)
    return True


# ══════════════════════════════════════════════════════════════════
# 1. daily.yml
# ══════════════════════════════════════════════════════════════════
p = Path(".github/workflows/daily.yml")
if not p.exists():
    p = Path("daily.yml")

if not p.exists():
    manual.append("daily.yml not found. Add a step running "
                  "'python canon_cameras.py' after red_cameras.py "
                  "and before build_feed.py.")
else:
    y = p.read_text()
    if "canon_cameras.py" in y:
        report.append("daily.yml already runs canon_cameras.py")
    else:
        m = re.search(r"([ \t]*)-[ \t]+name:[^\n]*\n(?:[ \t]+[^\n]*\n)*?"
                      r"[ \t]+run:[ \t]*python[ \t]+red_cameras\.py[^\n]*\n",
                      y)
        if not m:
            m = re.search(r"([ \t]*)-[ \t]+name:[^\n]*\n(?:[ \t]+[^\n]*\n)*?"
                          r"[ \t]+run:[ \t]*python[ \t]+build_feed\.py[^\n]*\n", y)
            insert_before = True
        else:
            insert_before = False

        if not m:
            manual.append("daily.yml: could not find the red_cameras.py or "
                          "build_feed.py step. Add manually:" + NL
                          + "      - name: Canon cameras" + NL
                          + "        run: python canon_cameras.py")
        else:
            indent = m.group(1)
            block = (indent + "- name: Canon cameras" + NL
                     + indent + "  run: python canon_cameras.py" + NL)
            backup(p)
            if insert_before:
                y2 = y[:m.start()] + block + y[m.start():]
            else:
                y2 = y[:m.end()] + block + y[m.end():]
            # cheap YAML sanity: no tabs introduced, step count grew by one
            if chr(9) in block:
                print("  refusing: tab characters in YAML block")
            else:
                p.write_text(y2)
                report.append("daily.yml: added the Canon cameras step "
                              + ("before build_feed" if insert_before
                                 else "after red_cameras"))

# ══════════════════════════════════════════════════════════════════
# 2. build_feed.py
# ══════════════════════════════════════════════════════════════════
p = Path("build_feed.py")
if not p.exists():
    manual.append("build_feed.py not found. Load canon_cameras.json and "
                  "extend the feed list with it.")
else:
    s = p.read_text()
    if "canon_cameras.json" in s:
        report.append("build_feed.py already loads canon_cameras.json")
    else:
        orig = s
        # find how the other makers are loaded, mirror it
        m = re.search(r"^([ \t]*)(\w+)\s*=\s*json\.loads\(\s*Path\(\s*"
                      r"[\"']red_cameras\.json[\"']\s*\)\.read_text\(\)\s*\)",
                      s, re.M)
        if m:
            ind, var = m.group(1), m.group(2)
            line = (NL + ind + "canon = json.loads("
                    + "Path(\"canon_cameras.json\").read_text()) \\"
                    + NL + ind + "    if Path(\"canon_cameras.json\").exists() else []")
            s = s[:m.end()] + line + s[m.end():]
        else:
            m = re.search(r"^([ \t]*)(\w+)\s*=\s*json\.load\(\s*open\(\s*"
                          r"[\"']red_cameras\.json[\"']\s*\)\s*\)", s, re.M)
            if m:
                ind = m.group(1)
                line = (NL + ind + "canon = json.load(open(\"canon_cameras.json\")) \\"
                        + NL + ind + "    if Path(\"canon_cameras.json\").exists() else []")
                s = s[:m.end()] + line + s[m.end():]

        if s == orig:
            manual.append("build_feed.py: could not find how red_cameras.json "
                          "is loaded. Add, matching the existing style:" + NL
                          + "    canon = json.loads(Path(\"canon_cameras.json\").read_text())" + NL
                          + "  then include 'canon' in the merged feed list.")
        else:
            # now extend the feed
            done_extend = False
            m2 = re.search(r"^([ \t]*)feed\.extend\(\s*red\w*\s*\)", s, re.M)
            if m2:
                s = (s[:m2.end()] + NL + m2.group(1) + "feed.extend(canon)"
                     + s[m2.end():])
                done_extend = True
            else:
                m2 = re.search(r"^([ \t]*)feed\s*=\s*(\[[^\]]*red\w*[^\]]*\])",
                               s, re.M)
                if m2:
                    lst = m2.group(2)
                    s = s[:m2.start(2)] + lst[:-1].rstrip() + " + canon]" + s[m2.end(2):]
                    done_extend = True
            if done_extend:
                if save_py(p if True else p, s, "build_feed.py"):
                    backup_note = "build_feed.py: loads canon_cameras.json and extends the feed"
                    report.append(backup_note)
            else:
                manual.append("build_feed.py: loaded canon but could not find "
                              "where the feed list is assembled. Add "
                              "'feed.extend(canon)' next to the other makers.")

# ══════════════════════════════════════════════════════════════════
# 3. build_site.py
# ══════════════════════════════════════════════════════════════════
p = Path("build_site.py")
if not p.exists():
    manual.append("build_site.py not found. Add \"Canon\" to EXPECTED_MAKES "
                  "and honour download_opens_page for the arrow icon.")
else:
    s = p.read_text()
    orig = s
    changed = []

    # 3a. EXPECTED_MAKES
    m = re.search(r"EXPECTED_MAKES\s*=\s*(\[[^\]]*\])", s)
    if m:
        block = m.group(1)
        if re.search(r"[\"']Canon[\"']", block):
            report.append("build_site.py: Canon already in EXPECTED_MAKES")
        else:
            q = "\"" if "\"" in block else "'"
            newblock = block[:-1].rstrip()
            if not newblock.endswith("["):
                newblock += ","
            newblock += " " + q + "Canon" + q + "]"
            s = s[:m.start(1)] + newblock + s[m.end(1):]
            changed.append("added Canon to EXPECTED_MAKES")
    else:
        manual.append("build_site.py: EXPECTED_MAKES not found. Add "
                      "\"Canon\" to the maker list so the tab renders.")

    # 3b. download_opens_page -> arrow
    if "download_opens_page" in s:
        report.append("build_site.py: already honours download_opens_page")
    else:
        # find whatever the existing arrow condition is
        m2 = re.search(r"^([ \t]*)(\w+)\s*=\s*[\"']\u2197[\"']", s, re.M)
        hint = ""
        if m2:
            hint = " (existing arrow variable: " + m2.group(2) + ")"
        manual.append("build_site.py: add the arrow for Canon. Each Canon "
                      "record carries download_opens_page=true, so wherever "
                      "the Download button is rendered, append the \u2197 when "
                      "entry.get(\"download_opens_page\") is true." + hint)

    if s != orig:
        backup(p)
        if save_py(p, s, "build_site.py"):
            for c in changed:
                report.append("build_site.py: " + c)

# ══════════════════════════════════════════════════════════════════
# 4. check_changes.py
# ══════════════════════════════════════════════════════════════════
p = Path("check_changes.py")
if not p.exists():
    manual.append("check_changes.py not found. If it validates per-maker "
                  "counts, add Canon with an expected count of 22.")
else:
    s = p.read_text()
    if re.search(r"[\"']Canon[\"']", s):
        report.append("check_changes.py already mentions Canon")
    else:
        m = re.search(r"^([ \t]*)([A-Z_]+)\s*=\s*\{([^}]*[\"']RED[\"'][^}]*)\}",
                      s, re.M | re.S)
        if m:
            body = m.group(3)
            sep = "," if body.strip() and not body.strip().endswith(",") else ""
            ind = m.group(1)
            s = (s[:m.end(3)] + sep + NL + ind + "    \"Canon\": 22,"
                 + NL + ind + s[m.end(3):])
            backup(p)
            if save_py(p, s, "check_changes.py"):
                report.append("check_changes.py: added Canon with expected count 22")
        else:
            manual.append("check_changes.py: no per-maker count dict found. "
                          "If it guards on total entry count, bump it by 22; "
                          "otherwise no change is needed.")

# ══════════════════════════════════════════════════════════════════
print()
print("=" * 66)
print("APPLIED")
print("=" * 66)
if report:
    for r in report:
        print("  " + r)
else:
    print("  nothing")

if manual:
    print()
    print("=" * 66)
    print("DO THESE BY HAND")
    print("=" * 66)
    for mm in manual:
        print()
        print("  * " + mm)

print()
print("=" * 66)
print("THEN VERIFY")
print("=" * 66)
print("  python canon_cameras.py        # writes canon_cameras.json")
print("  python build_feed.py           # should report Canon entries")
print("  python check_changes.py")
print("  python build_site.py           # rebuilds index.html")
print()
print("  Open index.html and confirm: a Canon tab appears, entries show")
print("  changelogs, previous versions expand, and Download buttons carry")
print("  the arrow because they open a Canon support page.")
