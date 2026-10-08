#!/usr/bin/env python3
"""Scan every tracked file for things that must never be published, before a release or a visibility change.

    python3 tools/prepublish_scan.py              scan `git ls-files`, exit 1 on any finding
    python3 tools/prepublish_scan.py --list       also print the files scanned

Why this exists: version 1.x of this project shipped an example config with real test-server accounts (phone-number
usernames and plain passwords) in a public repository for six months. gitleaks scanned the full history and reported
nothing, because it looks for credentials with a known format and a plain password in a JSON config has none.

What it looks for:
  S1  a password, secret, token or API key assigned a literal value (JSON, YAML, env, code)
  S2  a phone number: Vietnamese mobile (0xxxxxxxxx, +84...) or any E.164 number
  S3  a 12-digit number, the shape of a national ID number
  S4  a host name from your private deny list: NGHIEM_LEAK_DENY="corp.example,internal.example" or one per line in
      ~/.config/nghiem/leak-deny.txt. The list lives OUTSIDE the repository, because publishing it would leak it.
Values that are clearly fake are skipped (***, <placeholder>, ${VAR}, $VAR, changeme, example). A deliberate fake in a
test is marked on its own line with the comment `leakscan: fake`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ASSIGN = re.compile(r"""(?ix)["']?\b(password|passwd|pwd|secret|client_secret|token|access_token|refresh_token|api[_-]?key)\b["']?
                        \s*[:=]\s*["']([^"'\s,}{]{3,})["']""")
PHONE = re.compile(r"(?<![\w.-])(?:\+84|0)(?:3|5|7|8|9)\d{8}(?![\w-])|(?<![\w.-])\+[1-9]\d{9,13}(?![\w-])")
ID12 = re.compile(r"(?<![\w.-])\d{12}(?![\w-])")
FAKE = re.compile(r"^(\*+|<.*>|\$\{?\w+\}?|changeme|example.*|placeholder|redacted|xxx+|your[-_].*|none|null|true|false)$", re.I)
MARK = "leakscan: fake"
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf"}


def deny_list() -> list[str]:
    hosts = [h.strip().lower() for h in os.environ.get("NGHIEM_LEAK_DENY", "").split(",") if h.strip()]
    f = Path.home() / ".config" / "nghiem" / "leak-deny.txt"
    if f.exists():
        hosts += [l.strip().lower() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")]
    return hosts


def scan_text(path: str, text: str, deny: list[str]) -> list[tuple[str, int, str]]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if MARK in line:
            continue
        for m in ASSIGN.finditer(line):
            if not FAKE.match(m.group(2)):
                out.append(("S1", i, f"{m.group(1)} has a literal value"))
        if PHONE.search(line):
            out.append(("S2", i, "phone number"))
        if ID12.search(line):
            out.append(("S3", i, "12-digit number (national ID shape)"))
        low = line.lower()
        for h in deny:
            if h in low:
                out.append(("S4", i, f"deny-listed host ({h[:3]}…)"))
    return [(c, i, f"{path}:{i}: {msg}") for c, i, msg in out]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or ".")
    files = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"], capture_output=True,
                           text=True).stdout.split("\n")
    deny = deny_list()
    findings = []
    for f in filter(None, files):
        p = root / f
        if p.suffix.lower() in SKIP_EXT or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(("S0", 0, f"{f}: binary file in a text-only plugin"))
            continue
        findings += scan_text(f, text, deny)
        if "--list" in argv:
            print(f"scanned {f}")
    for _, _, msg in findings:
        print(msg)
    print(f"prepublish_scan: {len([f for f in files if f])} files, {len(findings)} finding(s), "
          f"deny list {'loaded (' + str(len(deny)) + ' hosts)' if deny else 'EMPTY: S4 did not run'}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
