"""Reads feed.json and writes index.html using site_template.html.

Invents nothing: every value on the page comes from the feed, and every
link points at the manufacturer's own URL.
"""

import html
import json
import re
from datetime import datetime, timezone

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Firmware Index / cinema camera firmware, in one place</title>
<meta name="description" content="Every professional cinema camera firmware update in one place. ARRI and Sony, checked daily, every record linked to the manufacturer.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --ink:#100c09; --plate:#191510; --edge:#2b2521; --edge-hi:#5c4a37;
  --text:#ede9e3; --mute:#8f8579; --dim:#8d8378;
  --orange:#ff7200; --olive:#a3bd6a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--text);
  font-family:Manrope,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace}
a{color:inherit}
.wrap{max-width:1220px;margin:0 auto;padding:0 24px}

header{border-bottom:1px solid var(--edge);padding:56px 0 40px}
.eyebrow{display:flex;align-items:center;gap:10px;font-family:"JetBrains Mono",monospace;
  font-size:.75rem;letter-spacing:.18em;text-transform:uppercase;color:var(--mute)}
.tally{width:7px;height:7px;border-radius:50%;background:var(--orange);
  animation:tally 2.6s ease-in-out infinite}
@keyframes tally{0%,100%{opacity:1}50%{opacity:.25}}
h1{margin:22px 0 0;font-size:clamp(2.1rem,5.4vw,3.9rem);font-weight:800;
  line-height:1.02;letter-spacing:-.03em;max-width:16ch}
h1 em{font-style:normal;color:var(--orange)}
.stats{display:flex;flex-wrap:wrap;gap:44px;margin-top:40px}
.stat span{display:block;font-family:"JetBrains Mono",monospace;font-size:.7rem;
  letter-spacing:.18em;text-transform:uppercase;color:var(--mute)}
.stat strong{display:block;margin-top:8px;font-family:"JetBrains Mono",monospace;
  font-size:1.65rem;font-weight:500;letter-spacing:-.02em;color:var(--text)}

nav{display:flex;gap:8px;padding:26px 0;border-bottom:1px solid var(--edge)}
nav button{font-family:"JetBrains Mono",monospace;font-size:.72rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--mute);background:none;cursor:pointer;
  border:1px solid var(--edge);padding:9px 16px;transition:.18s}
nav button:hover{border-color:var(--edge-hi);color:var(--text)}
nav button[aria-current=true]{border-color:var(--orange);color:var(--orange)}
nav .soon{opacity:.45;cursor:default;pointer-events:none}

.grid{display:grid;gap:1px;background:var(--edge);border:1px solid var(--edge);
  grid-template-columns:repeat(auto-fill,minmax(272px,1fr));margin:32px 0 0}
.plate{background:var(--plate);padding:0;position:relative;display:flex;flex-direction:column}
.plate .stripe{height:3px;width:100%}
.plate .top{display:flex;justify-content:space-between;gap:12px;padding:20px 20px 0;
  font-family:"JetBrains Mono",monospace;font-size:.72rem;letter-spacing:.1em;color:var(--mute)}
