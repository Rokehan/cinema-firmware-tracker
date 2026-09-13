#!/usr/bin/env python3
"""fix_canon_403.py  --  Patch canon_cameras.py to defeat Canon WAF 403s.

Upgrades headers to full Chrome fingerprint + adds curl subprocess fallback.
Safe to run twice.
"""

import shutil, sys
from pathlib import Path

target = Path("canon_cameras.py")
if not target.exists():
    print("ERROR: canon_cameras.py not found in current directory")
    sys.exit(1)

bak = target.with_suffix(".py.bak")
shutil.copy2(target, bak)
print(f"Backup: {bak}")

src = target.read_text()

# ── 1. Replace HEADERS with full Chrome fingerprint ────────────

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
    print("Patched HEADERS to full Chrome fingerprint")
else:
    print("HEADERS already patched or not found (skipping)")

# ── 2. Replace fetch() with requests+curl fallback ─────────────

old_fetch = '''def fetch(url, label=""):
    """GET with retry."""
    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(DELAY * (attempt + 1))
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  [{label}] attempt {attempt + 1} failed: {e}")
    return None'''

new_fetch = '''def fetch(url, label=""):
    """GET with retry: requests first, curl fallback."""
    import subprocess
    # Attempt 1-2: requests with full headers
    for attempt in range(2):
        try:
            if attempt > 0:
                time.sleep(DELAY * (attempt + 1))
            s = requests.Session()
            s.headers.update(HEADERS)
            r = s.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  [{label}] requests attempt {attempt + 1} failed: {e}")
    # Attempt 3: curl with impersonation headers
    try:
        time.sleep(DELAY * 2)
        cmd = [
            "curl", "-s", "-L",
            "--max-time", "30",
            "--compressed",
            "-H", "User-Agent: " + HEADERS["User-Agent"],
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: en-US,en;q=0.9",
            "-H", "Accept-Encoding: gzip, deflate, br",
            "-H", "Sec-Ch-Ua: " + chr(34) + "Not/A)Brand" + chr(34) + ";v=" + chr(34) + "8" + chr(34),
            "-H", "Sec-Fetch-Dest: document",
            "-H", "Sec-Fetch-Mode: navigate",
            "-H", "Sec-Fetch-Site: none",
            "-H", "Upgrade-Insecure-Requests: 1",
            "-H", "Connection: keep-alive",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.returncode == 0 and len(result.stdout) > 500:
            print(f"  [{label}] curl fallback succeeded ({len(result.stdout)} bytes)")
            return result.stdout
        else:
            print(f"  [{label}] curl returned {result.returncode}, {len(result.stdout)} bytes")
    except Exception as e:
        print(f"  [{label}] curl fallback failed: {e}")
    return None'''

if old_fetch in src:
    src = src.replace(old_fetch, new_fetch)
    print("Patched fetch() with curl fallback")
else:
    print("fetch() already patched or not found (skipping)")

# ── Validate and save ──────────────────────────────────────────

try:
    compile(src, "canon_cameras.py", "exec")
except SyntaxError as e:
    print(f"SYNTAX ERROR after patching: {e}")
    print("Restoring backup...")
    shutil.copy2(bak, target)
    sys.exit(1)

target.write_text(src)
print(f"Saved patched {target}")
print("Now run: python canon_cameras.py --debug")
