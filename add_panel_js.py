"""Stage 2 of the detail panel: render the content and wire up the behaviour.

Each plate carries its panel content as a JSON payload, so opening a panel
needs no network and no template duplication. Adds:

  - panel data on every plate
  - the renderer (bench line, actions, changelog, instruction sections)
  - open/close on click, Escape and scrim, with focus returned to the plate

Patches build_site.py. Writes a .bak, refuses to save if it will not parse.

Run once:  python3 add_panel_js.py
"""

import ast
import shutil

TARGET = "build_site.py"

PAYLOAD = '''
def panel_payload(cam, name, label):
    """Everything the panel shows for one camera, as plain data."""
    bench = bench_line(cam)
    steps = []
    for block in cam.get("install") or []:
        items = [item for item in (block.get("items") or []) if item]
        if items:
            steps.append({"h": block.get("heading") or "", "i": items})

    links = []
    for text, href in panel_links(cam):
        if href:
            links.append({"t": text, "u": href})

    return {
        "make": cam.get("manufacturer") or "",
        "name": name,
        "version": cam.get("version") or "",
        "date": date_label(cam.get("release_date"), cam.get("release_precision")),
        "size": cam.get("file_size") or "",
        "state": label,
        "bench": bench,
        "news": cam.get("changelog") or cam.get("features") or [],
        "steps": steps,
        "guides": cam.get("guides") or [],
        "stepsVersion": cam.get("install_version") or "",
        "stepsSource": cam.get("install_source") or "",
        "source": cam.get("source_url") or "",
        "summary": cam.get("summary") or "",
    }


def panel_links(cam):
    """The same three labels the plate uses, for the panel's action row."""
    make = cam.get("manufacturer")
    out = []
    if cam.get("firmware_url"):
        if cam.get("firmware_kind") != "page" or make == "RED":
            out.append(("Download", cam["firmware_url"]))
        else:
            out.append(("Source", cam["firmware_url"]))
    if cam.get("notes_url"):
        out.append(("Release notes", cam["notes_url"]))
    out.append(("Source", cam.get("source_url") or ""))

    seen = []
    final = []
    for text, href in out:
        if not href or href in [u for _, u in final] or text in seen:
            continue
        seen.append(text)
        final.append((text, href))
    return final

'''

