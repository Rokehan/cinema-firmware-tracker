"""Add the detail panel: install steps, changelog, and a bench summary.

Each plate becomes clickable. The panel opens with, in order:

  1. the bench line: file name, where it goes, which slot, the menu path.
     Extracted from Sony's own sentences, never composed. Shown only when
     every part of it was found.
  2. version, date, size and the download button
  3. What's new: the manufacturer's changelog, verbatim
  4. Full instructions: the manufacturer's sections, in their order, with
     their own headings kept
  5. the source link, plus a note when the steps were published for a
     different version than the one listed

Patches build_site.py. Writes a .bak, refuses to save if it will not parse.

Run once:  python3 add_panel.py
"""

import ast
import shutil

TARGET = "build_site.py"

HELPERS = '''
SLOT_RE = re.compile(r"\\bslot\\s+([AB1-9])\\b", re.I)
FILE_RE = re.compile(r"\\b([A-Z0-9_]{3,}\\.(?:DAT|bin|zip|SUP))\\b")
# Two menu styles. The Alpha pages write a path ("Menu -> Setup -> ...");
# the FX pages write a sentence ("Select Version Up in the Maintenance
# menu."). Both are quoted as found, never rebuilt.
MENU_PATH_RE = re.compile(
    r"((?:MENU|Menu)\\s*(?:->|>)[^.;]{0,90}?(?:Version|Update|Upgrade)[^.;]{0,30})")
MENU_SENTENCE_RE = re.compile(
    r"((?:Version Up|Software Update|Update Camera|Version Number)"
    r"\\s+in the\\s+[A-Za-z ]{2,24}\\s+menu)", re.I)
ROOT_RE = re.compile(r"\\broot directory\\b", re.I)


def install_lines(cam):
    """Every instruction line, flattened, in Sony's order."""
    lines = []
    for block in cam.get("install") or []:
        for item in block.get("items") or []:
            lines.append(item)
    return lines


def bench_line(cam):
    """The four facts a tech needs at the bench, or None.

    Every value is lifted from the manufacturer's own instructions. When a
    part is missing the whole strip is dropped rather than guessed at.
    """
    lines = install_lines(cam)
    if not lines:
        return None
    joined = " ".join(lines)

    file_name = cam.get("file_name")
    if not file_name:
        hit = FILE_RE.search(joined)
        file_name = hit.group(1) if hit else None

    slot = None
    for line in lines:
        if "insert" not in line.lower():
            continue
        hit = SLOT_RE.search(line)
        if hit:
            slot = hit.group(1).upper()
            break
    if slot is None:
        hit = SLOT_RE.search(joined)
        slot = hit.group(1).upper() if hit else None

    menu = None
    hit = MENU_PATH_RE.search(joined)
    if hit is None:
        # Prefer the sentence that performs the update over the one that
        # only checks the version.
        for line in lines:
            found = MENU_SENTENCE_RE.search(line)
            if found and "number" not in found.group(1).lower():
                hit = found
                break
        if hit is None:
            hit = MENU_SENTENCE_RE.search(joined)
    if hit:
        menu = " ".join(hit.group(1).split()).rstrip(" .,")

    if not (file_name and slot and menu):
        return None

    return {
        "file": file_name,
        "where": "card root" if ROOT_RE.search(joined) else "card",
        "slot": "slot " + slot,
        "menu": menu,
    }

'''

