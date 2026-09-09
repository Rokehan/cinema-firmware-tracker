import urllib.request
import re
import json

url = "https://www.sony.jp/ls-camera/update/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

print("Fetching Sony index...")
raw = urllib.request.urlopen(req).read()

# Try encodings until the Japanese decodes cleanly
html = None
for enc in ["utf-8", "shift_jis", "cp932", "euc_jp"]:
    try:
        candidate = raw.decode(enc)
        if "ファームウェア" in candidate:
            html = candidate
            print("Encoding: " + enc)
            break
    except Exception:
        continue

if html is None:
    html = raw.decode("utf-8", errors="replace")
    print("Encoding: fallback")

text = re.sub(r"<[^>]+>", "|", html)
lines = [l.strip() for l in text.split("|") if l.strip()]

# Match "Ver. 5.00（2026年7月リリース）" AND bare "5.00（2026年7月リリース）"
VERSION = re.compile(r"^(?:Ver\.\s*)?(\d+\.\d+)\s*[（(](\d{4})年(\d{1,2})月")

results = []
for i, line in enumerate(lines):
    m = VERSION.match(line)
    if not m:
        continue

    product = lines[i - 1] if i > 0 else None
    category = lines[i - 2] if i > 1 else None

    # Strip Sony's suffix: "VENICE 2用機器アップデートファームウェア" -> "VENICE 2"
    name = product
    if name:
        name = re.split(r"用機器|用ファームウェア|アップデートファームウェア", name)[0].strip()

    results.append({
        "manufacturer": "Sony",
        "product": name,
        "product_raw": product,
        "category_raw": category,
        "version": "V" + m.group(1),
        "release_year": int(m.group(2)),
        "release_month": int(m.group(3)),
        "source_url": url,
    })

print("Found " + str(len(results)) + " entries")
print()
for r in results:
    date = str(r["release_year"]) + "-" + str(r["release_month"]).zfill(2)
    print("  " + str(r["product"])[:30].ljust(30) + r["version"].ljust(9) + date)

with open("sony_index.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print()
print("Saved to sony_index.json")