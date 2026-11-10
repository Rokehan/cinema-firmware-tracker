#!/usr/bin/env python3
"""Apply approved Firmware Tracker updates from the ClickUp update shelf.

How it works
  1. Reads the shelf task through the ClickUp API (token from the
     CLICKUP_TOKEN secret, which never leaves GitHub).
  2. Looks for attachments named fwtracker-update-NNNN.zip uploaded by an
     allowed person, newer than the last update applied here.
  3. Downloads and checks the oldest pending one, then writes its files.
  4. The workflow then runs the full refresh. Only if every step passes is
     anything committed, so a bad package can never take the site down.

Commands
  python clickup_updater.py fetch     find + check + apply one pending package
  python clickup_updater.py finish    record success in the state file
  python clickup_updater.py fail      record a rejection in the state file
  python clickup_updater.py notify    post the recorded result on the shelf

A package is a zip holding manifest.json plus files/<name>:
  {"format": 1, "update": 7, "summary": "What changed",
   "files": {"arri_kit.py": "<sha256>"}, "delete": []}
Only top-level .py/.json/.txt/.md/.html files may change. The workflow,
this updater, its state and the generated data cannot, so the disappearance
check and the refresh stamp stay trustworthy. Scripts must compile and JSON
must parse before anything is written.
"""
import hashlib
import io
import json
import os
import py_compile
import re
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

API = os.environ.get("CLICKUP_API_BASE", "https://api.clickup.com/api/v2")
STATE = Path("clickup_update_state.json")
PENDING = Path(".clickup_pending.json")
MESSAGE = Path(".clickup_message.txt")
NAME_RX = re.compile(r"^fwtracker-update-(\d{4})\.zip$")
FILE_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.(py|json|txt|md|html)$")
PROTECTED = {
    "clickup_updater.py", "clickup_update_state.json", "last_refresh.json",
    "snapshot.json", "feed.json", "index.html", ".clickup_pending.json",
}
MAX_BYTES = 20 * 1024 * 1024


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None or value == "":
        sys.exit("Missing setting: " + name)
    return value


def output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(key + "=" + str(value) + chr(10))


def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + chr(10))
    print(text)


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"last_update": 0, "applied": [], "rejected": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2) + chr(10), encoding="utf-8")


def request(url, token=None, data=None, method=None):
    headers = {"User-Agent": "cinema-firmware-tracker-updater"}
    if token:
        headers["Authorization"] = token
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("download larger than 20 MB")
    return body


def comment(text):
    token = os.environ.get("CLICKUP_TOKEN")
    task = os.environ.get("SHELF_TASK_ID")
    if not (token and task):
        return
    try:
        request(API + "/task/" + task + "/comment", token,
                {"comment_text": text, "notify_all": False}, "POST")
    except Exception as exc:
        print("Could not post the result to ClickUp: " + str(exc))


def candidates(task, state, allowed):
    found = []
    for att in task.get("attachments") or []:
        if att.get("deleted"):
            continue
        name = str(att.get("title") or "").strip()
        m = NAME_RX.match(name)
        if not m:
            continue
        number = int(m.group(1))
        if number <= int(state.get("last_update") or 0):
            continue
        uploader = str((att.get("user") or {}).get("id") or "")
        if allowed and uploader not in allowed:
            print("Skipping " + name + ": uploaded by user " + (uploader or "unknown")
                  + ", not an allowed uploader.")
            continue
        found.append((number, name, att))
    found.sort(key=lambda row: row[0])
    return found


def download(att, token):
    urls = [u for u in (att.get("url"), att.get("url_w_host")) if u]
    last = None
    for url in urls:
        for auth in (token, None):
            try:
                return request(url, auth)
            except Exception as exc:
                last = exc
    raise RuntimeError("could not download the package: " + str(last))


def safe_member(name):
    return (name and not name.startswith("/") and "\\" not in name
            and ".." not in name.split("/"))