PANEL_CSS = '''
.plate{cursor:pointer}
.plate:focus-visible{outline:2px solid var(--orange);outline-offset:-2px}

.scrim{position:fixed;inset:0;background:rgba(8,6,4,.72);opacity:0;
  pointer-events:none;transition:opacity .22s ease;z-index:40}
.scrim.on{opacity:1;pointer-events:auto}

.panel{position:fixed;top:0;right:0;bottom:0;width:min(560px,100%);
  background:var(--plate);border-left:1px solid var(--edge);z-index:50;
  transform:translateX(100%);transition:transform .26s cubic-bezier(.2,.7,.2,1);
  display:flex;flex-direction:column;overflow:hidden}
.panel.on{transform:translateX(0)}
.panel header{display:flex;align-items:flex-start;gap:16px;padding:26px 26px 20px;
  border-bottom:1px solid var(--edge)}
.panel .who{flex:1}
.panel .maker{font-family:"JetBrains Mono",monospace;font-size:.68rem;
  letter-spacing:.18em;text-transform:uppercase;color:var(--mute)}
.panel h2{margin:8px 0 0;font-size:1.5rem;font-weight:800;letter-spacing:-.02em;
  line-height:1.1}
.panel .ver{margin-top:10px;font-family:"JetBrains Mono",monospace;
  font-size:1.5rem;line-height:1;letter-spacing:-.03em;color:var(--orange)}
.panel .meta{margin-top:10px;font-family:"JetBrains Mono",monospace;
  font-size:.72rem;letter-spacing:.06em;color:var(--mute)}
.panel .shut{flex:0 0 auto;background:none;border:1px solid var(--edge);
  color:var(--mute);width:34px;height:34px;font-size:1.1rem;line-height:1;
  cursor:pointer;transition:.18s}
.panel .shut:hover{border-color:var(--orange);color:var(--orange)}
.panel .scroll{overflow-y:auto;padding:0 26px 40px;flex:1}

.bench{margin:24px 0 0;border:1px solid var(--edge-hi);background:#1e1811;
  padding:16px 18px}
.bench .tag{font-family:"JetBrains Mono",monospace;font-size:.64rem;
  letter-spacing:.2em;text-transform:uppercase;color:var(--olive)}
.bench ol{margin:12px 0 0;padding:0;list-style:none;display:flex;
  flex-wrap:wrap;align-items:center;gap:8px;
  font-family:"JetBrains Mono",monospace;font-size:.86rem;color:var(--text)}
.bench li{white-space:nowrap}
.bench li+li::before{content:"\\2192";color:var(--mute);margin-right:8px}

.acts{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}
.acts a{font-family:"JetBrains Mono",monospace;font-size:.72rem;
  letter-spacing:.12em;text-transform:uppercase;text-decoration:none;
  border:1px solid var(--edge);padding:11px 15px;color:var(--mute);
  transition:.18s}
.acts a:hover{border-color:var(--orange);color:var(--orange)}
.acts a.lead{border-color:var(--orange);color:var(--orange)}
.acts a.lead:hover{background:var(--orange);color:#140f0a}

.panel details{margin:22px 0 0;border-top:1px solid var(--edge);padding-top:16px}
.panel summary{cursor:pointer;font-family:"JetBrains Mono",monospace;
  font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;
  color:var(--mute);list-style:none}
.panel summary::-webkit-details-marker{display:none}
.panel summary::before{content:"+";display:inline-block;width:16px;
  color:var(--orange)}
.panel details[open] summary::before{content:"\\2013"}
.panel summary:hover{color:var(--text)}
.panel details .inner{padding:16px 0 4px}
.panel h4{margin:20px 0 8px;font-size:.82rem;font-weight:700;
  letter-spacing:.02em;color:var(--text)}
.panel h4:first-child{margin-top:0}
.panel ul.lines,.panel ol.lines{margin:0;padding-left:20px;
  font-size:.88rem;line-height:1.6;color:var(--mute)}
.panel ul.lines li,.panel ol.lines li{margin:0 0 7px}
.panel .said{margin:20px 0 0;font-size:.76rem;line-height:1.6;color:var(--dim)}
.panel .said a{color:var(--olive)}
'''

PANEL_MARKUP = '''
<div class="scrim" id="scrim"></div>
<aside class="panel" id="panel" role="dialog" aria-modal="true"
       aria-labelledby="panel-name" hidden>
  <header>
    <div class="who">
      <p class="maker" id="panel-maker"></p>
      <h2 id="panel-name"></h2>
      <p class="ver" id="panel-ver"></p>
      <p class="meta" id="panel-meta"></p>
    </div>
    <button type="button" class="shut" id="panel-shut"
            aria-label="Close">&times;</button>
  </header>
  <div class="scroll" id="panel-body"></div>
</aside>
'''


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "bench_line" in text:
        print("Already patched. Nothing to do.")
        return

    # 1. helpers
    anchor = "def state_of(cam):"
    if anchor not in text:
        print("Could not find state_of().")
        return
    text = text.replace(anchor, HELPERS.lstrip(chr(10)) + anchor, 1)

    # 2. css
    css_anchor = ".empty b{color:var(--text)}\n"
    if css_anchor not in text:
        print("Could not find the empty-state CSS.")
        return
    text = text.replace(css_anchor, css_anchor + PANEL_CSS, 1)

    # 3. markup, before the footer
    footer_anchor = "<footer>"
    if footer_anchor not in text:
        print("Could not find the footer.")
        return
    text = text.replace(footer_anchor, PANEL_MARKUP.lstrip(chr(10))
                        + chr(10) + footer_anchor, 1)

    try:
        ast.parse(text)
    except SyntaxError as err:
        print("Refusing to write: result would not parse.")
        print("  line " + str(err.lineno) + ": " + str(err.msg))
        return

    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(text)

    print("Stage 1 of 2 written to " + TARGET + " (backup: " + TARGET + ".bak)")
    print("Run add_panel_js.py next.")


if __name__ == "__main__":
    main()
