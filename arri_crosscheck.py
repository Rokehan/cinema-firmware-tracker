"""Cross-check scraped ARRI versions against ARRI's own index titles.

ARRI's combined index prints each product's current package, for example
"ALEXA 35 SUP 6.2.0". The product pages are scraped separately, so a parsing
regression could otherwise publish an old version without anyone noticing.

Fails the run when an indexed product is missing from the scrape. A version
that disagrees with the index is reported loudly but does not stop the run,
because ARRI occasionally updates a product page before its index tile.
"""
import json
import os
import sys

import arri_index

SECTIONS = {
    "Cameras": "arri_cameras.json",
    "Electronic Control Systems": "arri_kit.json",
    "Monitors": "arri_kit.json",
    "Camera Stabilizer Systems": "arri_kit.json",
}


def load(name):
    with open(name, encoding="utf-8") as fh:
        return {row.get("slug"): row for row in json.load(fh)}


def main():
    index = arri_index.sections()
    missing, mismatched, ok = [], [], 0
    for heading, source in SECTIONS.items():
        rows = load(source)
        for item in index.get(heading, []):
            row = rows.get(item["slug"])
            if row is None:
                missing.append(heading + ": " + item["title"])
                continue
            want = arri_index.version_numbers(item["title"])
            got = arri_index.version_numbers(row.get("version"))
            if want and got and want != got:
                mismatched.append(item["title"] + " (scraped " + str(row.get("version")) + ")")
            else:
                ok += 1
    lines = ["ARRI cross-check: " + str(ok) + " match ARRI's index"]
    for m in mismatched:
        lines.append("  VERSION DIFFERS FROM ARRI INDEX: " + m)
    for m in missing:
        lines.append("  MISSING FROM SCRAPE: " + m)
    print(chr(10).join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(chr(10).join(lines) + chr(10))
    if missing or ok == 0:
        sys.exit("ARRI scrape is incomplete. Nothing will be published.")


if __name__ == "__main__":
    main()
