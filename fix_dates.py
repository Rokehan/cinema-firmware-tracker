"""Make ARRI's own headline the authority for version and release date.

Why: the page h1 (e.g. "ALEXA SUP 11.1.1") and the date printed right under
it are what ARRI actually publishes. The scraper was reading the version off
the URL slug (stale for ALEXA Classic / XT, absent for the -sup-overview
pages) and the date off the first PDF label it found (wrong for most bodies).

This patches arri_cameras.py in place:
  1. adds headline_version_and_date(html)
  2. release_date  -> headline date first, PDF label only as fallback
  3. version       -> headline version first, find_version() as fallback

Dates are emitted in the same "Feb. 7, 2022" shape the scraper already used,
so build_feed.py keeps working unchanged. Nothing is invented: if the
headline has no date, the old behaviour applies.

Writes arri_cameras.py.bak. Refuses to save if the result does not parse.

Run once:  python3 fix_dates.py
"""

import ast
import re
import shutil

TARGET = "arri_cameras.py"

HELPER = '''
LONG_MONTHS = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov",
    "december": "Dec",
}

SHORT_MONTHS = ("Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec")

LONG_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)"
    r"\\s+(\\d{1,2})(?:st|nd|rd|th)?,\\s*(\\d{4})",
    re.I,
)

SHORT_DATE_RE = re.compile(
    r"(" + SHORT_MONTHS + r")\\.?\\s+(\\d{1,2}),\\s*(\\d{4})"
)


def visible_text(fragment):
    """Tags out, entities and runs of whitespace tidied."""
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = fragment.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\\s+", " ", fragment).strip()


def headline_version_and_date(html):
    """Read the version and release date straight off ARRI's own headline.

    Returns (version, date) with either value None when the page does not
    state it. The date comes back as "Feb. 7, 2022" to match the format the
    rest of the pipeline already expects.
    """
    heads = list(re.finditer(r"(?is)<h1[^>]*>(.*?)</h1>", html))
    if not heads:
        return None, None

    chosen = None
    for head in heads:
        if "sup" in visible_text(head.group(1)).lower():
            chosen = head
            break
    if chosen is None:
        chosen = heads[-1]

    title = visible_text(chosen.group(1))

    version = None
    found = re.search(r"SUP\\s+(\\d+(?:\\.\\d+)*)", title, re.I)
    if found:
        version = "SUP " + found.group(1).rstrip(".")

    # ARRI prints the release date immediately below the headline.
    window = visible_text(html[chosen.end():chosen.end() + 4000])[:400]

    date = None
    long_hit = LONG_DATE_RE.search(window)
    if long_hit:
        month = LONG_MONTHS.get(long_hit.group(1).lower())
        if month:
            date = month + ". " + str(int(long_hit.group(2))) + ", " + long_hit.group(3)
    if date is None:
        short_hit = SHORT_DATE_RE.search(window)
        if short_hit:
            date = (short_hit.group(1) + ". " + str(int(short_hit.group(2)))
                    + ", " + short_hit.group(3))

    return version, date

'''

OLD_DATE = ('    release_date = firmware[0]["date"] if firmware '
            'else (notes[0]["date"] if notes else None)')

NEW_DATE = '''    head_version, head_date = headline_version_and_date(html)

    fallback_date = firmware[0]["date"] if firmware else (
        notes[0]["date"] if notes else None)
    release_date = head_date or fallback_date'''

OLD_VERSION = "    version = find_version(slug, html, downloads)"
NEW_VERSION = "    version = head_version or find_version(slug, html, downloads)"

ANCHOR = "results = []"


def main():
    with open(TARGET, encoding="utf-8") as fh:
        text = fh.read()

    if "headline_version_and_date" in text:
        print("Already patched. Nothing to do.")
        return

    problems = []
    for needle in (OLD_DATE, OLD_VERSION, ANCHOR):
        if needle not in text:
            problems.append(needle.strip()[:60])
    if problems:
        print("Could not find these lines in " + TARGET + ":")
        for item in problems:
            print("  " + item)
        print("Nothing written.")
        return

    text = text.replace(ANCHOR, HELPER.lstrip(chr(10)) + chr(10) + ANCHOR, 1)
    text = text.replace(OLD_DATE, NEW_DATE, 1)
    text = text.replace(OLD_VERSION, NEW_VERSION, 1)

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
    print("Headline is now the authority for version and release date.")
    print("Next: python3 arri_cameras.py")


if __name__ == "__main__":
    main()
