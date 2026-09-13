#!/usr/bin/env python3
"""canon_cameras.py  --  Canon Cinema EOS firmware for the tracker.

Uniform path, identical for every camera:

  1. usa.canon.com/support/canon-product-advisories   (index, fetched once)
       -> every Cinema EOS firmware notice: model, version, release date,
          and the notice page URL
  2. each notice page
       -> "What's new" changelog, "How to install" steps
  3. usa.canon.com/support/service-and-repair/pro-firmware  (fetched once)
       -> extra version history for pre-2019 bodies. This archive stopped
          being updated in Nov 2019, so it holds nothing for the current
          lineup; it only deepens legacy history.

Download button
  Canon builds the firmware download table client-side from an internal
  API, so no direct pdisp01.c-wss.com file link is reachable without a
  browser. The button therefore points at the model's own support page and
  is flagged download_opens_page=true, which is the arrow case in rule 3.

Everything over curl: requests gets 403'd by Canon's WAF.
Canon US only, English throughout. Nothing is invented; every field comes
from a Canon page and every record carries its source URL.

Output: canon_cameras.json
Flags:  --debug          save intermediates
        --only <substr>  process just the matching camera(s)
"""

import json, re, subprocess, sys, time
from pathlib import Path
from bs4 import BeautifulSoup

DEBUG = "--debug" in sys.argv
ONLY = None
if "--only" in sys.argv:
    _k = sys.argv.index("--only")
    if _k + 1 < len(sys.argv):
        ONLY = sys.argv[_k + 1].lower()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

BASE = "https://www.usa.canon.com"
ADVISORY_INDEX = BASE + "/support/canon-product-advisories"
PRO_FW_URL = BASE + "/support/service-and-repair/pro-firmware"
DELAY = 0.8

# ── Catalogue ─────────────────────────────────────────────────────
# slug:      Canon US support page slug (source + download button)
# match:     regex claiming advisory notices for this body
# pro_names: names in the legacy pro-firmware archive
# major:     restrict to this leading version (Dual Pixel AF variants)

