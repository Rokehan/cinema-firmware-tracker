import json
import re

SONY_CAMERAS = [
    "VENICE 2", "VENICE", "BURANO", "PMW-F55", "PMW-F5",
    "FX9", "FR7", "FS7 II", "PXW-FS7", "PXW-FS5",
    "FX6", "FX3(ILME-FX3)", "FX3(ILME-FX3A)", "FX2", "FX30",
]

MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

def arri_date(s):
    if not s:
        return None
    m = re.match(r"(\w{3})\.?\s+(\d{1,2}),\s+(\d{4})", s)
    if not m:
        return None
    return m.group(3) + "-" + MONTHS.get(m.group(1), "01") + "-" + m.group(2).zfill(2)

def arri_product(slug):
    name = slug.replace("-", " ").upper()
    name = re.sub(r"\s+SUP.*$", "", name)
    return name.replace("ALEXA", "ALEXA").strip()

EN_DETAILS = {}
try:
    with open("sony_english.json") as f:
        for row in json.load(f):
            EN_DETAILS[row["product"]] = row
except FileNotFoundError:
    pass


# feed product name -> sony_english.json key. Explicit, because loose
# matching once gave the FX3A the FX3's changelog: they are separate bodies
# on separate firmware tracks.
EN_ALIASES = {
    "FX3(ILME-FX3)": "FX3",
    "PXW-FX9": "FX9",
    "PXW-FS7 II": "FS7 II",
    "FS7 II": "FS7 II",
    "FX3 (ILME-FX3)": "FX3",
    "α7 V (ILCE-7M5)": "a7 V",
    "α7 IV (ILCE-7M4)": "a7 IV",
    "α7R V (ILCE-7RM5)": "a7R V",
    "α7S III (ILCE-7SM3)": "a7S III",
}


def english_extras(product):
    """Sony's English changelog and install steps for this body, if any.

    Only an exact name or a declared alias counts. An unmatched body gets
    nothing rather than a neighbour's instructions.
    """
    row = EN_DETAILS.get(product)
    if row is None:
        alias = EN_ALIASES.get(product)
        if alias:
            row = EN_DETAILS.get(alias)
    if row is None:
        return {}
    extras = {
        "changelog": row.get("changelog") or [],
        "install": row.get("install") or [],
        "file_name": row.get("file_name"),
        "install_version": row.get("version"),
        "install_source": row.get("source_url"),
        "guides": row.get("guides") or [],
        "source_url": row.get("source_url"),
    }
    if row.get("firmware_url"):
        extras["firmware_url"] = row["firmware_url"]
        extras["firmware_kind"] = "file"
    if row.get("previous_versions"):
        extras["previous_versions"] = row["previous_versions"]
    return extras


def arri_prev(row):
    """Previous ARRI SUP versions from the release notes list."""
    import re as _re
    notes = [d for d in (row.get("all_downloads") or []) if d["kind"] == "release_notes"]
    prev = []
    for n in notes[1:]:
        hit = _re.search(r"SUP\s+([\d.]+)", n["label"])
        if hit:
            prev.append({"v": "SUP " + hit.group(1), "d": n.get("date"), "cl": [], "dl": n["url"]})
    return prev

feed = []
# FX pages give exact dates, so they override the month-only index values
FX_OVERRIDE = {}
try:
    with open("sony_fx.json") as f:
        for row in json.load(f):
            if row.get("version"):
                FX_OVERRIDE[row["product"]] = row
except FileNotFoundError:
    pass
ARRI_INSTALL = {}
try:
    with open("arri_install.json") as f:
        for row in json.load(f):
            ARRI_INSTALL[row["slug"]] = row
except FileNotFoundError:
    pass


ARRI_DETAILS = {}
try:
    with open("arri_details.json") as f:
        for row in json.load(f):
            ARRI_DETAILS[row["slug"]] = row
except FileNotFoundError:
    pass
# ---- ARRI ----
with open("arri_cameras.json") as f:
    for row in json.load(f):
        feed.append({
            "manufacturer": "ARRI",
            "product": arri_product(row["slug"]),
            "version": row["version"],
            "release_date": arri_date(row["release_date"]),
            "release_precision": "day",
            "status": row["status"],
            "source_url": row["source_url"],
            "firmware_url": row.get("firmware_download"),
            "firmware_kind": "file",
            "notes_url": row.get("release_notes_download"),
            "archive_url": row.get("archive_url"),
            "summary": (ARRI_DETAILS.get(row["slug"]) or {}).get("summary"),
            "features": (ARRI_DETAILS.get(row["slug"]) or {}).get("features") or [],
            "install": (ARRI_INSTALL.get(row["slug"]) or {}).get("install") or [],
            "install_version": (ARRI_INSTALL.get(row["slug"]) or {}).get("install_version"),
            "install_source": (ARRI_INSTALL.get(row["slug"]) or {}).get("install_source"),
            "previous_versions": arri_prev(row),
            "file_name": (ARRI_INSTALL.get(row["slug"]) or {}).get("file_name"),
        })