.plate .body{padding:26px 20px 22px}
.plate .name{font-size:1.06rem;font-weight:700;letter-spacing:-.01em;line-height:1.2}
.plate .ver{margin-top:10px;font-family:"JetBrains Mono",monospace;font-size:1.75rem;
  line-height:1;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.plate .state{margin-top:14px;font-family:"JetBrains Mono",monospace;font-size:.68rem;
  letter-spacing:.16em;text-transform:uppercase;color:var(--mute)}
.plate .links{margin-top:18px;padding-top:16px;border-top:1px solid var(--edge);
  display:flex;flex-wrap:wrap;gap:8px}
.plate .links a{font-family:"JetBrains Mono",monospace;font-size:.68rem;letter-spacing:.1em;
  text-transform:uppercase;text-decoration:none;border:1px solid var(--edge);
  padding:7px 11px;color:var(--mute);transition:.18s}
.plate .links a:hover{border-color:var(--orange);color:var(--orange)}
.plate .sum{margin-top:16px;font-size:.86rem;line-height:1.55;color:var(--mute)}

footer{border-top:1px solid var(--edge);margin-top:64px;padding:36px 0 72px;
  font-size:.86rem;line-height:1.65;color:var(--mute);max-width:62ch}
footer strong{color:var(--text);font-weight:700}
</style>
</head>
<body>
<div class="wrap">
<header>
  <p class="eyebrow"><span class="tally"></span> Firmware Index / monitoring ARRI + Sony</p>
  <h1>Every cinema camera firmware update, <em>in one place.</em></h1>
  <div class="stats">
    <div class="stat"><span>Cameras</span><strong>__COUNT__</strong></div>
    <div class="stat"><span>With links</span><strong>__LINKED__</strong></div>
    <div class="stat"><span>Manufacturers</span><strong>__MAKES__ of 3</strong></div>
    <div class="stat"><span>Checked daily</span><strong>09:00 JST</strong></div>
  </div>
</header>

<nav id="filters">
  <button data-make="all" aria-current="true">All</button>
  __TABS__
</nav>

<main class="grid" id="grid">
__CARDS__
</main>

<footer>
  <strong>Every record links to the manufacturer's own page.</strong>
  Version numbers, dates and files are read from that page, never generated.
  Sony publishes month-precision dates outside the FX line, and the FX bodies
  update from a file copied to a card rather than a direct download.
  Last checked __STAMP__.
</footer>
</div>

<script>
var buttons = document.querySelectorAll("#filters button[data-make]:not(.soon)");
buttons.forEach(function (b) {
  b.addEventListener("click", function () {
    var make = b.dataset.make;
    buttons.forEach(function (o) { o.setAttribute("aria-current", String(o === b)); });
    document.querySelectorAll("#grid .plate").forEach(function (p) {
      p.style.display = (make === "all" || p.dataset.make === make) ? "flex" : "none";
    });
  });
});
</script>
</body>
</html>
"""

ORANGE = "#ff7200"
OLIVE = "#a3bd6a"
GREY = "#8d8378"

EXPECTED_MAKES = ["ARRI", "Sony", "RED"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def date_label(value, precision):
    if not value:
        return "Date not published"
    parts = value.split("-")
    year = parts[0]
    month = MONTHS[int(parts[1]) - 1] if len(parts) > 1 else ""
    if precision == "day" and len(parts) > 2:
        return str(int(parts[2])) + " " + month + " " + year
    return (month + " " + year).strip()


def state_of(cam):
    """What a tech actually gets if they click. Honest outcomes only.

    A "page" link is not a download: Sony's FX bodies want a file copied to
    a card, and RED puts the firmware behind an account login. Say so
    rather than promising a file.
    """
    kind = cam.get("firmware_kind")
    make = cam.get("manufacturer")
    if cam.get("firmware_url") and kind == "page":
        if make == "RED":
            return "Login to download", OLIVE
        return "Card update via Sony", OLIVE
    if cam.get("firmware_url"):
        return "Firmware + notes", ORANGE
    if cam.get("notes_url"):
        return "Documentation only", OLIVE
    return "Version only", GREY


def sort_key(cam):
    return cam.get("release_date") or ""


# ARRI's page headlines are the source of the version, but they are not always
# the name a tech uses for the body. ARRI's own release notes and user manual
# for SUP 11.1.1 call it "ALEXA Classic" (the h1 just says "ALEXA"), and the
# camera index writes the Mini bodies in mixed case. Nothing here invents a
# product: each value is the manufacturer's own wording for the same camera.
DISPLAY_NAMES = {
    "ALEXA": "ALEXA Classic",
    "ALEXA MINI": "ALEXA Mini",
    "ALEXA MINI LF": "ALEXA Mini LF",
    "AMIRA LIVE / AMIRA": "AMIRA",
}


def display_name(product):
    """Manufacturer's own name for the body, tidied for reading."""
    if not product:
        return ""
    name = " ".join(product.split())
    fixed = DISPLAY_NAMES.get(name.upper())
    if fixed:
        return fixed
    # Sony ships model codes bolted onto the name, e.g. FX3(ILME-FX3A).
    name = re.sub(r"(?<=[^ (])\(", " (", name)
    return name


def card(cam):
    label, tone = state_of(cam)
    make = cam.get("manufacturer", "")
    esc = html.escape
    links = []
    if cam.get("firmware_url"):
        if cam.get("firmware_kind") != "page":
            text = "Download"
        elif make == "RED":
            text = "Release history"
        else:
            text = "Update page"
        links.append((text, cam["firmware_url"]))
    if cam.get("notes_url"):
        links.append(("Release notes", cam["notes_url"]))
    if cam.get("archive_url"):
        links.append(("Archive", cam["archive_url"]))
    links.append(("Source", cam.get("source_url") or ""))

    rows = []
    used = []
    for text, href in links:
        if not href or href in used:
            continue
        used.append(href)
        rows.append('<a href="' + esc(href, quote=True)
                    + '" target="_blank" rel="noopener">' + esc(text) + "</a>")

    summary = cam.get("summary")
    summary_html = ""
    if summary:
        short = summary if len(summary) < 190 else summary[:187].rstrip() + "..."
        summary_html = '<p class="sum">' + esc(short) + "</p>"

    return (
        '<article class="plate" data-make="' + esc(make, quote=True) + '">'
        + '<span class="stripe" style="background:' + tone + '"></span>'
        + '<div class="top"><span>' + esc(make) + "</span><span>"
        + esc(date_label(cam.get("release_date"), cam.get("release_precision")))
        + "</span></div>"
        + '<div class="body">'
        + '<h2 class="name">' + esc(display_name(cam.get("product"))) + "</h2>"
        + '<p class="ver" style="color:' + tone + '">'
        + esc(cam.get("version") or "unknown") + "</p>"
        + '<p class="state">' + esc(label) + "</p>"
        + summary_html
        + '<div class="links">' + "".join(rows) + "</div>"
        + "</div></article>"
    )


def main():
    with open("feed.json", encoding="utf-8") as fh:
        feed = json.load(fh)

    cams = sorted(feed, key=sort_key, reverse=True)
    makes = []
    for cam in cams:
        if cam.get("manufacturer") and cam["manufacturer"] not in makes:
            makes.append(cam["manufacturer"])

    linked = sum(1 for cam in cams if cam.get("firmware_url"))
    ordered = [m for m in EXPECTED_MAKES if m in makes]
    ordered += [m for m in makes if m not in ordered]

    parts = []
    for make in ordered:
        parts.append('<button data-make="' + html.escape(make, quote=True)
                     + '">' + html.escape(make) + "</button>")
    for make in EXPECTED_MAKES:
        if make not in makes:
            parts.append('<button class="soon" data-make="'
                         + html.escape(make, quote=True) + '">'
                         + html.escape(make) + " / soon</button>")
    tabs = "".join(parts)
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    page = TEMPLATE

    page = page.replace("__COUNT__", str(len(cams)))
    page = page.replace("__LINKED__", str(linked))
    page = page.replace("__MAKES__", str(len(makes)))
    page = page.replace("of 3", "of " + str(len(EXPECTED_MAKES)))
    page = page.replace("__TABS__", tabs)
    page = page.replace("__CARDS__", chr(10).join(card(c) for c in cams))
    page = page.replace("__STAMP__", stamp)

    with open("index.html", "w", encoding="utf-8") as fh:
        fh.write(page)

    print("index.html written:", len(cams), "cameras,", linked, "with links")


if __name__ == "__main__":
    main()
