import urllib.request
import re
import json
import time

INDEX = "https://www.sony.jp/ls-camera/update/"

CAMERAS = [
    "VENICE 2", "VENICE", "BURANO", "PMW-F55", "PMW-F5",
    "FX9", "FR7", "FS7 II", "PXW-FS7", "PXW-FS5",
    "FX6", "FX3(ILME-FX3)", "FX3(ILME-FX3A)", "FX2", "FX30",
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req).read()
    for enc in ["utf-8", "shift_jis", "cp932", "euc_jp"]:
        try:
            c = raw.decode(enc)
            if "ファームウェア" in c or "firmware" in c.lower():
                return c
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")

def absolute(href):
    if href.startswith("http"):
        return href
    return "https://www.sony.jp" + href

def chunks(fragment):
    t = re.sub(r"<[^>]+>", "|", fragment)
    return [c.strip() for c in t.split("|") if c.strip()]

print("Fetching Sony index...")
html = fetch(INDEX)

VERSION = re.compile(r"(?:Ver\.\s*)?(\d+\.\d+)\s*[（(](\d{4})年(\d{1,2})月")

entries = []
for m in VERSION.finditer(html):
    before = chunks(html[max(0, m.start() - 800):m.start()])
    if not before:
        continue
    name = re.split(r"用機器|用ファームウェア|アップデートファームウェア", before[-1])[0].strip()
    if name not in CAMERAS:
        continue
    if any(e["product"] == name for e in entries):
        continue

    link = re.search(r'<a[^>]+href="([^"]+)"', html[m.end():m.end() + 1200])
    entries.append({
        "manufacturer": "Sony",
        "product": name,
        "version": "V" + m.group(1),
        "year": int(m.group(2)),
        "month": int(m.group(3)),
        "page_url": absolute(link.group(1)) if link else None,
        "firmware_url": None,
        "notes_url": None,
    })

# Warn about anything on the index we don't recognise, so a new body
# gets noticed instead of silently vanishing.
KNOWN_NON_CAMERAS = ["OCELLUS", "AXS", "CBK", "XDCA", "NEX"]
unknown = []
for m in VERSION.finditer(html):
    before = chunks(html[max(0, m.start() - 800):m.start()])
    if not before:
        continue
    name = re.split(r"用機器|用ファームウェア|アップデートファームウェア", before[-1])[0].strip()
    if not name or name in CAMERAS or name in unknown:
        continue
    if any(p in name for p in KNOWN_NON_CAMERAS):
        continue
    if name.startswith("Ver.") or "--" in name or "<" in name:
        continue
    unknown.append(name)

print("Cameras matched: " + str(len(entries)))
if unknown:
    print()
    print("*** UNKNOWN PRODUCTS on Sony's index ***")
    for u in unknown:
        print("  " + u)
    print("If any is a camera, add it to the CAMERAS list.")
print()

for e in entries:
    if not e["page_url"]:
        print("  " + e["product"].ljust(18) + "no page link")
        continue

    print("Fetching: " + e["product"])
    try:
        page = fetch(e["page_url"])
    except Exception as err:
        print("      failed: " + str(err)[:60])
        continue

    for href, raw in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.DOTALL):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
        if "リリースノート" in label and not e["notes_url"]:
            e["notes_url"] = absolute(href)

    # Firmware zips sit in the raw HTML, not always inside a link tag
    zips = re.findall(r'https?://[^"\'<>\s]+\.zip', page, re.I)
    if zips:
        e["firmware_url"] = zips[0]

    print("      fw: " + ("yes" if e["firmware_url"] else "NO")
          + "   notes: " + ("yes" if e["notes_url"] else "NO"))
    time.sleep(1)

with open("sony_cameras.json", "w") as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)

print()
got = len([e for e in entries if e["firmware_url"]])
print("Firmware links: " + str(got) + " of " + str(len(entries)))
print("Saved to sony_cameras.json")