CINEMA_EOS = [
    {"display": "EOS C500 Mark II",  "slug": "eos-c500-mark-ii",
     "match": r"C500\s*Mark\s*II",              "pro_names": ["EOS C500 Mark II"]},
    {"display": "EOS C400",          "slug": "eos-c400",
     "match": r"EOS\s*C400\b",                  "pro_names": ["EOS C400"]},
    {"display": "EOS C300 Mark III", "slug": "eos-c300-mark-iii",
     "match": r"C300\s*Mark\s*III",             "pro_names": ["EOS C300 Mark III"]},
    {"display": "EOS C80",           "slug": "eos-c80",
     "match": r"EOS\s*C80\b",                   "pro_names": ["EOS C80"]},
    {"display": "EOS C70",           "slug": "eos-c70",
     "match": r"EOS\s*C70\b",                   "pro_names": ["EOS C70"]},
    {"display": "EOS C50",           "slug": "eos-c50",
     "match": r"EOS\s*C50\b",                   "pro_names": ["EOS C50"]},
    {"display": "EOS C700",          "slug": "eos-c700",
     "match": r"C700(?!\s*(?:GS|FF|PL))",       "pro_names": ["EOS C700"]},
    {"display": "EOS C700 PL",       "slug": "eos-c700-pl",
     "match": r"C700\s*PL|C700PL",              "pro_names": ["EOS C700 PL", "EOS C700PL"]},
    {"display": "EOS C700 GS PL",    "slug": "eos-c700-gs-pl",
     "match": r"C700\s*GS\s*PL",                "pro_names": ["EOS C700 GS PL"]},
    {"display": "EOS C700 FF",       "slug": "eos-c700-ff",
     "match": r"C700\s*FF|C700FF",              "pro_names": ["EOS C700 FF", "EOS C700FF"]},
    {"display": "EOS C300 Mark II",  "slug": "eos-c300-mark-ii",
     "match": r"C300\s*Mark\s*II\b(?!\s*PL)",   "pro_names": ["EOS C300 Mark II"]},
    {"display": "EOS C300 Mark II PL", "slug": "eos-c300-mark-ii-pl",
     "match": r"C300\s*Mark\s*II\s*PL",         "pro_names": ["EOS C300 Mark II PL"]},
    {"display": "EOS C200",          "slug": "eos-c200",
     "match": r"C200\b(?!B)",                   "pro_names": ["EOS C200"]},
    {"display": "EOS C200B",         "slug": "eos-c200b",
     "match": r"C200B",                         "pro_names": ["EOS C200B"]},
    {"display": "EOS C300",          "slug": "eos-c300",
     "match": r"EOS\s*C300(?!\s*(?:Mark|PL))",  "pro_names": ["EOS C300"], "major": 1},
    {"display": "EOS C300 (Dual Pixel AF)", "slug": "eos-c300",
     "match": r"EOS\s*C300(?!\s*(?:Mark|PL))",
     "pro_names": ["EOS C300 with Dual Pixel AF"], "major": 2},
    {"display": "EOS C300 PL",       "slug": "eos-c300-pl",
     "match": r"C300\s*PL(?!.*Mark)",           "pro_names": ["EOS C300 PL"], "major": 1},
    {"display": "EOS C100 Mark II",  "slug": "eos-c100-mark-ii",
     "match": r"C100\s*Mark\s*II",              "pro_names": ["EOS C100 Mark II", "C100 MarkII"]},
    {"display": "EOS C100",          "slug": "eos-c100",
     "match": r"EOS\s*C100\b(?!\s*Mark)",       "pro_names": ["EOS C100"], "major": 1},
    {"display": "EOS C100 (Dual Pixel AF)", "slug": "eos-c100",
     "match": r"EOS\s*C100\b(?!\s*Mark)",
     "pro_names": ["EOS C100 (with Dual Pixel CMOS AF Feature Upgrade applied)",
                   "EOS C100 DAF"], "major": 2},
    {"display": "EOS C500",          "slug": "eos-c500",
     "match": r"EOS\s*C500(?!\s*(?:Mark|PL))",  "pro_names": ["EOS C500"]},
    {"display": "EOS C500 PL",       "slug": "eos-c500-pl",
     "match": r"C500\s*PL",                     "pro_names": ["EOS C500 PL"]},
]

# ── HTTP ──────────────────────────────────────────────────────────

def curl(url, timeout=45):
    """Fetch a URL with curl. Returns (body, ok)."""
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout), "--compressed",
           "-w", "%{http_code}",
           "-H", "User-Agent: " + UA,
           "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "-H", "Accept-Language: en-US,en;q=0.9",
           "-H", "Sec-Fetch-Dest: document",
           "-H", "Sec-Fetch-Mode: navigate",
           "-H", "Connection: keep-alive",
           url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        b = r.stdout
        if len(b) >= 3:
            code, body = b[-3:], b[:-3]
            return body, (code == "200" and len(body) > 500)
        return "", False
    except Exception as e:
        print("      curl error: " + str(e))
        return "", False

# ── version / date helpers ────────────────────────────────────────

def normalize_version(v):
    """Cinema EOS versions are 4-part.

    Canon writes '1.0.7.1.00' on some pages and appends a page-duplicate
    suffix on others ('1-0-3-1-001'), so any 5th component is dropped.
    """
    p = [x for x in v.split(".") if x != ""]
    if len(p) >= 5:
        return ".".join(p[:4])
    return ".".join(p)

def version_tuple(s):
    return tuple(int(x) for x in s.split(".") if x.isdigit())

def date_us(text):
    """'10.16.20' or '07/14/2020' -> '2020-10-16'. Rejects impossible dates."""
    for m in re.finditer(r"(\d{2})[./](\d{2})[./](\d{2,4})", text):
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        if len(yy) == 2:
            yy = "20" + yy
        if 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31 and 2005 <= int(yy) <= 2035:
            return yy + "-" + mm + "-" + dd
    return ""

