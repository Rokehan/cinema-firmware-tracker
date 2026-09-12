#!/usr/bin/env python3
"""Patcher: extract direct download URLs from Sony EN pages.

Sony hosts firmware files on nexim.my.salesforce-sites.com via a
FileDownload servlet. The scraper already fetches these pages but
only extracts the download URL for cinema bodies (via cinema_details).

This patch adds a generic download URL extractor that runs for all
models, catching the Salesforce-hosted files for FX/Alpha/FR7 bodies.

Touches sony_english.py only. Safe to run twice.
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

MARKER = "DOWNLOAD_RE"
if MARKER in original:
    print("Already patched (%s found). Nothing to do." % MARKER)
    sys.exit(0)

# 1. Add the regex constant after the existing TITLE_VERSION_RE
ANCHOR1 = 'TITLE_VERSION_RE = re.compile(r"V([0-9]+\\.[0-9]+)")'
INSERT1 = (
    'TITLE_VERSION_RE = re.compile(r"V([0-9]+\\.[0-9]+)")\n\n'
    '# Sony serves firmware files from Salesforce. This catches the\n'
    '# direct download link on FX, Alpha, and FR7 pages.\n'
    'DOWNLOAD_RE = re.compile(\n'
    '    r\'href="(https?://[^"]*(?:FileDownload|servlet\\.FileDownload)[^"]*)\',\n'
    '    re.I,\n'
    ')'
)

# 2. In main(), after the install sections extraction, extract the download URL.
# We hook into where firmware_url is set in the row dict.
ANCHOR2 = '            "firmware_url": cinema.get("firmware_url"),'
INSERT2 = (
    '            "firmware_url": cinema.get("firmware_url")\n'
    '                or (DOWNLOAD_RE.search(page) and DOWNLOAD_RE.search(page).group(1)),'
)

patched = original

if ANCHOR1 not in patched:
    print("Cannot find TITLE_VERSION_RE anchor")
    sys.exit(1)
patched = patched.replace(ANCHOR1, INSERT1, 1)

if ANCHOR2 not in patched:
    print("Cannot find firmware_url anchor")
    sys.exit(1)
patched = patched.replace(ANCHOR2, INSERT2, 1)

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
