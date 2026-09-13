#!/usr/bin/env python3
"""patch_canon_v6.py  --  Fill version history for the current cameras.

Two fixes to canon_cameras.py:

  1. normalize_version: Cinema EOS versions are 4-part (1.0.7.1). Canon
     sometimes appends a page-duplicate suffix, which produced the bogus
     "1.0.3.1.001" in the C500 Mark II list. Any 5th component is dropped.

  2. Sibling-notice probing. The advisory index only lists recent notices,
     so C400 / C80 / C50 came back with no previous versions even though
     older firmware exists. This is NOT blind URL guessing: for each camera
     we already hold a notice URL that is confirmed to work, so its exact
     shape becomes the template and only the version number is substituted.
     Unknown versions are checked with a cheap HEAD request and only kept
     on HTTP 200. Nothing is invented; a version is only added if Canon
     actually serves a page for it.

     Probe budget is capped per camera. Skips versions already known.

Writes a .bak, refuses to save if the result will not parse, safe to run twice.
"""

import shutil, sys
from pathlib import Path

target = Path("canon_cameras.py")
if not target.exists():
    print("ERROR: canon_cameras.py not found in this directory")
    sys.exit(1)

bak = Path("canon_cameras.py.bak")
shutil.copy2(target, bak)
print("Backup: " + str(bak))

src = target.read_text()
applied = []
NL = chr(10)

# ── FIX 1: normalize_version ───────────────────────────────────────

old_norm = '''def normalize_version(v):
    """Cinema EOS pads a trailing .00: '1.0.7.1.00' -> '1.0.7.1'."""
    p = v.split(".")
    if len(p) == 5 and p[-1] == "00":
        return ".".join(p[:4])
    return v'''

new_norm = '''def normalize_version(v):
    """Cinema EOS versions are 4-part.

    Canon writes '1.0.7.1.00' on some pages and appends a page-duplicate
    suffix on others ('1-0-3-1-001'), so any 5th component is dropped.
    """
    p = [x for x in v.split(".") if x != ""]
    if len(p) >= 5:
        return ".".join(p[:4])
    return ".".join(p)'''

if old_norm in src:
    src = src.replace(old_norm, new_norm)
    applied.append("normalize_version(): drops any 5th component (fixes 1.0.3.1.001)")

# ── FIX 2: sibling probing ─────────────────────────────────────────

helper = '''
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


'''

anchor = "# \u2500\u2500 assemble \u2500"
i = src.find(anchor)
if i == -1:
    print("ERROR: could not find the assemble section")
    sys.exit(1)
src = src[:i] + helper.lstrip(NL) + src[i:]
applied.append("added probe_siblings(): verifies candidate versions with HEAD requests")

# call it after the merge, before ordering
old_guard = '''    if not merged:
        print("  WARNING: no versions found")
        return None

    order = sorted(merged, key=version_tuple, reverse=True)'''

new_guard = '''    if not merged:
        print("  WARNING: no versions found")
        return None

    probe_siblings(model, merged)

    order = sorted(merged, key=version_tuple, reverse=True)'''

if old_guard in src:
    src = src.replace(old_guard, new_guard)
    applied.append("process(): probes for sibling versions before building output")

# ── validate + save ────────────────────────────────────────────────

try:
    compile(src, "canon_cameras.py", "exec")
except SyntaxError as e:
    print("SYNTAX ERROR after patching: " + str(e))
    print("Restoring backup, nothing changed.")
    shutil.copy2(bak, target)
    sys.exit(1)

target.write_text(src)
print()
if not applied:
    print("  nothing matched, file may already be patched")
for a in applied:
    print("  applied: " + a)
print()
print("Saved. Now run: python canon_cameras.py --debug")