def version_from_text(t):
    t = t.replace("-", ".")
    m = re.search(r"[Vv]ersion[.\s]+(\d+(?:\.\d+){1,4})", t)
    if m:
        return normalize_version(m.group(1))
    m = re.search(r"(\d+\.\d+\.\d+\.\d+(?:\.00)?)", t)
    if m:
        return normalize_version(m.group(1))
    return None

# ── Step 1: advisory index -> notices ──────────────────────────────

def discover_notices():
    print("Scraping advisory index...")
    html, ok = curl(ADVISORY_INDEX)
    if not ok:
        print("  FAILED: no notices, changelogs will be empty")
        return []

    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "canon-product-advisories/" not in href:
            continue
        slug = href.rstrip("/").split("/")[-1]
        if "firmware" not in slug.lower():
            continue
        full = href if href.startswith("http") else \
            BASE + ("" if href.startswith("/") else "/") + href
        title = a.get_text(" ", strip=True)
        blob = title + " " + slug
        if not re.search(r"C\d{2,3}", blob, re.I):
            continue
        ver = version_from_text(title) or version_from_text(slug)
        if not ver:
            continue
        date = ""
        i = html.find(href)
        if i != -1:
            win = re.sub(r"<[^>]+>", " ", html[max(0, i - 900): i + 900])
            date = date_us(win)
        if full not in found:
            found[full] = {"title": title or slug, "url": full,
                           "version": ver, "date": date}

    print("  " + str(len(found)) + " Cinema EOS firmware notices")
    if DEBUG:
        Path("debug_notices.json").write_text(
            json.dumps(list(found.values()), indent=2, ensure_ascii=False))
    return list(found.values())

# ── legacy archive ────────────────────────────────────────────────

def fetch_pro_firmware():
    print("Fetching legacy pro-firmware archive...")
    html, ok = curl(PRO_FW_URL)
    if not ok:
        print("  FAILED (legacy history will be thinner)")
        return {}
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return {}
    out = {}
    for row in table.find_all("tr"):
        c = row.find_all(["td", "th"])
        if len(c) < 3:
            continue
        name = c[0].get_text(strip=True)
        ver = c[1].get_text(strip=True)
        if not re.search(r"EOS C\d|^C100", name):
            continue
        if not re.match(r"^\d+(\.\d+)+$", ver):
            continue
        out.setdefault(name, []).append(
            {"version": normalize_version(ver),
             "date": date_us(c[2].get_text(strip=True))})
    for k in out:
        out[k].sort(key=lambda e: version_tuple(e["version"]), reverse=True)
    print("  " + str(len(out)) + " models in archive")
    return out

# ── Step 2: notice page -> changelog + install ────────────────────

def split_numbered(blob):
    parts = re.split(r"(?=(?:^|\s)\d{1,2}\.\s)", blob)
    items = [p.strip() for p in parts if p.strip()]
    return chr(10).join(items) if len(items) > 1 else blob.strip()

# A bare "Support" must NEVER be a boundary here: Canon changelogs
# sometimes open with that word, e.g. the C200 entry reads
# "Support for the separately-sold LCD Monitor LM-V2 has been added."
STOP = (r"(?=\s*(?:Caution\s*:|Preparations\s+for|"
        r"Support\s+Download\s+Firmware|Download\s+Firmware\s+Version|"
        r"If\s+you\s+have\s+not\s+already|"
        r"If\s+the\s+camera(?:'s)?\s+firmware\s+is\s+already|"
        r"This\s+information\s+is\s+for\s+residents|Thank\s+you,|"
        r"Regarding\s+the\s+Software|Q&As|History\s*:|"
        r"The\s+following\s+items\s+are\s+required|"
        r"To\s+help\s+obtain\s+optimal|Please\s+perform\s+the\s+firmware|$))")

TAIL = (r"(?=\s*(?:Support\s+Download\s+Firmware|Download\s+Firmware\s+Version|"
        r"Thank\s+you,|This\s+information\s+is\s+for|Regarding\s+the\s+Software|"
        r"History\s*:|$))")

