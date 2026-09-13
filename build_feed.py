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


# ── english_extras precedence ─────────────────────────────────────
# sony_english.py finds the English changelog and install steps, which is what
# it is for. It also used to report a firmware_url, scraped with a regex that
# matched the page's own <link rel="stylesheet">, and because the Sony rows
# spread english_extras LAST that asset overwrote real BODYDATA.DAT urls from
# sony_fx.json and sony_alpha.json. Nine cameras ended up sharing one
# Salesforce asset id.
#
# So the English side no longer decides where the file is. A download url from
# it survives only if it looks like a firmware file; otherwise the Japanese
# side, which is the authority, keeps its own.

_EN_DOWNLOAD_KEYS = ("firmware_url", "firmware_kind", "file_size", "file_name")

_EN_FILE_EXTS = (".zip", ".dat", ".fir", ".exe", ".dmg", ".pkg", ".bin",
                 ".tar.gz", ".tgz")

_EN_ASSET_MARKS = ("/articleimage", "/articleimages", ".css", ".js", ".svg",
                   ".png", ".jpg", ".woff", "/styles/")


def _en_url_is_file(url):
    if not url:
        return False
    low = str(url).lower()
    if any(mark in low for mark in _EN_ASSET_MARKS):
        return False
    path = low.split("?", 1)[0]
    return any(path.endswith(ext) for ext in _EN_FILE_EXTS)


def en_extras_safe(product):
    """english_extras() without its download fields, unless they are real."""
    extras = english_extras(product) or {}
    url = extras.get("firmware_url")
    if not _EN_URL_OK(url):
        for key in _EN_DOWNLOAD_KEYS:
            extras.pop(key, None)
    return extras


def _EN_URL_OK(url):
    return _en_url_is_file(url)


ARRI_ARCHIVE = {}
try:
    with open("arri_archive.json") as f:
        for row in json.load(f):
            ARRI_ARCHIVE[row["slug"]] = row
except FileNotFoundError:
    pass


def arri_prev(row):
    """Previous ARRI SUP versions.

    Prefers arri_archive.py's scrape of the camera's own SUP archive page,
    which carries the real firmware package and the release notes PDF per
    version. Falls back to the release-notes labels in all_downloads for
    ALEXA and ALEXA XT, the two bodies ARRI publishes no archive for.

    Order is ARRI's page order, not date order: the teaser footer date is the
    asset upload date and runs out of sequence, while the page lists true
    release order.

    "cl" stays empty. ARRI's per-version changelog lives inside the release
    notes PDF and nothing here reads PDF text, so a summary would be invented.
    """
    arc = ARRI_ARCHIVE.get(row.get("slug"))
    if arc and arc.get("versions"):
        out = []
        for v in arc["versions"]:
            label = v.get("version") or ""
            note = (v.get("note") or "").strip()
            if note:
                label = label + " " + note
            out.append({
                "v": label,
                "d": v.get("date") or v.get("date_text") or None,
                "cl": [],
                "dl": v.get("package_url") or v.get("notes_url") or None,
                "dl_kind": v.get("package_kind") or "page",
                "notes": v.get("notes_url") or None,
                "size": v.get("notes_size") or None,
            })
        return out

    import re as _re
    notes = [d for d in (row.get("all_downloads") or []) if d["kind"] == "release_notes"]
    prev = []
    for n in notes[1:]:
        hit = _re.search(r"SUP\s+([\d.]+)", n["label"])
        if hit:
            prev.append({"v": "SUP " + hit.group(1), "d": n.get("date"), "cl": [], "dl": n["url"]})
    return prev


# ── equipment categories ──────────────────────────────────────────
# Brand and category are independent facets, not a hierarchy: Teradek makes
# transmitters and monitors, ARRI makes cameras, viewfinders and lens control.
# Nesting either way would force duplication, so both live on the record.
CATEGORIES = [
    "Cameras",
    "Monitors",
    "Wireless Video",
    "Lens Control",
    "Viewfinders",
    "Stabilizers",
    "Mounts",
    "Audio",
    "Power & Media",
]


def categorise(entry):
    """The category for one feed row, from its own data.

    A row that already declares a category keeps it, so each maker script can
    name its own without touching this. SmallHD publishes a monitor
    compatibility list, which identifies it. Everything else in the feed today
    is a camera body.
    """
    named = (entry.get("category") or "").strip()
    if named:
        return named
    if entry.get("compatible_monitors"):
        return "Monitors"
    return "Cameras"


# ── download link guard ───────────────────────────────────────────
# A Download button must deliver a file. Nine Sony rows once shared one
# Salesforce id on an /articleimage/ path that served the page's stylesheet, so
# a URL now has to look like a file before it is offered as one. Anything else
# is downgraded to a page link, which is honest and gets the arrow.

