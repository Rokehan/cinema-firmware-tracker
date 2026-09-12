"""Wire the site rebuild into the daily workflow.

Two edits to .github/workflows/daily.yml:
  1. a "Build site" step after "Detect changes", running build_site.py
  2. index.html added to the files the bot stages and commits

Indentation is copied from the existing steps rather than assumed, so the
file stays valid whatever your current spacing is. Writes a .bak first and
refuses to save if the result is not valid YAML.

Run once:  python3 add_site_step.py
"""

import re
import shutil

TARGET = ".github/workflows/daily.yml"
NL = chr(10)


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "build_site.py" in text:
        print("Already wired up. Nothing to do.")
        return

    lines = text.split(NL)

    # Find the "Detect changes" step and copy its indentation.
    idx = None
    for i, line in enumerate(lines):
        if re.match(r"\s*-\s+name:\s*Detect changes\s*$", line):
            idx = i
            break
    if idx is None:
        print("Could not find the 'Detect changes' step in " + TARGET)
        print("Nothing written.")
        return

    dash_indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
    key_indent = dash_indent + "  "

    # The step ends at the next line indented no deeper than the dash.
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        stripped = lines[j].strip()
        if not stripped:
            continue
        indent = len(lines[j]) - len(lines[j].lstrip())
        if indent <= len(dash_indent):
            end = j
            break

    # Back up over blank lines so the new step lands directly under the
    # previous one, keeping the file's existing spacing rhythm.
    insert_at = end
    while insert_at > idx and not lines[insert_at - 1].strip():
        insert_at -= 1

    new_step = [
        "",
        dash_indent + "- name: Build site",
        key_indent + "run: python build_site.py",
    ]

    lines = lines[:insert_at] + new_step + lines[insert_at:]
    text = NL.join(lines)

    # Stage the generated page alongside the data files.
    old_add = "git add feed.json snapshot.json arri_cameras.json"
    if old_add in text and "index.html" not in text.split("git add")[1][:200]:
        text = text.replace(old_add, old_add + " index.html", 1)
    else:
        print("Warning: could not extend the 'git add' line; add index.html")
        print("to it by hand or the page will never be published.")

    try:
        import yaml
    except ImportError:
        yaml = None

    if yaml is not None:
        try:
            parsed = yaml.safe_load(text)
        except Exception as err:
            print("Refusing to write: result is not valid YAML.")
            print("  " + str(err))
            return
        steps = parsed["jobs"]["check"]["steps"]
        names = [s.get("name") for s in steps if isinstance(s, dict)]
        print("Steps now: " + ", ".join(n for n in names if n))
    else:
        print("PyYAML not installed, skipping the YAML validity check.")

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Patched " + TARGET + " (backup: " + TARGET + ".bak)")
    print("The daily run will now rebuild and publish index.html.")


if __name__ == "__main__":
    main()