def parse_notice(html):
    """Return (date, changelog, install_steps)."""
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()
    flat = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    date = date_us(flat[:4000])

    changelog = ""
    m = re.search(r"(?:incorporates|includes|contains)\s+the\s+following[^:]{0,90}:\s*"
                  r"(.{15,6000}?)" + STOP, flat, re.I)
    if not m:
        m = re.search(r"(?:Details\s+)?Firmware\s+[Vv]ersion\s+\d[\d.]+\s*"
                      r"(?:incorporates|includes|contains)?[^:]{0,90}:\s*"
                      r"(.{15,6000}?)" + STOP, flat, re.I)
    if m:
        changelog = split_numbered(m.group(1).strip())
        if re.match(r"^(?:for the EOS|Firmware Notice)", changelog, re.I):
            changelog = ""

    chunks = []
    for pat in (r"(Caution\s*:\s*.{20,4000}?)" + TAIL,
                r"(Preparations\s+for[^:]{0,60}:\s*.{20,4000}?)" + TAIL,
                r"(The\s+following\s+items\s+are\s+required[^:]{0,60}:\s*"
                r".{20,2000}?)" + TAIL):
        mm = re.search(pat, flat, re.I)
        if mm:
            chunks.append(split_numbered(mm.group(1).strip()))
    install = (chr(10) + chr(10)).join(chunks)

    return date, changelog, install

# ── sibling notice probing ────────────────────────────────────────
# The advisory index only lists recent notices, so current cameras arrive
# with little or no history. For each camera we already hold at least one
# notice URL that is confirmed to work; that URL becomes the template and
# only the version number is substituted. Every candidate is verified with
# a HEAD request and kept only on HTTP 200, so no version is ever invented.

PROBE_BUDGET = 34


def curl_status(url, timeout=12):
    """HEAD request. Returns the HTTP status code as an int."""
    cmd = ["curl", "-s", "-o", "/dev/null", "-I",
           "-w", "%{http_code}", "--max-time", str(timeout),
           "-H", "User-Agent: " + UA,
           "-H", "Accept: text/html",
           "-H", "Sec-Fetch-Dest: document",
           "-H", "Sec-Fetch-Mode: navigate",
           url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 6)
        s = r.stdout.strip()
        return int(s) if s.isdigit() else 0
    except Exception:
        return 0


def notice_template(url, version):
    """Turn a working notice URL into a template with {V} for the version."""
    vd = version.replace(".", "-")
    i = url.rfind(vd)
    if i == -1:
        return None
    return url[:i] + "{V}" + url[i + len(vd):]


def candidate_versions(known):
    """Plausible sibling versions, newest first, excluding known ones.

    Cinema EOS numbering is major.minor.patch.build, where Canon walks the
    patch digit and occasionally the minor. Candidates stay within the
    major and minor values Canon has actually used for this body.
    """
    if not known:
        return []
    tops = sorted((version_tuple(v) for v in known), reverse=True)
    top = tops[0]
    if len(top) < 4:
        return []
    major, minor, patch, build = top[0], top[1], top[2], top[3]
    out = []
    for mi in range(minor, -1, -1):
        hi = patch if mi == minor else 9
        for pa in range(hi, 0, -1):
            cand = str(major) + "." + str(mi) + "." + str(pa) + "." + str(build)
            if cand not in known and cand not in out:
                out.append(cand)
    return out


def probe_siblings(model, merged):
    """Add versions Canon actually serves a notice page for."""
    seed_url = ""
    seed_ver = ""
    for v in sorted(merged, key=version_tuple, reverse=True):
        if merged[v].get("notice_url"):
            seed_url = merged[v]["notice_url"]
            seed_ver = v
            break
    if not seed_url:
        return 0

    tpl = notice_template(seed_url, seed_ver)
    if not tpl:
        return 0

    cands = candidate_versions(set(merged.keys()))
    if not cands:
        return 0

    added = 0
    spent = 0
    for cand in cands:
        if spent >= PROBE_BUDGET:
            break
        urls = [tpl.replace("{V}", cand.replace(".", "-"))]
        if not tpl.rstrip("/").endswith("-00"):
            urls.append(tpl.replace("{V}", cand.replace(".", "-") + "-00"))
        for u in urls:
            spent += 1
            if curl_status(u) == 200:
                merged[cand] = {"version": cand, "date": "", "notice_url": u}
                added += 1
                print("      probe found v" + cand)
                break
            time.sleep(0.15)
    if spent:
        print("      probed " + str(spent) + " URL(s), added " + str(added))
    return added


