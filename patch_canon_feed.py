#!/usr/bin/env python3
"""
patch_canon_feed.py  -  adds the Canon block to build_feed.py.

Safe to run twice. Writes build_feed.py.bak. Refuses to save if the result
does not parse.

Translates canon_cameras.json's own shape into feed shape:
    model             -> product
    date              -> release_date
    changelog (str)   -> changelog (list of items, verbatim)
    install_steps     -> install (list of {heading, items}, verbatim)
    download_url      -> firmware_url, with firmware_kind "page"
    previous_versions -> v / d / cl / dl, the shape arri_prev() returns

Nothing is invented: every item is Canon's own text, only re-split.
"""
from pathlib import Path
import ast
import sys

NL = chr(10)
TARGET = Path("build_feed.py")

ANCHOR = 'print("red_cameras.json not found, skipping RED")'

BLOCK = r'''
# ---- Canon ----
# canon_cameras.py writes its own shape: one changelog string, one install
# string, "model" instead of "product". Canon's firmware table is JS-rendered
# and the rendition XML is Akamai 403, so the download link opens Canon's own
# support page. firmware_kind "page" reuses the same Download arrow the Sony
# and RED page links already render, and state_of() then reports
# "Firmware + notes" for the 21 bodies that have a notice.
CANON_HEADINGS = [
    "How to check the firmware version",
    "Preparations", "Preparation",
    "Required items", "Items required",
    "Procedures", "Procedure",
    "How to update",
    "Cautions", "Caution",
    "Notes", "Note",
]


def canon_items(text):
    """Canon prose as a list of items. Verbatim, only re-split."""
    if not text:
        return []
    parts = [p.strip() for p in str(text).split(chr(10))]
    parts = [p for p in parts if p]
    if len(parts) == 1:
        one = parts[0]
        bits = re.split(r"\s+-\s+", one)
        if len(bits) < 2:
            bits = re.split(r"(?<=[.)])\s+(?=\d+[.)]\s)", one)
        parts = bits
    out = []
    for p in parts:
        p = p.strip().lstrip("-").strip()
        if p:
            out.append(p)
    return out


def canon_install(text):
    """Canon install steps as {heading, items} blocks, quoted verbatim.

    Canon writes "Caution:", "Preparations:" and so on inline. Anything
    before the first heading becomes an unheaded block rather than being
    dropped, and with no heading at all the whole text stays one block. That
    is honest: rule 5 wants the manufacturer's words, not a tidy shape.
    """
    if not text:
        return []
    body = str(text)
    rx = re.compile("(" + "|".join(CANON_HEADINGS) + r")\s*:", re.I)
    marks = list(rx.finditer(body))
    chunks = []
    lead = body[:marks[0].start()] if marks else body
    if lead.strip():
        chunks.append(("", lead))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        chunks.append((m.group(1), body[m.end():end]))
    blocks = []
    for heading, chunk in chunks:
        items = canon_items(chunk)
        if items:
            blocks.append({"heading": heading, "items": items})
    return blocks


def canon_prev(row):
    """Previous Canon versions, the same v/d/cl/dl shape as arri_prev().

    "dl" prefers the version's own notice page, matching ARRI, where the
    previous-version link is the release notes rather than a file. Canon's
    download_url is the model page and is identical for every version, so it
    is only a fallback.
    """
    out = []
    for p in row.get("previous_versions") or []:
        out.append({
            "v": p.get("version"),
            "d": p.get("date"),
            "cl": canon_items(p.get("changelog")),
            "dl": p.get("release_notes_url") or p.get("download_url"),
        })
    return out


try:
    with open("canon_cameras.json") as f:
        for row in json.load(f):
            notes = row.get("release_notes_url") or None
            steps = canon_install(row.get("install_steps"))
            feed.append({
                "manufacturer": "Canon",
                "product": row["model"],
                "version": row["version"],
                "release_date": row.get("date"),
                "release_precision": "day",
                "status": "firmware_available"
                if row.get("download_url") else "documentation_only",
                "source_url": row.get("source_url"),
                "firmware_url": row.get("download_url") or row.get("source_url"),
                "firmware_kind": "page"
                if row.get("download_opens_page") else "file",
                "notes_url": notes,
                "archive_url": None,
                "summary": None,
                "changelog": canon_items(row.get("changelog")),
                "features": [],
                "install": steps,
                "install_version": row["version"] if steps else None,
                "install_source": notes if steps else None,
                "previous_versions": canon_prev(row),
                "file_name": None,
                "file_size": None,
            })
except FileNotFoundError:
    print("canon_cameras.json not found, skipping Canon")
'''


def main():
    if not TARGET.exists():
        sys.exit("build_feed.py not found in " + str(Path.cwd()))

    src = TARGET.read_text(encoding="utf-8")

    if "canon_cameras.json" in src:
        print("Already applied: build_feed.py already loads canon_cameras.json")
        print("Nothing to do.")
        return

    if ANCHOR not in src:
        sys.exit("Anchor not found. Expected this line in build_feed.py:" + NL
                 + "    " + ANCHOR)

    at = src.index(ANCHOR) + len(ANCHOR)
    tail = src[at:]
    cut = tail.index(NL) + 1 if NL in tail else len(tail)
    out = src[:at] + tail[:cut] + BLOCK + tail[cut:]

    try:
        ast.parse(out)
    except SyntaxError as exc:
        sys.exit("Refusing to save: result would not parse: " + str(exc))

    Path("build_feed.py.bak").write_text(src, encoding="utf-8")
    TARGET.write_text(out, encoding="utf-8")

    print("Backup: build_feed.py.bak")
    print()
    print("applied: Canon block added after the RED block")
    print("  model -> product, date -> release_date")
    print("  changelog string -> list of items")
    print("  install_steps string -> {heading, items} blocks")
    print("  firmware_kind = page, so the existing Download arrow applies")
    print("  previous_versions -> v/d/cl/dl, same shape as arri_prev()")
    print()
    print("check_changes.py needs no change: it keys on manufacturer +")
    print("product, not on counts, so 22 new Canon rows are just NEW CAMERAS.")
    print("build_site.py needs no change: the arrow already renders for")
    print("firmware_kind == 'page' and Canon is already in EXPECTED_MAKES.")
    print()
    print("Now run: python build_feed.py")


if __name__ == "__main__":
    main()
