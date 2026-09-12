#!/usr/bin/env python3
"""Patcher: add SmallHD PageOS as a new manufacturer + feed entry.

Creates smallhd.json with a single PageOS entry that lists all
compatible monitors from Capsule's rental fleet. Updates build_feed.py
to load it. Updates build_site.py EXPECTED_MAKES to include SmallHD.

The search haystack includes every monitor model name so typing
"Cine 7" or "Ultra 5" or "OLED 27" finds the PageOS entry.

Safe to run twice.
"""
import ast, json, shutil, sys

# ---- 1. Write smallhd.json ----
MONITORS = [
    "703 Bolt", "703 UltraBright", "503 UltraBright",
    "Ultra 5", "Ultra 7", "Cine 5", "Cine 7",
    "Cine 13", "Cine 18", "Cine 24",
    "Vision 17", "OLED 27",
]

CHANGELOG = [
    "Fleet Control: manage multiple monitors simultaneously over a network",
    "Portrait Mode UI for vertical video production",
    "Canon camera control (C70, C80, C300 III, C400, C500 II)",
    "Camera control on physical dials (Quantum/Ultra 10 series)",
    "Downstream LUT support on 4K Production Monitors",
    "Ultra 7 Max Bright mode",
    "Cross conversion and Signal Routing Diagram on 4K Production Monitors",
]

INSTALL = [
    {
        "heading": "Prepare the SD card",
        "items": [
            "SD card must be 16 GB or smaller.",
            "Format as FAT or FAT32 (Windows) or MS-DOS FAT (macOS). If partitioned, select MBR Master Boot Record under Scheme.",
        ]
    },
    {
        "heading": "Download and copy firmware",
        "items": [
            "Visit downloads.smallhd.com and download the latest PageOS firmware.",
            "Extract the .bin file from the .zip download.",
            "Drag and drop the .bin file onto your SD card.",
        ]
    },
    {
        "heading": "Install on the monitor",
        "items": [
            "Remove the SD card from your computer.",
            "Insert the SD card into your SmallHD monitor.",
            "Turn on the monitor.",
            "Swipe/toggle left, or tap the screen to access the Settings Menu.",
            "Scroll down and tap FIRMWARE.",
            "Tap the available firmware, then follow the prompts to begin the update.",
            "Once complete, hold the power button for at least 5 seconds to reboot.",
            "Press the power button again to start using the updated firmware.",
            "CAUTION: Do not lose power during the firmware update.",
        ]
    },
]

entry = {
    "manufacturer": "SmallHD",
    "product": "PageOS",
    "version": "6.3.0",
    "release_date": "2026-01-16",
    "release_precision": "day",
    "status": "firmware_available",
    "source_url": "https://downloads.smallhd.com/firmware/smallhdos/6.3.0",
    "firmware_url": "https://downloads.smallhd.com/firmware/smallhdos/6.3.0",
    "firmware_kind": "page",
    "notes_url": None,
    "archive_url": None,
    "summary": "Shared firmware for all current SmallHD monitors.",
    "compatible_monitors": MONITORS,
    "changelog": CHANGELOG,
    "install": INSTALL,
    "install_version": "6.3.0",
    "install_source": "https://guide.smallhd.com/a/1810433-firmware",
}

with open("smallhd.json", "w") as f:
    json.dump([entry], f, indent=2, ensure_ascii=False)
print("Wrote smallhd.json")

# ---- 2. Patch build_feed.py ----
TARGET = "build_feed.py"
with open(TARGET) as f:
    original = f.read()

try:
    ast.parse(original)
except SyntaxError as e:
    print("build_feed.py has a syntax error: %s" % e)
    sys.exit(1)

if "smallhd.json" in original:
    print("build_feed.py already loads smallhd.json, skipping.")
else:
    ANCHOR = '# Cameras without a direct file but with a source page'
    if ANCHOR not in original:
        print("Cannot find anchor in build_feed.py")
        sys.exit(1)

    SECTION = (
        '# ---- SmallHD ----\n'
        '# SmallHD ships one firmware (PageOS) for all current monitors.\n'
        '# The compatible_monitors list goes into the search haystack so\n'
        '# typing a monitor name finds the firmware entry.\n'
        'try:\n'
        '    with open("smallhd.json") as f:\n'
        '        for row in json.load(f):\n'
        '            feed.append(row)\n'
        'except FileNotFoundError:\n'
        '    print("smallhd.json not found, skipping SmallHD")\n'
        '\n'
    )

    patched = original.replace(ANCHOR, SECTION + ANCHOR, 1)

    try:
        ast.parse(patched)
    except SyntaxError as e:
        print("Patched build_feed.py has a syntax error: %s" % e)
        sys.exit(1)

    shutil.copy2(TARGET, TARGET + ".bak")
    with open(TARGET, "w") as f:
        f.write(patched)
    print("Patched build_feed.py")

