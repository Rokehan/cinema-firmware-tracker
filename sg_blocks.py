#!/usr/bin/env python3
"""
sg_blocks.py  -  why did some SG pages yield 1 install block and others 3?
Offline. Reads the sgpage_*.html files already cached. No network, writes nothing.

The C50 seed split into Caution / Preparations / Procedures. The C500 Mark II
and C300 Mark III pages produced one block, so those pages word their headings
differently and sg_crawl.py's HEADINGS list is missing the variants.

Also reports which firmware version each SG page documents, because SG showed
C500 Mark II 1.1.3.1 while Canon US has 1.1.5.1. Install steps for an older
version are still Canon's own steps, but the record has to say so.

Run:  python sg_blocks.py
"""
from pathlib import Path
import html as htmlmod
import re

NL = chr(10)
CINEMA = "canon digital cinema camera"


def squash(t):
    return " ".join(str(t).split())


def to_text(page):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    t = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", NL, t)
    t = re.sub(r"(?i)<br\s*/?>", NL, t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = htmlmod.unescape(t)
    return NL.join(x for x in (squash(l) for l in t.split(NL)) if x)


def main():
    files = sorted(Path(".").glob("sgpage_*.html"))
    print("cached pages:", len(files))
    print()

    cine = []
    for f in files:
        page = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
        h1 = squash(to_text(m.group(1))) if m else ""
        if CINEMA in h1.lower():
            cine.append((f, h1, page))

    print("cinema pages:", len(cine))
    print()

    # every "Word:" that starts a line: these are the real heading names
    print("=" * 70)
    print("colon-terminated labels, per page")
    print("=" * 70)
    tally = {}
    for f, h1, page in cine:
        text = to_text(page)
        labels = []
        for line in text.split(NL):
            m = re.match(r"([A-Z][A-Za-z /\-]{2,44})\s*:\s*(.*)$", line)
            if m:
                lab = squash(m.group(1))
                labels.append(lab)
                tally[lab] = tally.get(lab, 0) + 1
        ver = ""
        vm = re.search(r"Firmware\s+Version\s+(\d+(?:\.\d+){1,3})", h1, re.I)
        if vm:
            ver = vm.group(1)
        model = ""
        mm = re.search(r"(EOS\s+C\d{2,3}(?:\s+Mark\s+[IVX]+)?)", h1)
        if mm:
            model = mm.group(1)
        print("  %-14s %-20s v%-9s %s"
              % (f.name.replace("sgpage_", "").replace(".html", ""),
                 model, ver, ", ".join(labels[:9]) or "(none)"))
    print()

    print("=" * 70)
    print("label frequency across cinema pages")
    print("=" * 70)
    for lab, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print("    %-40s x%d" % (lab[:40], n))
    print()

    # the detail text of one page that only produced a single block
    print("=" * 70)
    print("detail text of a low-block page, verbatim")
    print("=" * 70)
    target = None
    for f, h1, page in cine:
        text = to_text(page)
        n = len(re.findall(r"(?im)^(Caution|Preparations?|Procedures?)\s*:", text))
        if n <= 1:
            target = (f, h1, text)
            break
    if target is None:
        print("  every cached cinema page had more than one block")
    else:
        f, h1, text = target
        print("  " + f.name)
        print("  " + h1[:100])
        print()
        start = 0
        m = re.search(r"(?i)\bDetail\b", text)
        if m:
            start = m.start()
        chunk = text[start:start + 2600]
        for line in chunk.split(NL)[:56]:
            print("    " + line[:150])
    print()

    # do headings live in tags rather than as "Word:" text?
    print("=" * 70)
    print("heading-ish tags on that page")
    print("=" * 70)
    if target:
        page = dict((f.name, p) for f, _, p in cine)[target[0].name]
        for m in re.finditer(r"<(h[2-6]|dt|th|strong|b)([^>]*)>(.*?)</\1>",
                             page, re.S | re.I):
            txt = squash(to_text(m.group(3)))
            if not txt or len(txt) > 60:
                continue
            cls = ""
            cm = re.search(r'class="([^"]*)"', m.group(2))
            if cm:
                cls = cm.group(1)[:26]
            print("    <%-8s class=%-28s %s" % (m.group(1), cls or "-", txt[:52]))
    print()


if __name__ == "__main__":
    main()
