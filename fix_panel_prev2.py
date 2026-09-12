#!/usr/bin/env python3
"""Patcher: render previous versions in the panel. v2 with correct indent."""
import shutil

TARGET = "build_site.py"
with open(TARGET) as f:
    content = f.read()

if "data.prev" in content:
    print("Already patched.")
    raise SystemExit(0)

# Exact anchor from the file (no leading spaces, newline + space indent)
OLD = "}\n\n panelBody.innerHTML = html;\n panelBody.scrollTop = 0;"

if OLD not in content:
    print("Anchor not found")
    raise SystemExit(1)

JS = r"""}

 if (data.prev && data.prev.length) {
   var pvInner = "";
   data.prev.forEach(function (pv) {
     var pvHead = esc(pv.v || "");
     if (pv.d) { pvHead += " / " + esc(pv.d); }
     pvInner += "<details><summary>" + pvHead + "</summary>";
     pvInner += '<div class="inner">';
     if (pv.cl && pv.cl.length) {
       pvInner += listOf(pv.cl, false);
     } else {
       pvInner += '<p class="said">No changelog published.</p>';
     }
     if (pv.dl) {
       pvInner += '<div class="acts" style="margin-top:12px">';
       pvInner += '<a href="' + esc(pv.dl) + '" target="_blank" rel="noopener">';
       pvInner += "Download " + esc(pv.v || "") + "</a></div>";
     }
     pvInner += "</div></details>";
   });
   html += "<details><summary>Previous versions (" + data.prev.length;
   html += ')</summary><div class="inner">' + pvInner;
   html += "</div></details>";
 }

 panelBody.innerHTML = html;
 panelBody.scrollTop = 0;"""

shutil.copy2(TARGET, TARGET + ".bak")
with open(TARGET, "w") as f:
    f.write(content.replace(OLD, JS, 1))
print("Patched")
