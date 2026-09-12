import urllib.request
import re
import json
import time

def discover_camera_pages():
    """Read the current camera list from ARRI's camera index every
    run, so version bumps and new bodies are picked up automatically.

    ARRI names some real camera pages '<body>-sup-overview' (ALEXA Mini,
    AMIRA), so only archive pages are skipped."""
    index = fetch(
        "https://www.arri.com/en/technical-service/firmware/software-and-firmware-updates-for-cameras"
    )
    pattern = (
        r'href="/en/technical-service/firmware/'
        r'software-and-firmware-updates-for-cameras/([^"/]+)"'
    )
    slugs = []
    for slug in re.findall(pattern, index):
        if slug in slugs:
            continue
        if "archive" in slug.lower():
            continue
        slugs.append(slug)
    return slugs

BASE = "https://www.arri.com/en/technical-service/firmware/software-and-firmware-updates-for-cameras/"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode("utf-8")

def classify(label):
    low = label.lower()
    if "release note" in low:
        return "release_notes"
    if "user manual" in low or "pocket guide" in low or "setting chart" in low or "overview" in low or "tools" in low:
        return "documentation"
    if "pdf |" in low:
        return "documentation"
    return "firmware"

def find_date(label):
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),\s+(\d{4})", label)
    return m.group(0) if m else None

def find_version(slug, html, downloads):
    # 1. Best source: the URL slug, e.g. alexa-mini-lf-sup-7-3-2
    m = re.search(r"sup-(\d+(?:-\d+)*)$", slug)
    if m:
        return "SUP " + m.group(1).replace("-", ".")
    # 2. Next: the page title
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
    if t:
        v = re.search(r"SUP\s+([\d.]+)", t.group(1))
        if v:
            return "SUP " + v.group(1).rstrip(".")
    # 3. Last resort: highest version seen in the download labels
    found = []
    for d in downloads:
        v = re.search(r"SUP\s+([\d.]+)", d["label"])
        if v:
            found.append(v.group(1).rstrip("."))
    if found:
        best = sorted(found, key=lambda s: [int(p) for p in s.split(".")])[-1]
        return "SUP " + best
    return None

LONG_MONTHS = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov",
    "december": "Dec",
}

SHORT_MONTHS = ("Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec")

LONG_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})",
    re.I,
)

SHORT_DATE_RE = re.compile(
    r"(" + SHORT_MONTHS + r")\.?\s+(\d{1,2}),\s*(\d{4})"
)


def visible_text(fragment):
    """Tags out, entities and runs of whitespace tidied."""
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", fragment).strip()


def headline_version_and_date(html):
    """Read the version and release date straight off ARRI's own headline.

    Returns (version, date) with either value None when the page does not
    state it. The date comes back as "Feb. 7, 2022" to match the format the
    rest of the pipeline already expects.
    """
    heads = list(re.finditer(r"(?is)<h1[^>]*>(.*?)</h1>", html))
    if not heads:
        return None, None

    chosen = None
    for head in heads:
        if "sup" in visible_text(head.group(1)).lower():
            chosen = head
            break
    if chosen is None:
        chosen = heads[-1]

    title = visible_text(chosen.group(1))

    version = None
    found = re.search(r"SUP\s+(\d+(?:\.\d+)*)", title, re.I)
    if found:
        version = "SUP " + found.group(1).rstrip(".")

    # ARRI prints the release date immediately below the headline.
    window = visible_text(html[chosen.end():chosen.end() + 4000])[:400]

    date = None
    long_hit = LONG_DATE_RE.search(window)
    if long_hit:
        month = LONG_MONTHS.get(long_hit.group(1).lower())
        if month:
            date = month + ". " + str(int(long_hit.group(2))) + ", " + long_hit.group(3)
    if date is None:
        short_hit = SHORT_DATE_RE.search(window)
        if short_hit:
            date = (short_hit.group(1) + ". " + str(int(short_hit.group(2)))
                    + ", " + short_hit.group(3))

    return version, date


results = []
CAMERA_PAGES = discover_camera_pages()
print("Discovered " + str(len(CAMERA_PAGES)) + " camera pages")
print()
for slug in CAMERA_PAGES:
    url = BASE + slug
    print("Fetching: " + slug)
    html = fetch(url)

    anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)

    downloads = []
    archive = None
    seen = set()

    for href, raw in anchors:
        label = re.sub(r"<[^>]+>", " ", raw)
        label = re.sub(r"\s+", " ", label).strip()
        full = href if href.startswith("http") else "https://www.arri.com" + href

        if ("archive" in href.lower() or "archive" in label.lower()) and not archive:
            archive = full
            continue

        is_file = "crblob" in href or "canto.de" in href or re.search(r"\.(zip|pdf|exe|dmg|gz|pkg|sup)$", href, re.I)
        if not is_file or not label or full in seen:
            continue
        seen.add(full)

        downloads.append({
            "kind": classify(label),
            "label": label,
            "date": find_date(label),
            "url": full,
        })

    firmware = [d for d in downloads if d["kind"] == "firmware"]
    notes = [d for d in downloads if d["kind"] == "release_notes"]

    head_version, head_date = headline_version_and_date(html)

    fallback_date = firmware[0]["date"] if firmware else (
        notes[0]["date"] if notes else None)
    release_date = head_date or fallback_date
    version = head_version or find_version(slug, html, downloads)
    status = "firmware_available" if firmware else "documentation_only"

    entry = {
        "manufacturer": "ARRI",
        "category": "Cameras",
        "slug": slug,
        "version": version,
        "status": status,
        "release_date": release_date,
        "source_url": url,
        "archive_url": archive,
        "firmware_download": firmware[0]["url"] if firmware else None,
        "release_notes_download": notes[0]["url"] if notes else None,
        "all_downloads": downloads,
    }
    results.append(entry)

    print("  Version: " + str(version))
    print("  Release date: " + str(release_date))
    print("  Firmware pkg: " + ("yes" if firmware else "NO"))
    print("  Release notes: " + ("yes" if notes else "NO"))
    print("  Docs: " + str(len([d for d in downloads if d["kind"] == "documentation"])))
    print()
    if not firmware:
        print("  --- no firmware package, listing all links ---")
        for d in downloads:
            print("    [" + d["kind"] + "] " + d["label"][:70])
    time.sleep(1)

with open("arri_cameras.json", "w") as f:
    json.dump(results, f, indent=2)

print("Saved to arri_cameras.json")