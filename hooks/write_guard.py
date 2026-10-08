#!/usr/bin/env python3
"""PreToolUse hook for Bash: while a QA run is open, refuse shell HTTP writes to hosts that are not test hosts.

Active only when `<project>/<report_dir>/.active` exists, so it costs nothing outside QA. It recognises:
  curl   -X/--request POST|PUT|PATCH|DELETE, or a body flag (-d, --data*, -F, --form, --json, -T, --upload-file)
  wget   --method=POST|PUT|PATCH|DELETE, --post-data, --post-file, --body-data, --body-file
  httpie http|https|xh POST|PUT|PATCH|DELETE <url>, or `http <url> key=value` (implies POST)
Calls made through the plugin's qa_http.py are left alone: that script enforces the same rule itself.

Limits, stated in the README: a write sent from a script file, a programming-language one-liner, or a browser is not
seen here. Exit 2 blocks the call and shows the reason to Claude; any parsing problem exits 0 (the guard never
blocks work it cannot understand).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit

WRITES = {"POST", "PUT", "PATCH", "DELETE"}
CURL_BODY = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--data-ascii", "-F", "--form",
             "--form-string", "--json", "-T", "--upload-file"}
WGET_BODY = ("--post-data", "--post-file", "--body-data", "--body-file")


def parse_hosts(value: str) -> list[str]:
    return [h.strip().lower() for h in (value or "").split(",") if h.strip()]


def allowed(url: str, hosts: list[str]) -> bool:
    p = urlsplit(url if "://" in url else "http://" + url)
    host = (p.hostname or "").lower()
    return bool(host) and (host in hosts or (p.port and f"{host}:{p.port}" in hosts))


def segments(command: str) -> list[list[str]]:
    """Split on shell control operators, then into words. Unparseable input yields nothing."""
    out = []
    for part in re.split(r"\|\||&&|;|\||\n", command):
        try:
            words = shlex.split(part, posix=True)
        except ValueError:
            continue
        if words:
            out.append(words)
    return out


def write_targets(words: list[str]) -> list[str]:
    """URLs that this command would send a write request to; empty when it is not a write."""
    while words and (re.fullmatch(r"\w+=.*", words[0]) or words[0] in ("sudo", "env", "command", "time")):
        words = words[1:]
    if not words:
        return []
    prog = os.path.basename(words[0])
    urls = [w for w in words[1:] if re.match(r"^https?://", w)]
    if prog == "curl":
        method, body = None, False
        for i, w in enumerate(words):
            if w in ("-X", "--request") and i + 1 < len(words):
                method = words[i + 1].upper()
            elif w.startswith("--request="):
                method = w.split("=", 1)[1].upper()
            elif re.fullmatch(r"-X[A-Za-z]+", w):
                method = w[2:].upper()
            elif w in CURL_BODY or any(w.startswith(f + "=") for f in CURL_BODY if f.startswith("--")):
                body = True
        is_write = (method in WRITES) or (method is None and body)
        return urls if is_write else []
    if prog == "wget":
        is_write = any(w.split("=", 1)[0] in WGET_BODY for w in words) or any(
            w.startswith("--method=") and w.split("=", 1)[1].upper() in WRITES for w in words)
        return urls if is_write else []
    if prog in ("http", "https", "xh", "xhs"):
        rest = [w for w in words[1:] if not w.startswith("-")]
        if rest and rest[0].upper() in WRITES:
            return rest[1:2]
        if rest and any(re.match(r"^[\w.-]+:?=", w) for w in rest[1:]):
            return rest[:1]
    return []


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if event.get("tool_name") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command", "")
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    report_dir = os.environ.get("CLAUDE_PLUGIN_OPTION_REPORT_DIR") or "qa"
    if not (project / report_dir / ".active").exists() or "qa_http.py" in command:
        return 0
    hosts = parse_hosts(os.environ.get("CLAUDE_PLUGIN_OPTION_TEST_HOSTS", ""))
    bad = [u for words in segments(command) for u in write_targets(words) if not allowed(u, hosts)]
    if not bad:
        return 0
    sys.stderr.write(
        "nghiem write guard: a QA run is open and this command sends a write request to "
        + ", ".join(sorted(set(bad))) + ", which is not a configured test host ("
        + (", ".join(hosts) or "none configured") + "). Writes during QA only go to test servers. If this host is a "
        "test server, add it to the plugin's test_hosts setting; otherwise do not send the request.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
