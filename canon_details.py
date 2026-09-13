#!/usr/bin/env python3
"""canon_details.py  --  Enrich Canon entries with changelog + install steps.

Reads:  canon_cameras.json
Writes: canon_details.json

Source: Canon US firmware notice pages (product advisories).
"""

import json, re, sys, time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

DEBUG = "--debug" in sys.argv

HEADERS = {
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
}

ADVISORY_BASE = "https://www.usa.canon.com/support/canon-product-advisories"
DELAY = 2.0

# ── Firmware notice URL patterns ───────────────────────────────────
# Canon US advisory URLs are wildly inconsistent. We try several
# patterns per model and take the first 200 response.

# Explicit slug overrides for quirky URLs
NOTICE_SLUGS = {
    "EOS C700 FF":         ["eos-c700ff"],
    "EOS C700 PL":         ["eos-c700-and-eos-c700pl", "eos-c700-pl"],
    "EOS C200":            ["eos-c200--eos-c200b", "eos-c200"],
    "EOS C200B":           ["eos-c200--eos-c200b"],
    "EOS C300 Mark II PL": ["eos-c300-mark-ii--eos-c300-mark-ii-pl", "eos-c300-mark-ii-pl"],
    "EOS C500":            ["eos-c500--eos-c500-pl-cinema-eos-cinema", "eos-c500"],
    "EOS C500 PL":         ["eos-c500--eos-c500-pl-cinema-eos-cinema", "eos-c500-pl"],
}


def model_to_slug(display):
    """Auto-generate URL slug from model display name."""
    s = display.lower()
    s = s.replace(" mark iii", "-mark-iii")
    s = s.replace(" mark ii", "-mark-ii")
    s = s.replace(" gs pl", "-gs-pl")
    s = s.replace(" ", "-")
    return s


def build_notice_urls(model_name, version):
    """Generate candidate firmware notice URLs."""
    v = version.replace(".", "-")
    slugs = list(NOTICE_SLUGS.get(model_name, []))
    auto = model_to_slug(model_name)
    if auto not in slugs:
        slugs.append(auto)

    urls = []
    for slug in slugs:
        # lowercase, no trailing 00
        urls.append(f"{ADVISORY_BASE}/firmware-notice-{slug}-firmware-version-{v}")
        # lowercase, trailing -00
        urls.append(f"{ADVISORY_BASE}/firmware-notice-{slug}-firmware-version-{v}-00")
        # with "canon-digital-cinema-camera" prefix (newer cameras)
        urls.append(f"{ADVISORY_BASE}/firmware-notice-canon-digital-cinema-camera-{slug}-firmware-version-{v}")
        # Capitalized (some older pages use this)
        parts = slug.split("-")
        cap = "-".join(p.upper() if p in ("eos", "pl", "gs", "ff") else p.capitalize() for p in parts)
        urls.append(f"{ADVISORY_BASE}/Firmware-Notice-{cap}-Firmware-Version-{v}")

    # Version with only major.minor.patch (no 4th segment) for some edge cases
    segs = version.split(".")
    if len(segs) >= 4:
        v3 = "-".join(segs[:3])
        for slug in slugs[:2]:
            urls.append(f"{ADVISORY_BASE}/firmware-notice-{slug}-firmware-version-{v3}")

    return urls


# ── Notice page parsing ────────────────────────────────────────────

def try_fetch_notice(urls, label=""):
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
    return None, None


def parse_notice(html):
    """Extract changelog and install caution from a firmware notice page."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=chr(10))

    # ── Changelog ──
    changelog = ""

    # Pattern: "incorporates the following ... :\n 1. ...\n 2. ..."
    m = re.search(
        r"(?:incorporates|includes)\s+the\s+following[^:]*:\s*\n((?:\s*\d+\..*(?:\n|$))+)",
        text, re.I,
    )
    if m:
        changelog = m.group(1).strip()

    # Fallback: numbered list right after "Version X.X.X.X"
    if not changelog:
        m = re.search(
            r"Version\s+\d[\d.]+[^:]*:\s*\n((?:\s*\d+\..*(?:\n|$))+)",
            text, re.I,
        )
        if m:
            changelog = m.group(1).strip()

    # Clean: collapse whitespace, trim lines
    if changelog:
        lines = [ln.strip() for ln in changelog.split(chr(10)) if ln.strip()]
        changelog = chr(10).join(lines)

    # ── Install caution ──
    install = ""

    m = re.search(
        r"Caution:\s*\n((?:\s*[-\u2022\u25cf].*(?:\n|$))+)",
        text, re.I,
    )
    if m:
        install = m.group(1).strip()

    if not install:
        # Try "Preparations for" block
        m = re.search(
            r"Preparations\s+for.*?:\s*\n((?:\s*[-\u2022\u25cf\d].*(?:\n|$))+)",
            text, re.I,
        )
        if m:
            install = m.group(1).strip()

    if install:
        lines = [ln.strip() for ln in install.split(chr(10)) if ln.strip()]
        install = chr(10).join(lines)

    return changelog, install


# ── Main ───────────────────────────────────────────────────────────

def enrich(camera):
    model = camera["model"]
    version = camera["version"]
    print(f"{chr(10)}{model} v{version}")

    urls = build_notice_urls(model, version)
    print(f"  Trying {len(urls)} URL patterns...")

    html, found = try_fetch_notice(urls, label=model)

    if html:
        print(f"  Found: {found}")
        cl, inst = parse_notice(html)
        camera["changelog"] = cl
        camera["install_steps"] = inst
        camera["release_notes_url"] = found
        print(f"  Changelog: {len(cl)} chars | Install: {len(inst)} chars")
        if DEBUG:
            Path(f"debug_notice_{model.replace(' ', '_')}.html").write_text(html)
    else:
        print(f"  WARNING: no notice page found")
        camera["changelog"] = ""
        camera["install_steps"] = ""
        camera["release_notes_url"] = ""

    # Enrich previous versions (limit attempts to save time)
    for pv in camera.get("previous_versions", [])[:5]:
        pv_urls = build_notice_urls(model, pv["version"])[:6]
        time.sleep(DELAY)
        pv_html, pv_found = try_fetch_notice(pv_urls, label=f"{model} prev")
        if pv_html:
            pv_cl, _ = parse_notice(pv_html)
            pv["changelog"] = pv_cl
            pv["release_notes_url"] = pv_found
        else:
            pv["changelog"] = ""
            pv["release_notes_url"] = ""


def main():
    inp = Path("canon_cameras.json")
    if not inp.exists():
        print("ERROR: canon_cameras.json not found. Run canon_cameras.py first.")
        sys.exit(1)

    cameras = json.loads(inp.read_text())
    print(f"Loaded {len(cameras)} cameras")

    for cam in cameras:
        time.sleep(DELAY)
        enrich(cam)

    out = Path("canon_details.json")
    out.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"{chr(10)}Wrote enriched data to {out}")


if __name__ == "__main__":
    main()
