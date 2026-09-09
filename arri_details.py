import urllib.request
import re
import json
import time

PAGES = [row["slug"] for row in json.load(open("arri_cameras.json"))]

BASE = "https://www.arri.com/en/technical-service/firmware/software-and-firmware-updates-for-cameras/"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode("utf-8")

def flat(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    t = t.replace("&nbsp;", " ").replace("&", "&").replace("&#39;", "'")
    return re.sub(r"\s+", " ", t).strip()

results = []

for slug in PAGES:
    url = BASE + slug
    print("Fetching: " + slug)
    html = fetch(url)

    # Cut off the licence agreement, it drowns everything
    cut = html.find("SOFTWARE LICENCE")
    if cut == -1:
        cut = html.find("SOFTWARE LICENCE")
    body = html[:cut] if cut > 0 else html

    text = flat(body)

    # Summary: the sentences right after the release date
    summary = None
    d = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}", text)
    if d:
        after = text[d.end():d.end() + 900]
        stop = re.search(r"New Features|Please review|We recommend|Downloads", after)
        chunk = after[:stop.start()] if stop else after
        # End on a sentence rather than mid-word
        if len(chunk) > 420:
            dot = chunk.rfind(". ", 0, 420)
            chunk = chunk[:dot + 1] if dot > 80 else chunk[:420].rsplit(" ", 1)[0]
        chunk = chunk.strip()
        if len(chunk) > 40:
            summary = chunk

    # Features: list items following the "New Features" heading
    features = []
    fm = re.search(r"New Features[^<]{0,40}|contains:|Highlights", body)
    if fm:
        region = body[fm.end():fm.end() + 4000]
        for item in re.findall(r"<li[^>]*>(.*?)</li>", region, re.DOTALL):
            label = flat(item)
            if 2 < len(label) < 90 and "http" not in label:
                features.append(label)
        features = features[:12]

    results.append({
        "slug": slug,
        "summary": summary,
        "features": features,
        "source_url": url,
    })

    print("  summary: " + (str(len(summary)) + " chars" if summary else "NONE"))
    if summary:
        print("      \"" + summary[:200] + "\"")
    print("  features: " + str(len(features)))
    for f in features[:6]:
        print("      " + f[:60])
    print()
    time.sleep(1)

with open("arri_details.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Saved to arri_details.json")