def check_package(raw, number):
    """Return (manifest, {path: bytes}) or raise ValueError with the reason."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ValueError("not a zip file")
    names = zf.namelist()
    for name in names:
        if not safe_member(name):
            raise ValueError("unsafe path in zip: " + name)
        if (zf.getinfo(name).external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("symlink in zip: " + name)
        if name != "manifest.json" and not name.startswith("files/"):
            raise ValueError("unexpected entry in zip: " + name)
    if "manifest.json" not in names:
        raise ValueError("manifest.json missing")
    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    if manifest.get("format") != 1:
        raise ValueError("unsupported manifest format")
    if int(manifest.get("update", -1)) != number:
        raise ValueError("manifest update number does not match the file name")
    files = manifest.get("files") or {}
    delete = manifest.get("delete") or []
    if not isinstance(files, dict) or not isinstance(delete, list):
        raise ValueError("manifest files/delete have the wrong shape")
    payload = {}
    with tempfile.TemporaryDirectory() as tmp:
        for path, digest in files.items():
            if not FILE_RX.match(path) or path in PROTECTED:
                raise ValueError("file not allowed in updates: " + path)
            member = "files/" + path
            if member not in names:
                raise ValueError("listed file missing from zip: " + path)
            data = zf.read(member)
            if hashlib.sha256(data).hexdigest() != str(digest).lower():
                raise ValueError("checksum mismatch: " + path)
            if path.endswith(".py"):
                probe = Path(tmp) / path
                probe.write_bytes(data)
                try:
                    py_compile.compile(str(probe), doraise=True)
                except py_compile.PyCompileError as exc:
                    raise ValueError("does not compile: " + path + ": " + str(exc))
            if path.endswith(".json"):
                try:
                    json.loads(data.decode("utf-8"))
                except ValueError:
                    raise ValueError("invalid JSON: " + path)
            payload[path] = data
        extra = [n for n in names if n.startswith("files/") and not n.endswith("/")
                 and n[6:] not in files]
        if extra:
            raise ValueError("zip holds files the manifest does not list: " + ", ".join(extra))
    for path in delete:
        if not FILE_RX.match(path) or path in PROTECTED or path in payload:
            raise ValueError("delete not allowed: " + path)
    return manifest, payload


def cmd_fetch():
    token = os.environ.get("CLICKUP_TOKEN")
    if not token:
        output("status", "none")
        summary("CLICKUP_TOKEN secret not set yet, so the shelf was not checked.")
        return
    task_id = env("SHELF_TASK_ID")
    allowed = {u.strip() for u in os.environ.get("ALLOWED_UPLOADERS", "").split(",") if u.strip()}
    state = load_state()
    try:
        task = json.loads(request(API + "/task/" + task_id, token))
    except urllib.error.HTTPError as exc:
        sys.exit("ClickUp refused the shelf request (HTTP " + str(exc.code)
                 + "). Check the CLICKUP_TOKEN secret.")
    rejected = {r.get("sha256") for r in state.get("rejected", [])}
    for number, name, att in candidates(task, state, allowed):
        raw = download(att, token)
        digest = hashlib.sha256(raw).hexdigest()
        if digest in rejected:
            print("Skipping " + name + ": this exact file was rejected before.")
            continue
        pending = {"update": number, "name": name, "sha256": digest,
                   "attachment_id": att.get("id")}
        try:
            manifest, payload = check_package(raw, number)
        except Exception as exc:
            pending["reason"] = str(exc)
            PENDING.write_text(json.dumps(pending), encoding="utf-8")
            output("status", "invalid")
            summary("Update " + name + " rejected before install: " + str(exc))
            return
        for path, data in payload.items():
            Path(path).write_bytes(data)
        for path in manifest.get("delete") or []:
            if Path(path).exists():
                Path(path).unlink()
        pending["summary"] = str(manifest.get("summary") or "")
        pending["files"] = sorted(payload)
        pending["delete"] = sorted(manifest.get("delete") or [])
        PENDING.write_text(json.dumps(pending), encoding="utf-8")
        output("status", "applied")
        output("paths", " ".join(pending["files"] + pending["delete"]))
        summary("Applied " + name + " (" + str(len(payload)) + " file(s)): " + pending["summary"])
        return
    output("status", "none")
    summary("No new approved update on the shelf.")


def cmd_finish():
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    state = load_state()
    state["last_update"] = pending["update"]
    state.setdefault("applied", []).append({
        "update": pending["update"], "name": pending["name"],
        "sha256": pending["sha256"], "summary": pending.get("summary", ""),
        "files": pending.get("files", []), "delete": pending.get("delete", []),
        "applied_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    save_state(state)
    MESSAGE.write_text("Firmware Tracker: " + pending["name"] + " installed. The full refresh "
                       "passed and the site was published. " + pending.get("summary", ""),
                       encoding="utf-8")


def cmd_fail():
    if not PENDING.exists():
        return
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    reason = pending.get("reason") or "the full refresh failed after applying it"
    state = load_state()
    state.setdefault("rejected", []).append({
        "update": pending["update"], "name": pending["name"],
        "sha256": pending["sha256"], "reason": reason,
        "rejected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    save_state(state)
    run = os.environ.get("RUN_URL", "")
    MESSAGE.write_text("Firmware Tracker: " + pending["name"] + " NOT installed (" + reason
                       + "). The live site is unchanged. " + run, encoding="utf-8")


def cmd_notify():
    if MESSAGE.exists():
        comment(MESSAGE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    {"fetch": cmd_fetch, "finish": cmd_finish, "fail": cmd_fail,
     "notify": cmd_notify}[sys.argv[1]]()
