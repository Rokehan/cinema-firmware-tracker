"""Find where ARRI publishes its update instructions.

ARRI is the last manufacturer without install steps on the site. Two
possible sources:

  1. the SUP page itself, which may carry an update or installation section
  2. the release notes PDF, which ends with "Detailed instructions for the
     update process can be found at the end of this document"

This checks both, read-only. For the PDF it tries pypdf if available and
reports whether the instruction section is extractable, without writing
anything.

Run:  python3 arri_install_peek.py
"""

import json
import re
import urllib.request

BASE = ("https://www.arri.com/en/technical-service/firmware/"
        "software-and-firmware-updates-for-cameras/")

HEADING_RE = re.compile(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>")

INSTALL_WORDS = ("update", "install", "procedure", "how to", "usb",
                 "downgrade", "downdate", "registration")

PDF_MARKERS = ("Camera Update Procedure", "How to download", "update process",
               "USB memory stick", "Update Procedure", "prepare the USB")


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    return raw if binary else raw.decode("utf-8", "replace")


def flat(fragment):
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", fragment).strip()


def rows():
    with open("arri_cameras.json", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    data = rows()
    print("ARRI cameras in arri_cameras.json: " + str(len(data)))
    print("")

    first_pdf = None

    for row in data[:4]:
        slug = row.get("slug")
        url = row.get("source_url") or (BASE + str(slug))
        print("=" * 66)
        print(slug)
        try:
            html = fetch(url)
        except Exception as err:
            print("  fetch failed: " + str(err))
            print("")
            continue

        heads = []
        for level, raw in HEADING_RE.findall(html):
            title = flat(raw)
            if title and title not in heads:
                heads.append("h" + level + " " + title)
        print("  headings: " + str(len(heads)))
        for head in heads[:18]:
            mark = "  *" if any(w in head.lower() for w in INSTALL_WORDS) else "   "
            print("   " + mark + " " + head[:70])

        text = flat(html)
        for phrase in ("USB", "SUP file", "Menu > System", "factory reset",
                       "LICENSES"):
            if phrase.lower() in text.lower():
                start = text.lower().find(phrase.lower())
                print("  found '" + phrase + "': "
                      + text[max(0, start - 70):start + 110])

        if not first_pdf and row.get("release_notes_download"):
            first_pdf = (slug, row["release_notes_download"])
        print("")

    print("=" * 66)
    print("RELEASE NOTES PDF")
    print("=" * 66)
    if not first_pdf:
        print("  no release notes link in arri_cameras.json")
        return

    slug, pdf_url = first_pdf
    print("  " + slug)
    print("  " + pdf_url[:96])

    try:
        import pypdf
    except ImportError:
        print("")
        print("  pypdf is not installed, so the pdf cannot be read here.")
        print("  Install it with:  pip install pypdf")
        print("  Then run this again.")
        return

    try:
        raw = fetch(pdf_url, binary=True)
    except Exception as err:
        print("  download failed: " + str(err))
        return

    print("  bytes: " + str(len(raw)))

    import io
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
    except Exception as err:
        print("  could not open as pdf: " + str(err))
        return

    print("  pages: " + str(len(reader.pages)))

    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")

    whole = "\n".join(pages)
    print("  extracted characters: " + str(len(whole)))

    for marker in PDF_MARKERS:
        index = whole.lower().find(marker.lower())
        print("  '" + marker + "': "
              + ("page " + str(next(
                  (i + 1 for i, p in enumerate(pages)
                   if marker.lower() in p.lower()), 0))
                 if index > -1 else "not found"))

    hit = None
    for marker in ("Camera Update Procedure", "Update Procedure"):
        index = whole.find(marker)
        if index > -1:
            hit = index
            break
    if hit is None:
        print("")
        print("  No update-procedure section found. Paste this output.")
        return

    chunk = whole[hit:hit + 1400]
    print("")
    print("  update section, as extracted:")
    for line in chunk.split("\n")[:26]:
        line = " ".join(line.split())
        if line:
            print("    | " + line[:96])

    print("")
    print("Nothing was written. Paste this output.")


if __name__ == "__main__":
    main()