# ---- 3. Patch build_site.py ----
TARGET2 = "build_site.py"
with open(TARGET2) as f:
    original2 = f.read()

try:
    ast.parse(original2)
except SyntaxError as e:
    print("build_site.py has a syntax error: %s" % e)
    sys.exit(1)

changed2 = False
patched2 = original2

# 3a. Add SmallHD to EXPECTED_MAKES
OLD_MAKES = 'EXPECTED_MAKES = ["ARRI", "Sony", "RED"]'
NEW_MAKES = 'EXPECTED_MAKES = ["ARRI", "Sony", "RED", "SmallHD"]'
if "SmallHD" not in patched2:
    if OLD_MAKES in patched2:
        patched2 = patched2.replace(OLD_MAKES, NEW_MAKES, 1)
        changed2 = True
    else:
        print("Cannot find EXPECTED_MAKES in build_site.py")

# 3b. Add compatible_monitors to the search haystack in card()
# Find where haystack is built and add monitor names
OLD_HAYSTACK = '''    haystack = " ".join(str(part) for part in [
        name,
        make,
        cam.get("version") or "",
        cam.get("product") or "",
        (cam.get("release_date") or "")[:4],
    ]).lower()'''

NEW_HAYSTACK = '''    haystack = " ".join(str(part) for part in [
        name,
        make,
        cam.get("version") or "",
        cam.get("product") or "",
        (cam.get("release_date") or "")[:4],
        " ".join(cam.get("compatible_monitors") or []),
    ]).lower()'''

if "compatible_monitors" not in patched2:
    if OLD_HAYSTACK in patched2:
        patched2 = patched2.replace(OLD_HAYSTACK, NEW_HAYSTACK, 1)
        changed2 = True
    else:
        print("Cannot find haystack block in build_site.py")

# 3c. Add compatible monitors to panel payload
OLD_PAYLOAD_END = '''        "summary": cam.get("summary") or "",
        "links": links,
    }'''

NEW_PAYLOAD_END = '''        "summary": cam.get("summary") or "",
        "links": links,
        "monitors": cam.get("compatible_monitors") or [],
    }'''

if '"monitors"' not in patched2:
    if OLD_PAYLOAD_END in patched2:
        patched2 = patched2.replace(OLD_PAYLOAD_END, NEW_PAYLOAD_END, 1)
        changed2 = True

# 3d. Add compatible monitors rendering in the panel JS
OLD_RENDER_NEWS = '''    if (data.news && data.news.length) {'''

NEW_RENDER_MONITORS = '''    if (data.monitors && data.monitors.length) {
        html += "<details open><summary>Compatible monitors</summary>"
            + '<div class="inner"><ul class="lines">';
        data.monitors.forEach(function (m) {
            html += "<li>SmallHD " + esc(m) + "</li>";
        });
        html += "</ul></div></details>";
    }

    if (data.news && data.news.length) {'''

if "data.monitors" not in patched2:
    if OLD_RENDER_NEWS in patched2:
        patched2 = patched2.replace(OLD_RENDER_NEWS, NEW_RENDER_MONITORS, 1)
        changed2 = True

# 3e. Show compatible monitors as summary text on the card
OLD_SUMMARY = '''    summary = cam.get("summary")
    summary_html = ""
    if summary:
        short = summary if len(summary) < 190 else summary[:187].rstrip() + "..."
        summary_html = '<p class="sum">' + esc(short) + "</p>"'''

NEW_SUMMARY = '''    summary = cam.get("summary")
    monitors = cam.get("compatible_monitors") or []
    summary_html = ""
    if monitors:
        summary = (summary or "") + " Compatible: " + ", ".join(monitors) + "."
    if summary:
        short = summary if len(summary) < 190 else summary[:187].rstrip() + "..."
        summary_html = '<p class="sum">' + esc(short) + "</p>"'''

if "compatible_monitors" not in original2 or "Compatible:" not in patched2:
    if OLD_SUMMARY in patched2:
        patched2 = patched2.replace(OLD_SUMMARY, NEW_SUMMARY, 1)
        changed2 = True

if changed2:
    try:
        ast.parse(patched2)
    except SyntaxError as e:
        print("Patched build_site.py has a syntax error: %s" % e)
        sys.exit(1)

    shutil.copy2(TARGET2, TARGET2 + ".bak")
    with open(TARGET2, "w") as f:
        f.write(patched2)
    print("Patched build_site.py")
else:
    print("build_site.py already patched, skipping.")

print()
print("Next: python3 build_feed.py && python3 build_site.py")
