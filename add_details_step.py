"""Run arri_details.py in the daily workflow.

Why: build_feed.py reads arri_details.json for the English summaries and
feature lists, but nothing in the workflow ever regenerates that file. It is
frozen at whatever was last produced by hand, so newly discovered bodies
(ALEXA Mini, AMIRA, ALEXA SXT) have no summary and corrected versions keep
the old text.

arri_details.py reads its slug list from arri_cameras.json, so the new step
goes immediately after "Scrape ARRI" and before "Build feed".

Two edits to .github/workflows/daily.yml:
  1. a "Fetch ARRI details" step after "Scrape ARRI"
  2. arri_details.json added to the files the bot stages

Indentation is copied from the existing steps. Writes a .bak and refuses to
save if the step order comes out wrong.

Run once:  python3 add_details_step.py
"""

import re
import shutil

TARGET = ".github/workflows/daily.yml"
NL = chr(10)

AFTER_STEP = "Scrape ARRI"
NEW_NAME = "Fetch ARRI details"
NEW_RUN = "python arri_details.py"
DATA_FILE = "arri_details.json"


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "arri_details.py" in text:
        print("Already wired up. Nothing to do.")
        return

    lines = text.split(NL)

    idx = None
    for i, line in enumerate(lines):
        if re.match(r"\s*-\s+name:\s*" + AFTER_STEP + r"\s*$", line):
            idx = i
            break
    if idx is None:
        print("Could not find the '" + AFTER_STEP + "' step in " + TARGET)
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

    marker = "git add feed.json snapshot.json arri_cameras.json"
    if marker in text:
        text = text.replace(marker, marker + " " + DATA_FILE, 1)
    else:
        print("Warning: could not extend the 'git add' line. Add "
              + DATA_FILE + " to it by hand or the summaries will")
        print("be regenerated and then thrown away each run.")

    order = re.findall(r"-\s+name:\s*(.+)", text)
    order = [name.strip() for name in order if not name.strip().startswith("actions/")]

    try:
        pos_details = order.index(NEW_NAME)
        pos_arri = order.index(AFTER_STEP)
        pos_feed = order.index("Build feed")
    except ValueError:
        print("Refusing to write: could not confirm the step order.")
        return

    if not pos_arri < pos_details < pos_feed:
        print("Refusing to write: '" + NEW_NAME + "' did not land between")
        print("'" + AFTER_STEP + "' and 'Build feed'.")
        return

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Steps now: " + ", ".join(order))
    print("Patched " + TARGET + " (backup: " + TARGET + ".bak)")
    print("Summaries will be refreshed every run.")


if __name__ == "__main__":
    main()
