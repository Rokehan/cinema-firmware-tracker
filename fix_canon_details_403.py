#!/usr/bin/env python3
"""fix_canon_details_403.py  --  Patch canon_details.py with same anti-WAF fixes.

Safe to run twice.
"""

import shutil, sys
from pathlib import Path

target = Path("canon_details.py")
if not target.exists():
    print("ERROR: canon_details.py not found in current directory")
    sys.exit(1)

bak = target.with_suffix(".py.bak")
shutil.copy2(target, bak)
print(f"Backup: {bak}")

src = target.read_text()

# ── 1. Replace HEADERS ────────────────────────────────────────

old_headers = '''HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}'''

new_headers = '''HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": chr(34) + "Not/A)Brand" + chr(34) + ";v=" + chr(34) + "8" + chr(34) + ", " + chr(34) + "Chromium" + chr(34) + ";v=" + chr(34) + "126" + chr(34) + ", " + chr(34) + "Google Chrome" + chr(34) + ";v=" + chr(34) + "126" + chr(34),
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": chr(34) + "Windows" + chr(34),
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}'''

if old_headers in src:
    src = src.replace(old_headers, new_headers)
    print("Patched HEADERS")
else:
    print("HEADERS already patched (skipping)")

# ── 2. Replace try_fetch_notice with curl fallback ─────────────

old_try = '''def try_fetch_notice(urls, label=""):
    """Try candidate URLs, return (html, url) for first success."""
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            if r.status_code == 200 and "Firmware" in r.text[:5000]:
                return r.text, url
        except Exception:
            pass
        time.sleep(0.3)
    return None, None'''

new_try = '''def try_fetch_notice(urls, label=""):
    """Try candidate URLs with requests, then curl fallback."""
    import subprocess
    s = requests.Session()
    s.headers.update(HEADERS)
    for url in urls:
        try:
            r = s.get(url, timeout=30, allow_redirects=True)
            if r.status_code == 200 and "Firmware" in r.text[:5000]:
                return r.text, url
        except Exception:
            pass
        time.sleep(0.3)
    # curl fallback: try first 4 URLs
    for url in urls[:4]:
        try:
            cmd = [
                "curl", "-s", "-L",
                "--max-time", "30",
                "--compressed",
                "-H", "User-Agent: " + HEADERS["User-Agent"],
                "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "-H", "Accept-Language: en-US,en;q=0.9",
                "-H", "Sec-Fetch-Dest: document",
                "-H", "Sec-Fetch-Mode: navigate",
                "-H", "Connection: keep-alive",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if result.returncode == 0 and "Firmware" in result.stdout[:5000]:
                print(f"  [{label}] curl got {url}")
                return result.stdout, url
        except Exception:
            pass
        time.sleep(0.3)
    return None, None'''

if old_try in src:
    src = src.replace(old_try, new_try)
    print("Patched try_fetch_notice() with curl fallback")
else:
    print("try_fetch_notice() already patched (skipping)")

# ── Validate and save ──────────────────────────────────────────

try:
    compile(src, "canon_details.py", "exec")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    shutil.copy2(bak, target)
    sys.exit(1)

target.write_text(src)
print(f"Saved patched {target}")
