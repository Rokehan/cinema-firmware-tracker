import json
import os

SNAPSHOT = "snapshot.json"

with open("feed.json") as f:
    current = json.load(f)

def key(r):
    return r["manufacturer"] + " " + str(r["product"])

now = {key(r): r for r in current}

if not os.path.exists(SNAPSHOT):
    with open(SNAPSHOT, "w") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    print("First run. Saved baseline of " + str(len(now)) + " cameras.")
    print("Run this again after the next scrape to see changes.")
    raise SystemExit

with open(SNAPSHOT) as f:
    before = {key(r): r for r in json.load(f)}

added = [k for k in now if k not in before]
removed = [k for k in before if k not in now]
changed = []
for k in now:
    if k in before and now[k]["version"] != before[k]["version"]:
        changed.append((k, before[k]["version"], now[k]["version"]))

print("Cameras: " + str(len(before)) + " before, " + str(len(now)) + " now")
print()

if changed:
    print("NEW FIRMWARE:")
    for k, old, new in changed:
        print("  " + k + ": " + str(old) + " -> " + str(new))
    print()

if added:
    print("NEW CAMERAS:")
    for k in added:
        print("  " + k + " " + str(now[k]["version"]))
    print()

if removed:
    print("*** WARNING: cameras disappeared ***")
    for k in removed:
        print("  " + k)
    print("A scraper may be broken. Snapshot NOT updated.")
    print("Investigate before re-running.")
    raise SystemExit(1)

if not (changed or added):
    print("No changes.")
    print()

with open(SNAPSHOT, "w") as f:
    json.dump(current, f, indent=2, ensure_ascii=False)
print("Snapshot updated.")