#!/usr/bin/env python3
"""
js_find.py  -  locate the exact JavaScript syntax error in index.html.
Offline. Reads index.html only. Writes nothing.

My brace counter said "unclosed '('" which is too vague, and it can be fooled by
a paren inside a regex literal such as /\\s+/ or inside a string. This does a
proper tokenizing scan that understands:
    - line and block comments
    - single, double and template strings, with escapes
    - regex literals, distinguished from division by what precedes them
and reports every unbalanced bracket with its line, plus the surrounding code.

It also lists every identifier that is used but never declared in the script,
which catches a leftover reference from a half-applied patch.

Run:  python js_find.py
"""
from pathlib import Path
import re
import sys

NL = chr(10)

PRE_REGEX = set("(,=:[!&|?{};+-*%~^<>") | {"return", "typeof", "case", "in",
                                           "of", "new", "delete", "void",
                                           "instanceof", "do", "else", "yield"}


def scan(src):
    """Yield (index, line, kind, char) for structural brackets only."""
    out = []
    i = 0
    n = len(src)
    line = 1
    prev_significant = ""
    stack = []
    problems = []
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        if ch == NL:
            line += 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue

        # comments
        if ch == "/" and nxt == "/":
            while i < n and src[i] != NL:
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                if src[i] == NL:
                    line += 1
                i += 1
            i += 2
            continue

        # strings
        if ch in "\"'`":
            quote = ch
            start_line = line
            i += 1
            closed = False
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == NL:
                    line += 1
                    if quote != "`":
                        problems.append("line " + str(start_line)
                                        + ": unterminated " + quote + " string")
                        break
                if src[i] == quote:
                    closed = True
                    i += 1
                    break
                i += 1
            if not closed and quote == "`":
                problems.append("line " + str(start_line)
                                + ": unterminated template string")
            prev_significant = quote
            continue

        # regex literal, only where a value can start
        if ch == "/":
            if prev_significant == "" or prev_significant in PRE_REGEX \
                    or prev_significant.isalpha() is False:
                j = i + 1
                closed = False
                inclass = False
                while j < n and src[j] != NL:
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == "[":
                        inclass = True
                    elif src[j] == "]":
                        inclass = False
                    elif src[j] == "/" and not inclass:
                        closed = True
                        break
                    j += 1
                if closed:
                    i = j + 1
                    prev_significant = "/"
                    continue
            i += 1
            prev_significant = "/"
            continue

        if ch in "([{":
            stack.append((ch, line))
            prev_significant = ch
            i += 1
            continue
        if ch in ")]}":
            want = {")": "(", "]": "[", "}": "{"}[ch]
            if not stack:
                problems.append("line " + str(line) + ": extra '" + ch + "'")
            elif stack[-1][0] != want:
                problems.append("line " + str(line) + ": '" + ch
                                + "' closes '" + stack[-1][0]
                                + "' opened on line " + str(stack[-1][1]))
                stack.pop()
            else:
                stack.pop()
            prev_significant = ch
            i += 1
            continue

        # words, for the regex-vs-division decision
        if ch.isalnum() or ch in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev_significant = src[i:j]
            i = j
            continue

        prev_significant = ch
        i += 1

    for ch, ln in stack:
        problems.append("unclosed '" + ch + "' opened on line " + str(ln))
    return problems


def main():
    p = Path("index.html")
    if not p.exists():
        sys.exit("index.html not found")
    html = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<script[^>]*>(.*?)</script>", html, re.S | re.I)
    if not m:
        sys.exit("no inline script found")
    body = m.group(1)
    offset = html[:m.start(1)].count(NL)

    print("script body: " + str(len(body)) + " chars, starts at html line "
          + str(offset + 1))
    print()
    probs = scan(body)
    if not probs:
        print("PARSES CLEAN. The brackets all balance.")
        print("If the page still does nothing, the error is runtime, not")
        print("syntax: open the browser console and read the red line.")
    else:
        print("PROBLEMS:")
        for pr in probs:
            print("  " + pr)
        print()
        lines = body.split(NL)
        for pr in probs[:4]:
            mm = re.search(r"line (\d+)", pr)
            if not mm:
                continue
            ln = int(mm.group(1))
            print("  --- script line " + str(ln)
                  + "  (html line " + str(offset + ln) + ") ---")
            for j in range(max(0, ln - 4), min(len(lines), ln + 4)):
                mark = ">>" if j + 1 == ln else "  "
                print("  %s %5d| %s" % (mark, j + 1, lines[j][:126]))
            print()

    # identifiers used but never declared
    declared = set(re.findall(r"\b(?:var|let|const|function)\s+([A-Za-z_$][\w$]*)",
                              body))
    declared |= set(re.findall(r"function\s*\(([^)]*)\)", body)[0].split(",")) \
        if re.search(r"function\s*\(", body) else set()
    used = set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*(?=[.\[(])", body))
    builtin = {"document", "window", "String", "Number", "Object", "Array",
               "JSON", "Math", "console", "Boolean", "parseInt", "parseFloat",
               "encodeURIComponent", "decodeURIComponent", "setTimeout",
               "isNaN", "RegExp", "Date", "Promise", "fetch", "location",
               "history", "navigator", "localStorage", "if", "for", "while",
               "return", "function", "catch", "switch", "typeof", "new"}
    suspect = sorted(u for u in used - declared - builtin
                     if not u[0].isupper() and len(u) > 2)
    print("identifiers used but not declared in this script:")
    if suspect:
        for u in suspect[:18]:
            first = None
            for i, l in enumerate(body.split(NL)):
                if re.search(r"\b" + re.escape(u) + r"\b", l):
                    first = i + 1
                    break
            print("  %-22s first at script line %s" % (u, first))
    else:
        print("  none")
    print()


if __name__ == "__main__":
    main()
