"""Stop ARRI's table of contents masquerading as the update procedure.

Five cameras came back with junk: "via SD Card ....... 17" (a contents-page
line) or "Bug fixes" (the changelog). Cause: the heading "Camera Update
Procedure" appears first in the table of contents, so the extractor started
there instead of at the real section.

Three corrections:
  1. start at the LAST occurrence of the heading, not the first
  2. drop contents-page lines, which carry dotted leaders and a page number
  3. require the section to look like instructions (it must mention a file,
     a folder, a menu or a stick) and report nothing when it does not,
     rather than publishing whatever text happened to follow

Patches arri_install.py. Writes a .bak, refuses to save if it will not parse.

Run once:  python3 fix_arri_toc.py
"""

import ast
import shutil

TARGET = "arri_install.py"

OLD_NOISE = '''NOISE_RE = re.compile(
    r"^(?:page\\s*\\d+|\\d+\\s*/\\s*\\d+|\\d{1,3}|arri|www\\.arri\\.com|"
    r"release notes?|software update package.*|"
    r"[A-Z]{2,}\\s*\\d{2,}.*)$",
    re.I,
)'''

NEW_NOISE = '''NOISE_RE = re.compile(
    r"^(?:page\\s*\\d+|\\d+\\s*/\\s*\\d+|\\d{1,3}|arri|www\\.arri\\.com|"
    r"release notes?|software update package.*|"
    r"[A-Z]{2,}\\s*\\d{2,}.*)$",
    re.I,
)

# A contents-page line: dotted leaders, or a trailing page number.
TOC_RE = re.compile(r"\\.\\s*\\.\\s*\\.|\\.{4,}|\\s\\d{1,3}$")

# The section has to read like instructions before it is published.
PROOF_WORDS = ("usb", "stick", "sup", "swu", "menu", "folder", "card",
               "unpack", "zip", "update camera", "licenses")'''

OLD_TIDY = '''        line = " ".join(raw.split())
        if not line or NOISE_RE.match(line):
            continue'''

NEW_TIDY = '''        line = " ".join(raw.split())
        if not line or NOISE_RE.match(line):
            continue
        if TOC_RE.search(line) and len(line) < 200:
            continue'''

OLD_PROC = '''    start = -1
    heading = None
    for candidate in START_HEADS:
        index = text.find(candidate)
        if index > -1:
            start = index
            heading = candidate
            break
    if start < 0:
        return None, []'''

NEW_PROC = '''    # The heading appears in the table of contents first, so take its last
    # occurrence, which is the section itself.
    start = -1
    heading = None
    for candidate in START_HEADS:
        index = text.rfind(candidate)
        if index > -1:
            start = index
            heading = candidate
            break
    if start < 0:
        return None, []'''

OLD_RETURN = '''    return heading, tidy(body.split(chr(10)))'''

NEW_RETURN = '''    steps = tidy(body.split(chr(10)))

    # Refuse to publish a section that does not read like instructions.
    joined = " ".join(steps).lower()
    if not any(word in joined for word in PROOF_WORDS):
        return heading, []

    return heading, steps'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "TOC_RE" in text:
        print("Already patched. Nothing to do.")
        return

    steps = (
        (OLD_NOISE, NEW_NOISE, "the noise pattern"),
        (OLD_TIDY, NEW_TIDY, "the tidy loop"),
        (OLD_PROC, NEW_PROC, "the heading search"),
        (OLD_RETURN, NEW_RETURN, "the return"),
    )

    for old, new, label in steps:
        if old not in text:
            print("Could not find " + label + " in " + TARGET)
            print("Nothing written.")
            return
        text = text.replace(old, new, 1)

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
    print("Next: python3 arri_install.py")


if __name__ == "__main__":
    main()
