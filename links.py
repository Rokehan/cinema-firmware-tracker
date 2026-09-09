import urllib.request
import re

req = urllib.request.Request("https://www.sony.jp/ls-camera/update/",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req).read().decode("shift_jis", errors="replace")

for href, raw in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
    label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
    if "ダウンロード" in label:
        print(href)