PANEL_JS = r'''
var scrim = document.getElementById("scrim");
var panel = document.getElementById("panel");
var panelBody = document.getElementById("panel-body");
var shut = document.getElementById("panel-shut");
var opener = null;

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function listOf(items, ordered) {
  var tag = ordered ? "ol" : "ul";
  var out = "<" + tag + ' class="lines">';
  items.forEach(function (item) { out += "<li>" + esc(item) + "</li>"; });
  return out + "</" + tag + ">";
}

function render(data) {
  document.getElementById("panel-maker").textContent = data.make;
  document.getElementById("panel-name").textContent = data.name;
  document.getElementById("panel-ver").textContent = data.version;

  var meta = [data.date, data.size, data.state].filter(Boolean);
  document.getElementById("panel-meta").textContent = meta.join("  /  ");

  var html = "";

  if (data.bench) {
    html += '<div class="bench"><p class="tag">At the bench</p><ol>'
      + "<li>" + esc(data.bench.file) + "</li>"
      + "<li>" + esc(data.bench.where) + "</li>"
      + "<li>" + esc(data.bench.slot) + "</li>"
      + "<li>" + esc(data.bench.menu) + "</li></ol></div>";
  }

  if (data.links && data.links.length) {
    html += '<div class="acts">';
    data.links.forEach(function (link, index) {
      html += '<a class="' + (index === 0 && link.t === "Download" ? "lead" : "")
        + '" href="' + esc(link.u) + '" target="_blank" rel="noopener">'
        + esc(link.t) + "</a>";
    });
    html += "</div>";
  }

  if (data.summary) {
    html += '<p class="said">' + esc(data.summary) + "</p>";
  }

  if (data.news && data.news.length) {
    html += "<details open><summary>What's new in " + esc(data.version)
      + '</summary><div class="inner">' + listOf(data.news, false)
      + "</div></details>";
  }

  if (data.steps && data.steps.length) {
    var inner = "";
    data.steps.forEach(function (block) {
      inner += "<h4>" + esc(block.h) + "</h4>" + listOf(block.i, true);
    });
    html += "<details><summary>How to install</summary>"
      + '<div class="inner">' + inner;
    if (data.stepsVersion && data.stepsVersion !== data.version) {
      inner += "";
      html += '<p class="said">These steps are published for '
        + esc(data.stepsVersion) + ".</p>";
    }
    if (data.stepsSource) {
      html += '<p class="said">Steps quoted from <a href="'
        + esc(data.stepsSource) + '" target="_blank" rel="noopener">'
        + "the manufacturer's page</a>.</p>";
    }
    html += "</div></details>";
  } else if (data.guides && data.guides.length) {
    var guides = "";
    data.guides.forEach(function (guide) {
      guides += '<li><a href="' + esc(guide.url) + '" target="_blank" '
        + 'rel="noopener">' + esc(guide.label) + "</a></li>";
    });
    html += "<details><summary>How to install</summary>"
      + '<div class="inner"><p class="said">The manufacturer publishes the '
      + "update procedure as a document rather than on the page.</p>"
      + '<ul class="lines">' + guides + "</ul></div></details>";
  }

  panelBody.innerHTML = html;
  panelBody.scrollTop = 0;
}

function openPanel(plate) {
  var data;
  try {
    data = JSON.parse(plate.dataset.panel);
  } catch (err) {
    return;
  }
  opener = plate;
  render(data);
  panel.hidden = false;
  window.requestAnimationFrame(function () {
    panel.classList.add("on");
    scrim.classList.add("on");
  });
  document.body.style.overflow = "hidden";
  shut.focus();
}

function closePanel() {
  panel.classList.remove("on");
  scrim.classList.remove("on");
  document.body.style.overflow = "";
  window.setTimeout(function () { panel.hidden = true; }, 260);
  if (opener) { opener.focus(); opener = null; }
}

plates.forEach(function (plate) {
  plate.addEventListener("click", function (event) {
    if (event.target.closest("a")) { return; }
    openPanel(plate);
  });
  plate.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPanel(plate);
    }
  });
});

shut.addEventListener("click", closePanel);
scrim.addEventListener("click", closePanel);
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && !panel.hidden) {
    event.stopPropagation();
    closePanel();
  }
});
'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "panel_payload" in text:
        print("Already patched. Nothing to do.")
        return

    anchor = "def card(cam):"
    if anchor not in text:
        print("Could not find card().")
        return
    text = text.replace(anchor, PAYLOAD.lstrip(chr(10)) + anchor, 1)

    old_article = ('''        '<article class="plate" data-make="' + esc(make, quote=True) + '"'
        + ' data-find="' + esc(haystack, quote=True) + '">\'''')
    new_article = ('''        '<article class="plate" data-make="' + esc(make, quote=True) + '"'
        + ' data-find="' + esc(haystack, quote=True) + '"'
        + ' tabindex="0" role="button"'
        + ' data-panel="' + esc(json.dumps(
            panel_payload(cam, name, label), ensure_ascii=False), quote=True)
        + '">\'''')
    if old_article not in text:
        print("Could not find the article line.")
        return
    text = text.replace(old_article, new_article, 1)

    # links belong in the payload too
    old_payload_end = '''        "summary": cam.get("summary") or "",
    }'''
    new_payload_end = '''        "summary": cam.get("summary") or "",
        "links": links,
    }'''
    if old_payload_end not in text:
        print("Could not find the payload dict end.")
        return
    text = text.replace(old_payload_end, new_payload_end, 1)

    # The bootstrap call appears twice: once inside the clear handler and
    # once at the end of the script. Append after the last one so the panel
    # code runs at load rather than on a click.
    js_anchor = "apply();"
    if js_anchor not in text:
        print("Could not find the search bootstrap call.")
        return
    cut = text.rindex(js_anchor) + len(js_anchor)
    text = text[:cut] + PANEL_JS + text[cut:]

    try:
        ast.parse(text)
    except SyntaxError as err:
        print("Refusing to write: result would not parse.")
        print("  line " + str(err.lineno) + ": " + str(err.msg))
        return

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Patched " + TARGET + " (backup: " + TARGET + ".bak)")
    print("Next: python3 build_site.py")


if __name__ == "__main__":
    main()
