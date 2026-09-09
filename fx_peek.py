import urllib.request
import re
import json

print("=== FX6 captured content ===")
for r in json.load(open("sony_fx.json")):
    if r["product"] == "FX6":
        print("summary: " + str(r.get("summary")))
        print()
        for f in r.get("features") or []:
            print("  - " + f)

print()
print("=== FX30 page: how does it mark the version? ===")
url = "https://support.sony.jp/electronics/support/software/00378860"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
page = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")

for kw in ["公開日", "リリース", "releaseDate", "アップデート内容"]:
    hits = [m.start() for m in re.finditer(kw, page)]
    print(kw + ": " + str(len(hits)) + " hits")
    if hits:
        s = hits[0]
        chunk = re.sub(r"<[^>]+>", " ", page[s:s + 500])
        chunk = chunk.replace(chr(92) + "n", " ").replace(chr(92) + "t", " ")
        print("    " + re.sub(r"\s+", " ", chunk)[:320])
    print()