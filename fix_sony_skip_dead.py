#!/usr/bin/env python3
"""Patcher: skip known-dead Sony EN models and reduce retries.

Five legacy models consistently 500/408/404 on sony.com. Rather than
waiting 90s * 3 retries * 2 paths = 9+ minutes per dead model, skip
them entirely. They can be re-enabled if Sony ever revives the pages.

Also reduces default fetch retries from 3 to 2 to speed up the run.

Safe to run twice.
"""
import ast, shutil, sys

TARGET = "sony_english.py"
BACKUP = TARGET + ".bak"

with open(TARGET) as f:
    original = f.read()

try:
    ast.parse(original)
except SyntaxError as e:
    print("Original has a syntax error: %s" % e)
    sys.exit(1)

if "SKIP_MODELS" in original:
    print("Already patched (SKIP_MODELS found). Nothing to do.")
    sys.exit(0)

patched = original

# 1. Add skip list before MODELS dict
ANCHOR1 = "MODELS = {"
INSERT1 = (
    "# EN pages for these legacy models are dead (500/408/404 as of Sep 2026).\n"
    "# Skip to avoid hanging the pipeline. Re-enable if Sony revives them.\n"
    "SKIP_MODELS = {\"FX9\", \"FS7 II\", \"PXW-FS7\", \"PMW-F55\", \"PMW-F5\"}\n\n"
    "MODELS = {"
)
patched = patched.replace(ANCHOR1, INSERT1, 1)

# 2. Add skip check at the top of the main loop
ANCHOR2 = '    for product, paths in MODELS.items():'
INSERT2 = (
    '    for product, paths in MODELS.items():\n'
    '        if product in SKIP_MODELS:\n'
    '            print("=" * 60)\n'
    '            print(product)\n'
    '            print("  skipped (EN page known dead)")\n'
    '            print()\n'
    '            continue'
)
# Only replace the first occurrence (in main)
patched = patched.replace(ANCHOR2, INSERT2, 1)

# 3. Reduce default retries from 3 to 2
patched = patched.replace("def fetch(url, tries=3):", "def fetch(url, tries=2):")

try:
    ast.parse(patched)
except SyntaxError as e:
    print("Patched version has a syntax error: %s" % e)
    sys.exit(1)

shutil.copy2(TARGET, BACKUP)
with open(TARGET, "w") as f:
    f.write(patched)

print("Patched %s (backup: %s)" % (TARGET, BACKUP))
print("Next: python3 sony_english.py")
