import urllib.request
import re

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

TARGETS = [
    ("VENICE", "https://www.sony.jp/ls-camera/update/VENICE.html"),
    ("FX9", "https://www.sony.jp/ls-camera/update/pxw-fx9.html"),
    ("FR7", "https://support.d-imaging.sony.co.jp/www/cscs/firm/?mdl=ILME-FR7&area=jp&lang="),
]

for name, url in TARGETS:
    print("========== " + name + " ==========")
    try:
        page = fetch(url)
    except Exception as err:
        print("  failed: " + str(err)[:70])
        print()
        continue

    print("  " + str(len(page)) + " characters")

    # Every link that looks like a real file, no truncation
    files = []
    for href, raw in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.DOTALL):
        if re.search(r"\.(zip|exe|dmg|pdf)", href, re.I) or "download" in href.lower():
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
            files.append((label, href))

    print("  file-ish links: " + str(len(files)))
    for label, href in files:
        print("    " + label[:40].ljust(42) + href[:70])

    # Any .zip anywhere in the HTML, even outside an <a> tag
    zips = re.findall(r'https?://[^"\'<>\s]+\.zip', page, re.I)
    print("  raw .zip URLs: " + str(len(set(zips))))
    for z in list(set(zips))[:5]:
        print("    " + z[:90])
    print()