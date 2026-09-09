import urllib.request
import re
import json
import time

PAGES = {
    "FX6": "https://support.sony.jp/electronics/support/software/00378932",
    "FX3(ILME-FX3)": "https://support.sony.jp/electronics/support/software/00378858",
    "FX3(ILME-FX3A)": "https://support.sony.jp/electronics/support/software/00378859",
    "FX30": "https://support.sony.jp/electronics/support/software/00378860",
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req).read()
    for enc in ["utf-8", "shift_jis", "cp932"]:
        try:
            c = raw.decode(enc)
            if "バージョン" in c or "Ver." in c:
                return c
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")

results = []

for name, url in PAGES.items():
    print("Fetching: " + name)
    page = fetch(url)

    version = None
    date = None

    # These pages embed JSON: "name":"... Ver. 6.01","releaseDate":"Tue, 17 Mar 2026..."
    m = re.search(r'"name"\s*:\s*"([^"]*?Ver\.\s*([\d.]+))"\s*,\s*"releaseDate"\s*:\s*"([^"]+)"', page)
    if m:
        version = "V" + m.group(2)
        d = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", m.group(3))
        if d:
            months = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                      "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                      "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
            date = d.group(3) + "-" + months.get(d.group(2), "01") + "-" + d.group(1).zfill(2)

    # Fallback: the older prose format
    if not version:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
        m2 = re.search(r"Ver\.\s*([\d.]+)\s*[（(]公開日[：:]\s*(\d{4}-\d{2}-\d{2})", text)
        if m2:
            version = "V" + m2.group(1)
            date = m2.group(2)

    # Sony's JP pages don't publish changelogs in a consistent scrapeable form.
    # Deliberately not extracted: one camera in fifteen isn't worth the upkeep.
    summary = None
    features = []
    changelog_version = None
    fname = re.search(r"([A-Z0-9_]+\.DAT)", page)

    results.append({
        "manufacturer": "Sony",
        "product": name,
        "version": version,
        "release_date": date,
        "page_url": url,
        "file_name": fname.group(1) if fname else None,
        "summary": summary,
        "features": features,
        "changelog_version": changelog_version,
    })

    print("      " + str(version) + "   " + str(date)
          + "   file: " + str(fname.group(1) if fname else "none"))
    time.sleep(1)

with open("sony_fx.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print()
print("Saved to sony_fx.json")