FILE_HOSTS = (
    "download.pro.sony",
    "support.d-imaging.sony.co.jp",
    "gdlp01.c-wss.com",
    "gdlp02.c-wss.com",
    "pdisp01.c-wss.com",
    "arri.canto.de",
    "downloads.red.com",
)

FILE_EXTS = (".zip", ".dat", ".fir", ".exe", ".dmg", ".pkg", ".bin",
             ".tar.gz", ".tgz", ".sit")

# path fragments that mean "page asset", never firmware
ASSET_MARKS = ("/articleimage", "/articleimages", "/resource/css",
               "/styles/", "/static/css", ".css", ".js", ".svg", ".png",
               ".jpg", ".jpeg", ".gif", ".woff")


def looks_like_file(url):
    """True when the URL's own shape says it serves a firmware file."""
    if not url:
        return False
    low = str(url).lower()
    if any(mark in low for mark in ASSET_MARKS):
        return False
    path = low.split("?", 1)[0]
    if any(path.endswith(ext) for ext in FILE_EXTS):
        return True
    if any(host in low for host in FILE_HOSTS):
        return True
    return False


def guard_downloads(rows):
    """Downgrade any file link that does not look like a file.

    Also rejects a URL claimed by more than one product: a shared link is how
    the stylesheet bug showed itself, and no two cameras share a firmware file.
    """
    counts = {}
    for row in rows:
        if row.get("firmware_kind") == "file" and row.get("firmware_url"):
            counts[row["firmware_url"]] = counts.get(row["firmware_url"], 0) + 1

    fixed = 0
    for row in rows:
        if row.get("firmware_kind") != "file":
            continue
        url = row.get("firmware_url")
        if not url:
            continue
        why = ""
        if not looks_like_file(url):
            why = "not a file url"
        elif counts.get(url, 0) > 1:
            why = "url shared by " + str(counts[url]) + " products"
        if not why:
            continue
        page = row.get("source_url") or row.get("notes_url")
        row["firmware_url"] = page
        row["firmware_kind"] = "page" if page else None
        row["file_name"] = None
        row["file_size"] = None
        fixed += 1
        print("  download guard: " + str(row.get("manufacturer")) + " "
              + str(row.get("product")) + " -> page (" + why + ")")
    return fixed


# ── ARRI kit previous versions ────────────────────────────────────
# arri_kit_archive.py reads each accessory's own SUP archive page, the same
# structure the camera archives use. Changelogs stay empty because ARRI keeps
# per-version detail inside the release notes PDF.
KIT_ARCHIVE = {}
try:
    with open("arri_kit_archive.json") as f:
        KIT_ARCHIVE = json.load(f)
except FileNotFoundError:
    pass


def kit_prev(row):
    """Previous versions for one accessory, in ARRI's own page order."""
    entry = KIT_ARCHIVE.get(row.get("slug") or "") or {}
    out = []
    for v in entry.get("versions") or []:
        label = v.get("version") or ""
        note = (v.get("note") or "").strip()
        if note:
            label = label + " " + note
        out.append({
            "v": label,
            "d": v.get("date") or v.get("date_text") or None,
            "cl": [],
            "dl": v.get("package_url") or v.get("notes_url") or None,
            "dl_kind": v.get("package_kind") or "page",
            "notes": v.get("notes_url") or None,
            "size": v.get("notes_size") or None,
        })
    return out


# ── Canon install steps and history from Canon Singapore ──────────
# Canon US publishes no Caution or Preparations block for the current Cinema
# EOS bodies. Canon SG does, in English, and adds a History section with
# per-version changelogs. sg_crawl.py collected 38 pages covering 6 bodies.
# Windows and macOS are separate pages for the same firmware, so the first is
# used and its platform is recorded.
SG_BY_MODEL = {}
try:
    with open("sg_issues.json") as f:
        for row in json.load(f):
            key = (row.get("model") or "").strip()
            if not key:
                continue
            SG_BY_MODEL.setdefault(key, []).append(row)
except FileNotFoundError:
    pass


def sg_for(product):
    """The SG record for this body, preferring one that has install steps."""
    rows = SG_BY_MODEL.get((product or "").strip()) or []
    if not rows:
        return None
    with_steps = [r for r in rows if r.get("install")]
    return (with_steps or rows)[0]


def sg_install(product):
    """Canon's own Caution and Preparations blocks, verbatim, or nothing."""
    rec = sg_for(product)
    if not rec:
        return {}
    blocks = []
    for b in rec.get("install") or []:
        items = [i for i in (b.get("items") or []) if i]
        if items:
            blocks.append({"heading": b.get("heading") or "", "items": items})
    if not blocks:
        return {}
    return {
        "install": blocks,
        # SG can document an older version than Canon US ships. Name the
        # version these steps were published for rather than implying they
        # describe the current one.
        "install_version": rec.get("install_version") or rec.get("version"),
        "install_source": rec.get("install_source") or rec.get("url"),
    }


