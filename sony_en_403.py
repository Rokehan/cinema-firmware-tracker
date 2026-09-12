"""Diagnose Sony's 403 on sony.com and find a header set that works.

sony.com refused a plain urllib request. That is usually a bot filter keyed
on missing browser headers rather than a real block, so this tries a few
combinations on one page and reports which get through.

Tries, in order:
  1. plain urllib (the current behaviour, expected to fail)
  2. a full browser header set
  3. the same plus gzip handling
  4. the same plus a Referer, as if arriving from the downloads page

Writes nothing. Read-only.

Run:  python3 sony_en_403.py
"""

import gzip
import io
import urllib.error
import urllib.request
import zlib

TARGET = "https://www.sony.com/electronics/support/software/00259043"

BROWSER = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/127.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="127", "Not)A;Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Connection": "keep-alive",
}


def decode(raw, encoding):
    if encoding == "gzip":
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    elif encoding == "deflate":
        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw.decode("utf-8", "replace")


def attempt(label, headers):
    print("--- " + label)
    req = urllib.request.Request(TARGET, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            encoding = response.headers.get("Content-Encoding", "")
            body = decode(raw, encoding)
            print("    status: " + str(response.status))
            print("    bytes:  " + str(len(body)))
            print("    encoding: " + (encoding or "none"))
            marker = "BODYDATA.DAT" in body
            print("    mentions BODYDATA.DAT: " + str(marker))
            if "Version:" in body:
                start = body.find("Version:")
                print("    near 'Version:': "
                      + " ".join(body[start:start + 90].split()))
            return True
    except urllib.error.HTTPError as err:
        print("    HTTP " + str(err.code) + " " + str(err.reason))
        server = err.headers.get("Server") if err.headers else None
        if server:
            print("    server: " + server)
    except Exception as err:
        print("    failed: " + str(err))
    return False


def main():
    print("Target: " + TARGET)
    print("")

    ok = attempt("1. plain urllib", {"User-Agent": "Mozilla/5.0"})
    print("")

    if not ok:
        ok = attempt("2. full browser headers", dict(BROWSER))
        print("")

    if not ok:
        headers = dict(BROWSER)
        headers["Accept-Encoding"] = "gzip, deflate"
        ok = attempt("3. browser headers + gzip", headers)
        print("")

    if not ok:
        headers = dict(BROWSER)
        headers["Accept-Encoding"] = "gzip, deflate"
        headers["Referer"] = ("https://www.sony.com/electronics/support/"
                              "interchangeable-lens-camcorders-ilme-series/"
                              "ilme-fx6v/downloads")
        headers["Sec-Fetch-Site"] = "same-origin"
        ok = attempt("4. browser headers + gzip + referer", headers)
        print("")

    if ok:
        print("A header set works. The scraper can use it.")
    else:
        print("Every attempt refused. sony.com is blocking server-side")
        print("requests, so the English pages need a different approach.")


if __name__ == "__main__":
    main()