# ---- Sony ----
with open("sony_cameras.json") as f:
    for row in json.load(f):
        fx = FX_OVERRIDE.get(row["product"])
        # sony_files.py resolves the real BODYDATA.DAT URL where Sony
        # publishes one. Absent, the support page stands in as before.
        fx_file = (fx or {}).get("firmware_url")
        feed.append({
            "manufacturer": "Sony",
            "product": row["product"],
            "version": fx["version"] if fx else row["version"],
            "release_date": fx["release_date"] if fx
                else str(row["year"]) + "-" + str(row["month"]).zfill(2),
            "release_precision": "day" if fx else "month",
            "status": "firmware_available"
                if (row.get("firmware_url") or fx) else "documentation_only",
            "source_url": fx["page_url"] if fx
                else (row.get("page_url") or "https://www.sony.jp/ls-camera/update/"),
            "firmware_url": row.get("firmware_url") or fx_file
            or (fx["page_url"] if fx else None),
            "firmware_kind": "file"
            if (row.get("firmware_url") or fx_file)
            else ("page" if fx else "file"),
            "file_size": (fx or {}).get("file_size"),
            "notes_url": row.get("notes_url"),
            "archive_url": None,
            **english_extras(row["product"]),
        })

# ---- RED ----
# red_cameras.py already writes feed-shaped rows. RED gates the file behind
# a login, so firmware_url points at RED's own page, not a direct download.
try:
    with open("red_cameras.json") as f:
        for row in json.load(f):
            feed.append({
                "manufacturer": "RED",
                "product": row["product"],
                "version": row["version"],
                "release_date": row["release_date"],
                "release_precision": row.get("release_precision") or "day",
                "status": row["status"],
                "source_url": row["source_url"],
                "firmware_url": row.get("firmware_url"),
                "firmware_kind": row.get("firmware_kind") or "page",
                "notes_url": row.get("notes_url"),
                "archive_url": None,
                "summary": row.get("summary"),
                "features": row.get("features") or [],
                "install": row.get("install") or [],
                "install_version": row.get("install_version"),
                "install_source": row.get("install_source"),
                "file_name": row.get("file_name"),
                "file_size": row.get("file_size"),
            })
except FileNotFoundError:
    print("red_cameras.json not found, skipping RED")

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

# ---- Sony Alpha bodies ----
# Stills-hybrid bodies that get used on cinema jobs. sony_alpha.py writes
# feed-shaped rows, including the real BODYDATA.DAT file URL where Sony
# publishes one.
try:
    with open("sony_alpha.json") as f:
        for row in json.load(f):
            feed.append({
                "manufacturer": "Sony",
                "product": row["product"],
                "version": row["version"],
                "release_date": row["release_date"],
                "release_precision": row.get("release_precision") or "day",
                "status": row["status"],
                "source_url": row["source_url"],
                "firmware_url": row.get("firmware_url"),
                "firmware_kind": row.get("firmware_kind") or "file",
                "notes_url": row.get("notes_url"),
                "archive_url": None,
                "summary": row.get("summary"),
                "features": row.get("features") or [],
                "file_size": row.get("file_size"),
                **english_extras(row["product"]),
            })
except FileNotFoundError:
    print("sony_alpha.json not found, skipping Sony Alpha bodies")

# ---- Sony EN-only bodies ----
# Some bodies have English firmware data but aren't listed on the Japanese
# site. Let sony_english.json contribute feed rows for those.
EN_ONLY_BODIES = {
    "a7R V": {
        "display": "α7R V (ILCE-7RM5)",
    },
}

existing_products = {r["product"] for r in feed}
for en_key, meta in EN_ONLY_BODIES.items():
    if meta["display"] in existing_products:
        continue
    row = EN_DETAILS.get(en_key)
    if row is None:
        continue
    feed.append({
        "manufacturer": "Sony",
        "product": meta["display"],
        "version": row.get("version"),
        "release_date": row.get("release_date"),
        "release_precision": "day" if len(row.get("release_date") or "") == 10 else "month",
        "status": "firmware_available" if row.get("version") else "documentation_only",
        "source_url": row.get("source_url") or "https://www.sony.com",
        "firmware_url": row.get("source_url"),
        "firmware_kind": "page",
        "file_size": row.get("file_size") or row.get("size"),
        "notes_url": None,
        "archive_url": None,
        **english_extras(meta["display"]),
    })

# ---- SmallHD ----
# SmallHD ships one firmware (PageOS) for all current monitors.
# The compatible_monitors list goes into the search haystack so
# typing a monitor name finds the firmware entry.
try:
    with open("smallhd.json") as f:
        for row in json.load(f):
            feed.append(row)
except FileNotFoundError:
    print("smallhd.json not found, skipping SmallHD")

# Cameras without a direct file but with a source page get a
# page-type download link so the Download button appears.
for entry in feed:
    if not entry.get("firmware_url") and entry.get("source_url"):
        entry["firmware_url"] = entry["source_url"]
        entry["firmware_kind"] = "page"

feed.sort(key=lambda r: (r["release_date"] or ""), reverse=True)

with open("feed.json", "w") as f:
    json.dump(feed, f, indent=2, ensure_ascii=False)

print("Feed: " + str(len(feed)) + " camera entries")
print()
for r in feed:
    print("  " + str(r["release_date"]).ljust(11)
          + r["manufacturer"].ljust(6)
          + str(r["product"])[:22].ljust(23)
          + str(r["version"]).ljust(10)
          + ("dl" if r["firmware_url"] else "--"))
print()
print("Saved to feed.json")