def sg_history(product):
    """version -> changelog list, from SG's History section."""
    rec = sg_for(product)
    if not rec:
        return {}
    out = {}
    for h in rec.get("history") or []:
        ver = (h.get("version") or "").strip()
        items = [i for i in (h.get("changelog") or []) if i]
        if ver and items:
            out[ver] = items
    return out


def canon_prev_with_history(product, prevs):
    """Fill empty previous-version changelogs from SG's History."""
    hist = sg_history(product)
    if not hist:
        return prevs
    for p in prevs:
        if p.get("cl"):
            continue
        key = str(p.get("v") or "").strip()
        if key in hist:
            p["cl"] = hist[key]
    return prevs


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
            **en_extras_safe(row["product"]),
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
                "install": steps or sg_install(row["model"]).get("install") or [],
                "install_version": row["version"] if steps
                else sg_install(row["model"]).get("install_version"),
                "install_source": notes if steps
                else sg_install(row["model"]).get("install_source"),
                "previous_versions": canon_prev_with_history(
                    row["model"], canon_prev(row)),
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
                **en_extras_safe(row["product"]),
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
        **en_extras_safe(meta["display"]),
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

# ---- ARRI kit that is not a camera ----
# arri_kit.py reads ARRI's ECS, monitor and stabilizer firmware sections. Its
# rows are already feed shaped and carry their own category, so no guessing
# happens here. ARRI serves ECS firmware as .cmf renamed to -data.txt by their
# CMS, and arri_kit.py records the real type in file_type.
try:
    with open("arri_kit.json") as f:
        for row in json.load(f):
            feed.append({
                "manufacturer": "ARRI",
                "category": row.get("category") or "Lens Control",
                "product": row["product"],
                "version": row["version"],
                "release_date": row.get("release_date"),
                "release_precision": row.get("release_precision") or "day",
                "status": row.get("status") or "firmware_available",
                "source_url": row.get("source_url"),
                "firmware_url": row.get("firmware_url") or row.get("source_url"),
                "firmware_kind": row.get("firmware_kind") or "page",
                "notes_url": row.get("notes_url") or None,
                "archive_url": row.get("archive_url") or None,
                "summary": row.get("summary") or None,
                "changelog": row.get("changelog") or [],
                "features": [],
                "install": [],
                "install_version": None,
                "install_source": None,
                "previous_versions": kit_prev(row),
                "guides": row.get("guides") or [],
                "file_name": None,
                "file_size": row.get("file_size") or None,
                "file_type": row.get("file_type") or None,
            })
except FileNotFoundError:
    print("arri_kit.json not found, skipping ARRI accessories")

# ---- Teradek ----
# teradek.py reads update.teradek.com/wares.php, the same api the Teradek
# downloads page calls. Rows are feed shaped and carry their own category.
# Their firmware_url is a download.php link to a real .bin, and companion
# software such as Bolt Manager rides along in guides rather than pretending
# to be firmware.
try:
    with open("teradek.json") as f:
        for row in json.load(f):
            feed.append({
                "manufacturer": "Teradek",
                "category": row.get("category") or "Wireless Video",
                "product": row["product"],
                "version": row["version"],
                "release_date": row.get("release_date"),
                "release_precision": row.get("release_precision") or "day",
                "status": row.get("status") or "firmware_available",
                "source_url": row.get("source_url"),
                "firmware_url": row.get("firmware_url") or row.get("source_url"),
                "firmware_kind": row.get("firmware_kind") or "page",
                "notes_url": row.get("notes_url") or None,
                "archive_url": None,
                "summary": row.get("summary") or None,
                "changelog": row.get("changelog") or [],
                "features": [],
                "install": row.get("install") or [],
                "install_version": row.get("install_version"),
                "install_source": row.get("install_source"),
                "previous_versions": row.get("previous_versions") or [],
                "guides": row.get("guides") or [],
                "file_name": None,
                "file_size": row.get("file_size") or None,
            })
except FileNotFoundError:
    print("teradek.json not found, skipping Teradek")

# Cameras without a direct file but with a source page get a
# page-type download link so the Download button appears.
for entry in feed:
    if not entry.get("firmware_url") and entry.get("source_url"):
        entry["firmware_url"] = entry["source_url"]
        entry["firmware_kind"] = "page"

# every row carries its category, so the UI can filter on brand and category
# independently
for entry in feed:
    entry["category"] = categorise(entry)

n = guard_downloads(feed)
if n:
    print("download guard: " + str(n)
          + " link(s) downgraded to a page, they did not serve a file")

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