# ── sibling notice probing ────────────────────────────────────────
# The advisory index only lists recent notices, so current cameras arrive
# with little or no history. For each camera we already hold at least one
# notice URL that is confirmed to work; that URL becomes the template and
# only the version number is substituted. Every candidate is verified with
# a HEAD request and kept only on HTTP 200, so no version is ever invented.

PROBE_BUDGET = 34


def curl_status(url, timeout=12):
    """HEAD request. Returns the HTTP status code as an int."""
    cmd = ["curl", "-s", "-o", "/dev/null", "-I",
           "-w", "%{http_code}", "--max-time", str(timeout),
           "-H", "User-Agent: " + UA,
           "-H", "Accept: text/html",
           "-H", "Sec-Fetch-Dest: document",
           "-H", "Sec-Fetch-Mode: navigate",
           url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 6)
        s = r.stdout.strip()
        return int(s) if s.isdigit() else 0
    except Exception:
        return 0


def notice_template(url, version):
    """Turn a working notice URL into a template with {V} for the version."""
    vd = version.replace(".", "-")
    i = url.rfind(vd)
    if i == -1:
        return None
    return url[:i] + "{V}" + url[i + len(vd):]


def candidate_versions(known):
    """Plausible sibling versions, newest first, excluding known ones.

    Cinema EOS numbering is major.minor.patch.build, where Canon walks the
    patch digit and occasionally the minor. Candidates stay within the
    major and minor values Canon has actually used for this body.
    """
    if not known:
        return []
    tops = sorted((version_tuple(v) for v in known), reverse=True)
    top = tops[0]
    if len(top) < 4:
        return []
    major, minor, patch, build = top[0], top[1], top[2], top[3]
    out = []
    for mi in range(minor, -1, -1):
        hi = patch if mi == minor else 9
        for pa in range(hi, 0, -1):
            cand = str(major) + "." + str(mi) + "." + str(pa) + "." + str(build)
            if cand not in known and cand not in out:
                out.append(cand)
    return out


def probe_siblings(model, merged):
    """Add versions Canon actually serves a notice page for."""
    seed_url = ""
    seed_ver = ""
    for v in sorted(merged, key=version_tuple, reverse=True):
        if merged[v].get("notice_url"):
            seed_url = merged[v]["notice_url"]
            seed_ver = v
            break
    if not seed_url:
        return 0

    tpl = notice_template(seed_url, seed_ver)
    if not tpl:
        return 0

    cands = candidate_versions(set(merged.keys()))
    if not cands:
        return 0

    added = 0
    spent = 0
    for cand in cands:
        if spent >= PROBE_BUDGET:
            break
        urls = [tpl.replace("{V}", cand.replace(".", "-"))]
        if not tpl.rstrip("/").endswith("-00"):
            urls.append(tpl.replace("{V}", cand.replace(".", "-") + "-00"))
        for u in urls:
            spent += 1
            if curl_status(u) == 200:
                merged[cand] = {"version": cand, "date": "", "notice_url": u}
                added += 1
                print("      probe found v" + cand)
                break
            time.sleep(0.15)
    if spent:
        print("      probed " + str(spent) + " URL(s), added " + str(added))
    return added


# ── assemble ──────────────────────────────────────────────────────

def claim(model, notices):
    pat = re.compile(model["match"], re.I)
    major = model.get("major")
    out = {}
    for n in notices:
        if pat.search(n["title"]) or pat.search(n["url"].replace("-", " ")):
            v = n["version"]
            if major is not None and not v.startswith(str(major) + "."):
                continue
            out.setdefault(v, n)
    return out

