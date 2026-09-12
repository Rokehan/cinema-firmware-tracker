#!/usr/bin/env python3
"""Patcher: render previous versions in the panel.

Inserts the JS rendering block right before panelBody.innerHTML.
Safe to run twice.
"""
import shutil

TARGET = "build_site.py"

with open(TARGET) as f:
    content = f.read()

if "data.prev" in content:
    print("Already patched.")
    raise SystemExit(0)

OLD = "    panelBody.innerHTML = html;" + chr(10) + "    panelBody.scrollTop = 0;"

if OLD not in content:
    print("Anchor not found. Showing context:")
    idx = content.find("panelBody.innerHTML")
    if idx > -1:
        print(repr(content[idx-40:idx+60]))
    raise SystemExit(1)

BLOCK = (
    '    if (data.prev && data.prev.length) {' + chr(10)
    + '        var pvInner = "";' + chr(10)
    + '        data.prev.forEach(function (pv) {' + chr(10)
    + '            var pvHead = esc(pv.v || "");' + chr(10)
    + '            if (pv.d) { pvHead += " / " + esc(pv.d); }' + chr(10)
    + '            pvInner += "<details><summary>" + pvHead + "</summary>"' + chr(10)
    + "                + '<div class=" + chr(34) + "inner" + chr(34) + ">';" + chr(10)
    + '            if (pv.cl && pv.cl.length) {' + chr(10)
    + '                pvInner += listOf(pv.cl, false);' + chr(10)
    + '            } else {' + chr(10)
    + "                pvInner += '<p class=" + chr(34) + "said" + chr(34) + ">No changelog published.</p>';" + chr(10)
    + '            }' + chr(10)
    + '            if (pv.dl) {' + chr(10)
    + "                pvInner += '<div class=" + chr(34) + "acts" + chr(34) + " style=" + chr(34) + "margin-top:12px" + chr(34) + ">'" + chr(10)
    + "                    + '<a href=" + chr(34) + "' + esc(pv.dl) + '" + chr(34) + " target=" + chr(34) + "_blank" + chr(34) + " rel=" + chr(34) + "noopener" + chr(34) + ">'" + chr(10)
    + '                    + "Download " + esc(pv.v || "") + "</a></div>";' + chr(10)
    + '            }' + chr(10)
    + '            pvInner += "</div></details>";' + chr(10)
    + '        });' + chr(10)
    + '        html += "<details><summary>Previous versions (" + data.prev.length' + chr(10)
    + "            + \")</summary>\" + '<div class=" + chr(34) + "inner" + chr(34) + ">' + pvInner" + chr(10)
    + '            + "</div></details>";' + chr(10)
    + '    }' + chr(10)
    + chr(10)
)

# Actually, building JS strings with chr() is getting unwieldy.
# Let me just use a raw string approach.
BLOCK2 = '''    if (data.prev && data.prev.length) {
        var pvInner = "";
        data.prev.forEach(function (pv) {
            var pvHead = esc(pv.v || "");
            if (pv.d) { pvHead += " / " + esc(pv.d); }
            pvInner += "<details><summary>" + pvHead + "</summary>"
'''
# OK this approach is also getting complex. Let me write the JS to a
# temporary variable and inject it.

JS_BLOCK = r"""    if (data.prev && data.prev.length) {
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

"""

NEW = JS_BLOCK + "    panelBody.innerHTML = html;" + chr(10) + "    panelBody.scrollTop = 0;"

shutil.copy2(TARGET, TARGET + ".bak")
with open(TARGET, "w") as f:
    f.write(content.replace(OLD, NEW, 1))

print("Patched %s" % TARGET)
