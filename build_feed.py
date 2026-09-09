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

feed = []

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
            "notes_url": row.get("release_notes_download"),
            "archive_url": row.get("archive_url"),
        })

# ---- Sony ----
with open("sony_index.json") as f:
    for row in json.load(f):
        if row["product"] not in SONY_CAMERAS:
            continue
        feed.append({
            "manufacturer": "Sony",
            "product": row["product"],
            "version": row["version"],
            "release_date": str(row["release_year"]) + "-" + str(row["release_month"]).zfill(2),
            "release_precision": "month",
            "status": "firmware_available",
            "source_url": row["source_url"],
            "firmware_url": None,
            "notes_url": None,
            "archive_url": None,
        })

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