#!/usr/bin/env python3
"""canon_peek2.py  --  Can curl see Canon's direct firmware download links?

Goal: one uniform path per camera. For every Cinema EOS body:
    usa.canon.com/support/p/<slug>?subtab=downloads-firmware
should yield version + date + a direct pdisp01.c-wss.com file link.

Canon's download ID is confirmed to be base64 of a 12-digit file id:
    MDQwMDAwNjA5NTAx  ->  040000609501
so if the ids are in the HTML we can build download URLs for everything.

CONTROLS (known to expose direct links to search-engine crawlers):
    dp-v2410, eos-5ds
If the controls come back empty, the links are injected client-side and
curl will never see them. If they show up, the same parse works for every
camera and we are done.

Throwaway diagnostic.
"""

import base64, re, subprocess
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

BASE = "https://www.usa.canon.com"


def curl(url, timeout=45):
    cmd = ["curl", "-s", "-L", "--max-time", str(timeout), "--compressed",
           "-w", "%{http_code}",
           "-H", "User-Agent: " + UA,
           "-H", "Accept: text/html,application/xhtml+xml,application/json,*/*;q=0.8",
           "-H", "Accept-Language: en-US,en;q=0.9",
           "-H", "Sec-Fetch-Dest: document",
           "-H", "Sec-Fetch-Mode: navigate",
           "-H", "Connection: keep-alive",
           url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        b = r.stdout
        if len(b) >= 3:
            return b[:-3], b[-3:]
        return "", "000"
    except Exception:
        return "", "ERR"


def report(label, url, save=True):
    print()
    print("#" * 74)
    print("# " + label)
    print("# " + url)
    print("#" * 74)

    body, code = curl(url)
    print("  HTTP " + str(code) + "   " + str(len(body)) + " bytes")
    if len(body) < 500:
        print("  too small, skipping")
        return None

    if save:
        Path("peek2_" + label + ".txt").write_text(body)
        print("  saved: peek2_" + label + ".txt")

    # direct file links
    dl = sorted(set(re.findall(
        r"https?://[^\s\"'<>\\)]*c-wss\.com[^\s\"'<>\\)]*", body)))
    print()
    if dl:
        print("  *** " + str(len(dl)) + " DIRECT DOWNLOAD URL(S) ***")
        for u in dl[:12]:
            print("    " + u[:150])
            m = re.search(r"[?&]id=([A-Za-z0-9+/=]+)", u)
            if m:
                try:
                    print("        id decodes to: "
                          + base64.b64decode(m.group(1)).decode(errors="replace"))
                except Exception:
                    pass
    else:
        print("  NO c-wss.com links in served HTML")

    # bare ids, in case the href is assembled client-side
    ids = sorted(set(re.findall(r"[\"'](MD[A-Za-z0-9+/=]{12,})[\"']", body)))
    if ids:
        print()
        print("  base64-looking ids found: " + str(len(ids)))
        for i in ids[:8]:
            try:
                print("    " + i + "  ->  "
                      + base64.b64decode(i).decode(errors="replace"))
            except Exception:
                print("    " + i)

    # firmware version strings + dates, to confirm the list is server-rendered
    vers = sorted(set(re.findall(
        r"Firmware\s+Version\s+(\d+(?:\.\d+){2,4})", body)))
    if vers:
        print()
        print("  firmware versions in HTML: " + ", ".join(vers[:12]))
    dates = sorted(set(re.findall(r"\b(\d{2}\.\d{2}\.\d{2})\b", body)))
    if dates:
        print("  dd.mm.yy style dates: " + ", ".join(dates[:12]))

    # markers
    print()
    marks = ["WWUFORedirectTarget", "downloadType", "subtab=downloads-firmware",
             "agree", "terms and conditions", "softwareDetail",
             "__PRELOADED", "__NEXT_DATA__", "apiUrl", "graphql", "/bin/canon"]
    hits = [(k, body.count(k)) for k in marks if body.count(k)]
    if hits:
        print("  markers: " + ", ".join(k + "=" + str(n) for k, n in hits))
    else:
        print("  markers: none")

    return body


# ── controls: search engines saw direct links on these ─────────────
report("CONTROL_dpv2410", BASE + "/support/p/dp-v2410?subtab=downloads-firmware")
report("CONTROL_5ds",     BASE + "/support/p/eos-5ds?subtab=downloads-firmware")

# ── the pro-firmware archive: dump its real hrefs ──────────────────
body = report("pro_firmware", BASE + "/support/service-and-repair/pro-firmware",
              save=False)
if body:
    print()
    print("  --- hrefs in the pro-firmware table ---")
    hrefs = sorted(set(re.findall(r'href=[\"\']([^\"\']+)[\"\']', body)))
    keep = [h for h in hrefs if re.search(r"c-wss|support/p/|advisor", h, re.I)]
    print("    " + str(len(keep)) + " of " + str(len(hrefs)) + " look relevant")
    for h in keep[:20]:
        print("    " + h[:150])

# ── the cameras we actually need ───────────────────────────────────
for slug in ["eos-c400", "eos-c50", "eos-c80", "eos-c70",
             "eos-c300-mark-iii", "eos-c500-mark-ii"]:
    report(slug, BASE + "/support/p/" + slug + "?subtab=downloads-firmware")

print()
print("=" * 74)
print("READ THIS FIRST: did CONTROL_dpv2410 / CONTROL_5ds show direct URLs?")
print("  yes -> uniform path works, same parse for every camera")
print("  no  -> links are client-side, need another route")
