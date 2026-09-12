"""One-shot repair for discover_camera_pages() in arri_cameras.py.

Replaces the whole function with a correctly indented version that reads
ARRI's camera index (not the firmware hub) and skips archive pages instead
of overview pages. Writes arri_cameras.py.bak first.

Run once:  python3 fix_discover.py
"""

import ast
import re
import shutil

TARGET = "arri_cameras.py"

Q = chr(34) * 3
IDX = "https://www.arri.com/en/technical-service/firmware/"
IDX = IDX + "software-and-firmware-updates-for-cameras"

NEW = [
    "def discover_camera_pages():",
    "    " + Q + "Read the current camera list from ARRI's camera index every",
    "    run, so version bumps and new bodies are picked up automatically.",
    "",
    "    ARRI names some real camera pages '<body>-sup-overview' (ALEXA Mini,",
    "    AMIRA), so only archive pages are skipped." + Q,
    "    index = fetch(",
    "        " + chr(34) + IDX + chr(34),
    "    )",
    "    pattern = (",
    "        r'href=" + chr(34) + "/en/technical-service/firmware/'",
    "        r'software-and-firmware-updates-for-cameras/([^" + chr(34) + "/]+)" + chr(34) + "'",
    "    )",
    "    slugs = []",
    "    for slug in re.findall(pattern, index):",
    "        if slug in slugs:",
    "            continue",
    "        if " + chr(34) + "archive" + chr(34) + " in slug.lower():",
    "            continue",
    "        slugs.append(slug)",
    "    return slugs",
]


def main():
    with open(TARGET, encoding="utf-8") as fh:
        lines = fh.read().split(chr(10))

    start = None
    for i, line in enumerate(lines):
        if line.startswith("def discover_camera_pages"):
            start = i
            break
    if start is None:
        print("Could not find discover_camera_pages in " + TARGET)
        return

    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line and not line[0].isspace() and not line.startswith(")"):
            end = j
            break

    rebuilt = lines[:start] + NEW + [""] + lines[end:]
    text = chr(10).join(rebuilt)

    try:
        ast.parse(text)
    except SyntaxError as err:
        print("Refusing to write: result would not parse.")
        print("  line " + str(err.lineno) + ": " + str(err.msg))
        return

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Replaced lines " + str(start + 1) + "-" + str(end)
          + " of " + TARGET + " (backup: " + TARGET + ".bak)")
    print("File parses cleanly. Now run: python3 arri_cameras.py")


if __name__ == "__main__":
    main()
