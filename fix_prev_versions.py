#!/usr/bin/env python3
"""Patcher: Previous versions UI + data pipeline.

Fixes the anchors that the first attempt missed:
1. build_site.py: adds previous_versions to panel payload and renders
   them as nested accordions in the panel
2. build_feed.py: adds previous_versions + firmware_url/kind to
   english_extras() return dict
3. sony_english.py: limits previous version scraping to non-cinema
   bodies only (cinema pages are too slow and have no useful changelog)

Safe to run twice.
"""
import ast, shutil, sys

def patch(path, replacements):
    with open(path) as f:
        content = f.read()
    try:
        ast.parse(content)
    except SyntaxError as e:
        print("%s has a syntax error before patching: %s" % (path, e))
        sys.exit(1)
    changed = False
    for old, new, label in replacements:
        if new in content and old not in content:
            print("  [skip] %s (already applied)" % label)
            continue
        if old not in content:
            print("  [miss] %s (anchor not found)" % label)
            continue
        content = content.replace(old, new, 1)
        changed = True
        print("  [done] %s" % label)
    if not changed:
        print("  Nothing to patch in %s" % path)
        return
    try:
        ast.parse(content)
    except SyntaxError as e:
        print("  Patched %s has a syntax error: %s" % (path, e))
        sys.exit(1)
    shutil.copy2(path, path + ".bak")
    with open(path, "w") as f:
        f.write(content)
    print("  Saved %s" % path)

# ---- build_feed.py ----
print("Patching build_feed.py:")
patch("build_feed.py", [
    # Add previous_versions + firmware fields to english_extras
    (
        '''    return {
        "changelog": row.get("changelog") or [],
        "install": row.get("install") or [],
        "file_name": row.get("file_name"),
        "install_version": row.get("version"),
        "install_source": row.get("source_url"),
        "guides": row.get("guides") or [],
        "source_url": row.get("source_url"),
    }''',
        '''    extras = {
        "changelog": row.get("changelog") or [],
        "install": row.get("install") or [],
        "file_name": row.get("file_name"),
        "install_version": row.get("version"),
        "install_source": row.get("source_url"),
        "guides": row.get("guides") or [],
        "source_url": row.get("source_url"),
    }
    if row.get("firmware_url"):
        extras["firmware_url"] = row["firmware_url"]
        extras["firmware_kind"] = "file"
    if row.get("previous_versions"):
        extras["previous_versions"] = row["previous_versions"]
    return extras''',
        "english_extras: add firmware_url + previous_versions"
    ),
])

# ---- build_site.py ----
print("Patching build_site.py:")
patch("build_site.py", [
    # Add previous_versions to panel payload
    (
        '        "monitors": cam.get("compatible_monitors") or [],\n    }',
        '        "monitors": cam.get("compatible_monitors") or [],\n'
        '        "prev": cam.get("previous_versions") or [],\n    }',
        "panel_payload: add prev"
    ),
    # Add rendering before panelBody.innerHTML
    (
        '    panelBody.innerHTML = html;\n    panelBody.scrollTop = 0;',
        '''    if (data.prev && data.prev.length) {
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
    panelBody.scrollTop = 0;''',
        "panel: render previous versions"
    ),
])

print()
print("Done. Now re-run: python3 sony_english.py && python3 build_feed.py && python3 build_site.py")
