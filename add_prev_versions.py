#!/usr/bin/env python3
"""Patcher: Previous versions UI in the detail panel.

Adds rendering for a previous_versions array in the panel. Each entry
has version, date, changelog (list of strings), and optionally a
download URL.

Touches build_site.py only. The data flows through feed.json as-is
from the source JSONs.

Safe to run twice.
"""
import ast, shutil, sys

TARGET = "build_site.py"
BACKUP = TARGET + ".bak"

with open(TARGET) as f:
    original = f.read()

try:
    ast.parse(original)
except SyntaxError as e:
    print("Original has a syntax error: %s" % e)
    sys.exit(1)

if "previous_versions" in original:
    print("Already patched (previous_versions found). Nothing to do.")
    sys.exit(0)

patched = original

# 1. Add previous_versions to panel_payload
OLD_PAYLOAD = '''        "monitors": cam.get("compatible_monitors") or [],
    }'''
NEW_PAYLOAD = '''        "monitors": cam.get("compatible_monitors") or [],
        "prev": cam.get("previous_versions") or [],
    }'''

if OLD_PAYLOAD in patched:
    patched = patched.replace(OLD_PAYLOAD, NEW_PAYLOAD, 1)
else:
    print("Cannot find panel_payload anchor")
    sys.exit(1)

# 2. Add previous versions rendering in the panel JS, after the install section
OLD_RENDER = '''    panelBody.innerHTML = html;
    panelBody.scrollTop = 0;'''

NEW_RENDER = '''    if (data.prev && data.prev.length) {
        var pvInner = "";
        data.prev.forEach(function (pv) {
            var pvHead = esc(pv.v || "");
            if (pv.d) { pvHead += " / " + esc(pv.d); }
            pvInner += "<details><summary>" + pvHead + "</summary>"
                + '<div class="inner">';
            if (pv.cl && pv.cl.length) {
                pvInner += listOf(pv.cl, false);
            } else {
                pvInner += '<p class="said">No changelog published.</p>';
            }
            if (pv.dl) {
                pvInner += '<div class="acts" style="margin-top:12px">'
                    + '<a href="' + esc(pv.dl) + '" target="_blank" rel="noopener">'
                    + "Download " + esc(pv.v || "") + "</a></div>";
            }
            pvInner += "</div></details>";
        });
        html += "<details><summary>Previous versions (" + data.prev.length
            + ")</summary>" + '<div class="inner">' + pvInner
            + "</div></details>";
    }

    panelBody.innerHTML = html;
    panelBody.scrollTop = 0;'''

if OLD_RENDER in patched:
    patched = patched.replace(OLD_RENDER, NEW_RENDER, 1)
else:
    print("Cannot find panel render anchor")
    sys.exit(1)

try:
    ast.parse(patched)
except SyntaxError as e:
    print("Patched version has a syntax error: %s" % e)
    sys.exit(1)

shutil.copy2(TARGET, BACKUP)
with open(TARGET, "w") as f:
    f.write(patched)

print("Patched %s (backup: %s)" % (TARGET, BACKUP))
print("Panel now renders previous_versions from feed.json.")
print("Next: add previous_versions data to source JSONs")