def claim_pro(model, pro):
    major = model.get("major")
    out = {}
    for pn in model.get("pro_names", []):
        for e in pro.get(pn, []):
            if major is not None and not e["version"].startswith(str(major) + "."):
                continue
            out.setdefault(e["version"], e)
    return out

def process(model, notices, pro):
    name = model["display"]
    print()
    print("=" * 64)
    print(name)

    nt = claim(model, notices)
    pf = claim_pro(model, pro)

    merged = {}
    for v, n in nt.items():
        merged[v] = {"version": v, "date": n["date"], "notice_url": n["url"]}
    for v, e in pf.items():
        if v in merged:
            if not merged[v]["date"]:
                merged[v]["date"] = e["date"]
        else:
            merged[v] = {"version": v, "date": e["date"], "notice_url": ""}

    if not merged:
        print("  WARNING: no versions found")
        return None

    probe_siblings(model, merged)

    order = sorted(merged, key=version_tuple, reverse=True)
    print("  versions: " + ", ".join(order[:10])
          + (" ..." if len(order) > 10 else ""))

    support_url = BASE + "/support/p/" + model["slug"]
    download_url = support_url + "?subtab=downloads-firmware"

    def build(v, deep):
        rec = merged[v]
        out = {"version": v, "date": rec["date"],
               "download_url": download_url,
               "download_opens_page": True,
               "release_notes_url": rec["notice_url"],
               "changelog": ""}
        if deep:
            out["install_steps"] = ""
        if rec["notice_url"]:
            html, ok = curl(rec["notice_url"])
            time.sleep(DELAY)
            if ok:
                d, cl, inst = parse_notice(html)
                out["date"] = rec["date"] or d
                out["changelog"] = cl
                if deep:
                    out["install_steps"] = inst
        return out

    latest = build(order[0], deep=True)
    prev = [build(v, deep=False) for v in order[1:]]

    result = {
        "make": "Canon",
        "model": name,
        "version": latest["version"],
        "date": latest["date"],
        "download_url": latest["download_url"],
        "download_opens_page": True,
        "source_url": support_url,
        "release_notes_url": latest["release_notes_url"],
        "changelog": latest["changelog"],
        "install_steps": latest["install_steps"],
        "previous_versions": prev,
    }

    print("  v" + result["version"] + "  " + (result["date"] or "NO DATE")
          + "  changelog=" + str(len(result["changelog"]))
          + "  install=" + str(len(result["install_steps"]))
          + "  prev=" + str(len(prev)))
    return result

def main():
    notices = discover_notices()
    pro = fetch_pro_firmware()

    models = CINEMA_EOS
    if ONLY:
        models = [m for m in CINEMA_EOS
                  if ONLY in m["display"].lower() or ONLY in m["slug"].lower()]
        print("filtered to " + str(len(models)) + " model(s)")

    cams = []
    for m in models:
        time.sleep(DELAY)
        r = process(m, notices, pro)
        if r:
            cams.append(r)

    Path("canon_cameras.json").write_text(
        json.dumps(cams, indent=2, ensure_ascii=False))

    n = len(cams)
    print()
    print("=" * 64)
    print("Wrote " + str(n) + " cameras to canon_cameras.json")
    if not n:
        return
    print("  date:          " + str(sum(1 for c in cams if c["date"])) + "/" + str(n))
    print("  changelog:     " + str(sum(1 for c in cams if c["changelog"])) + "/" + str(n))
    print("  install steps: " + str(sum(1 for c in cams if c["install_steps"])) + "/" + str(n))
    print("  prev versions: " + str(sum(1 for c in cams if c["previous_versions"])) + "/" + str(n))
    for label, field in (("no changelog", "changelog"),
                         ("no install steps", "install_steps"),
                         ("no date", "date")):
        bad = [c["model"] for c in cams if not c[field]]
        if bad:
            print("  " + label + ": " + ", ".join(bad))
    print()
    print("  NOTE download buttons point at Canon support pages")
    print("       (download_opens_page=true -> arrow icon, rule 3)")

if __name__ == "__main__":
    main()
