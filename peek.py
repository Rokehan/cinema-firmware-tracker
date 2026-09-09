import urllib.request
import re

req = urllib.request.Request("https://www.sony.jp/ls-camera/update/",
                             headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req).read()
html = raw.decode("shift_jis", errors="replace")

text = re.sub(r"<[^>]+>", "|", html)
lines = [l.strip() for l in text.split("|") if l.strip()]

for i, l in enumerate(lines):
    if l.startswith("FX6"):
        print(l)
        print("   -> " + lines[i + 1])