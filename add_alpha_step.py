"""Run sony_alpha.py in the daily workflow.

Adds a "Scrape Sony Alpha" step after the Sony FX steps and before
"Build feed", and puts sony_alpha.json in the files the bot stages.

Indentation is copied from the existing steps. Writes a .bak and refuses to
save if the step order comes out wrong.

Run once:  python3 add_alpha_step.py
"""

import re
import shutil

TARGET = ".github/workflows/daily.yml"
NL = chr(10)

AFTER_CANDIDATES = ("Resolve Sony file URLs", "Scrape Sony FX line")
NEW_NAME = "Scrape Sony Alpha"
NEW_RUN = "python sony_alpha.py"
DATA_FILE = "sony_alpha.json"


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "sony_alpha.py" in text:
        print("Already wired up. Nothing to do.")
        return

    lines = text.split(NL)

    idx = None
    after = None
    for candidate in AFTER_CANDIDATES:
        for i, line in enumerate(lines):
            if re.match(r"\s*-\s+name:\s*" + re.escape(candidate) + r"\s*$", line):
                idx = i
                after = candidate
                break
        if idx is not None:
            break

    if idx is None:
        print("Could not find a Sony step to follow in " + TARGET)
        print("Nothing written.")
        return

    dash_indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
    key_indent = dash_indent + "  "

    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if not lines[j].strip():
            continue
        indent = len(lines[j]) - len(lines[j].lstrip())
        if indent <= len(dash_indent):
            end = j
            break

    insert_at = end
    while insert_at > idx and not lines[insert_at - 1].strip():
        insert_at -= 1

    new_step = [
        "",
        dash_indent + "- name: " + NEW_NAME,
        key_indent + "run: " + NEW_RUN,
    ]

    lines = lines[:insert_at] + new_step + lines[insert_at:]
    text = NL.join(lines)

    marker = "git add feed.json snapshot.json"
    if marker in text:
        text = text.replace(marker, marker + " " + DATA_FILE, 1)
    else:
        print("Warning: could not extend the 'git add' line. Add "
              + DATA_FILE + " to it by hand.")

    order = [n.strip() for n in re.findall(r"-\s+name:\s*(.+)", text)]
    try:
        pos_new = order.index(NEW_NAME)
        pos_after = order.index(after)
        pos_feed = order.index("Build feed")
    except ValueError:
        print("Refusing to write: could not confirm the step order.")
        return

    if not pos_after < pos_new < pos_feed:
        print("Refusing to write: '" + NEW_NAME + "' did not land between")
        print("'" + after + "' and 'Build feed'.")
        return

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Steps now: " + ", ".join(order))
    print("Patched " + TARGET + " (backup: " + TARGET + ".bak)")


if __name__ == "__main__":
    main()
