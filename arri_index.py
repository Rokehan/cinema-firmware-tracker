"""Shared reader for ARRI's combined firmware index.

In autumn 2026 ARRI replaced its per-section firmware indexes (cameras, ECS,
monitors, CSS) with one page, "Overview of all current Software Update
Packages". The old section URLs now redirect there, and every product page
moved under the same path. This module reads that page once, groups product
links under ARRI's own section headings, and keeps ARRI's index title (for
example "ALEXA 35 SUP 6.2.0") so the pipeline can cross-check versions.

Nothing is constructed: every slug and title comes from ARRI's page. An index
that yields no sections raises, so a layout change fails loudly instead of
silently publishing an empty brand.
"""
import html as htmlmod
import json
import re
import subprocess
import urllib.request

SITE = "https://www.arri.com"
PREFIX = "/en/technical-service/firmware/overview-of-all-current-software-update-packages"
INDEX_URL = SITE + PREFIX
PAGE_BASE = INDEX_URL + "/"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_CACHE = {}


def _fetch(url):
    try:
        out = subprocess.run(
            ["curl", "-s", "-L", "--compressed", "--max-time", "60",
             "-H", "User-Agent: " + UA,
             "-H", "Accept-Language: en-US,en;q=0.9", url],
            capture_output=True, text=True, timeout=75)
        if out.returncode == 0 and len(out.stdout) > 2000:
            return out.stdout
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def _text(fragment):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(htmlmod.unescape(t).split())


def sections(html=None):
    """{ARRI section heading: [{"slug", "title", "date"}]} in page order."""
    if html is None:
        html = _CACHE.get("index")
        if html is None:
            html = _fetch(INDEX_URL)
            _CACHE["index"] = html
    heads = list(re.finditer(
        r'<h2[^>]*class="[^"]*ci-section-title[^"]*"[^>]*>(.*?)</h2>',
        html, re.S | re.I))
    out = {}
    link_rx = re.compile(r'<a[^>]+href="' + re.escape(PREFIX)
                         + r'/([^"/?#]+)"[^>]*>(.*?)</a>', re.S | re.I)
    for i, head in enumerate(heads):
        name = _text(head.group(1))
        end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
        items = []
        for m in link_rx.finditer(html, head.end(), end):
            slug = m.group(1)
            if "archive" in slug.lower():
                continue
            body = m.group(2)
            tm = re.search(r'teaser-item__title[^>]*>(.*?)</', body, re.S)
            dm = re.search(r'teaser-item__subTitle[^>]*>(.*?)</div>', body, re.S)
            items.append({
                "slug": slug,
                "title": _text(tm.group(1)) if tm else _text(body),
                "date": _text(dm.group(1)) if dm else "",
            })
        if name and items:
            out[name] = items
    if not out:
        raise RuntimeError("ARRI index at " + INDEX_URL
                           + " has no recognisable sections. Layout changed?")
    return out


def slugs(section_name, html=None):
    """Unique slugs under one ARRI heading, in ARRI's order."""
    found = sections(html).get(section_name)
    if found is None:
        raise RuntimeError("ARRI index has no '" + section_name + "' section")
    seen = []
    for item in found:
        if item["slug"] not in seen:
            seen.append(item["slug"])
    return seen


def version_numbers(text):
    m = re.search(r"(\d+(?:\.\d+)+)", str(text or ""))
    return m.group(1) if m else None


if __name__ == "__main__":
    for name, items in sections().items():
        print(name)
        for it in items:
            print("  " + it["slug"].ljust(58) + it["title"])
