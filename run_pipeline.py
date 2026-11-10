#!/usr/bin/env python3
"""Run the whole firmware refresh in order, stopping at the first failure.

Used by both GitHub workflows (the daily check and approved ClickUp updates),
so they can never drift apart. Each step's log is grouped in GitHub's output,
and the step that failed is named at the bottom of the log and in the run
summary, so nobody has to dig through the log to find it.
"""
import os
import subprocess
import sys
import time

STEPS = [
    ("Scrape ARRI", ["arri_cameras.py"]),
    ("Fetch ARRI details", ["arri_details.py"]),
    ("Extract ARRI install steps", ["arri_install.py"]),
    ("ARRI SUP archive", ["arri_archive.py"]),
    ("ARRI accessories", ["arri_kit.py"]),
    ("ARRI accessory archives", ["arri_kit_archive.py"]),
    ("ARRI version cross-check", ["arri_crosscheck.py"]),
    ("Scrape Sony index", ["sony_downloads.py"]),
    ("Scrape Sony FX line", ["sony_fx.py"]),
    ("Resolve Sony file URLs", ["sony_files.py"]),
    ("Scrape Sony Alpha", ["sony_alpha.py"]),
    ("Sony English data", ["sony_english.py"]),
    ("Scrape RED", ["red_cameras.py"]),
    ("Canon cameras", ["canon_cameras.py"]),
    ("Teradek", ["teradek.py"]),
    ("Build feed", ["build_feed.py"]),
    ("Detect changes", ["check_changes.py"]),
    ("Build site", ["build_site.py"]),
]

# Files the daily run is allowed to commit. Everything else it writes is
# scratch and is regenerated next run.
DATA_FILES = [
    "feed.json", "snapshot.json", "last_refresh.json", "index.html",
    "arri_install.json", "arri_cameras.json", "arri_details.json",
    "sony_alpha.json", "red_cameras.json", "sony_cameras.json", "sony_fx.json",
]

IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + chr(10))


def main():
    for name, args in STEPS:
        if IN_ACTIONS:
            print("::group::" + name, flush=True)
        else:
            print(chr(10) + "=== " + name + " ===", flush=True)
        started = time.time()
        code = subprocess.call([sys.executable] + args)
        if IN_ACTIONS:
            print("::endgroup::", flush=True)
        took = int(time.time() - started)
        if code != 0:
            msg = "FAILED STEP: " + name + " (" + args[0] + ", exit " + str(code) + ")"
            print(chr(10) + msg + chr(10) + "Open that group above for the error. Nothing was published.")
            if IN_ACTIONS:
                print("::error title=Firmware refresh failed::" + msg)
            summary("### " + msg + chr(10) + "Nothing was published; the live site is unchanged.")
            sys.exit(1)
        print("  ok: " + name + " (" + str(took) + "s)", flush=True)
    summary("### Refresh succeeded")
    print(chr(10) + "All steps passed.")


if __name__ == "__main__":
    if "--data-files" in sys.argv:
        print(" ".join(DATA_FILES))
    else:
        main()
