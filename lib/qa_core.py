"""Shared helpers for the nghiem QA scripts. Python 3.9+, standard library only.

A QA run lives in one folder inside the project, by default `qa/<run-id>/`:

    CASES.md        the plan: requirements, cases, expected results and where each expectation comes from
    calls.tsv       every HTTP call the run made, with the exact command and status code
    results.tsv     one row per check: expected, actual, verdict, evidence
    build.tsv       fingerprint of the build under test, taken at the start and at the end of the run
    evidence/       response bodies, screenshots, query output
    report.md       written by the report skill from the files above

`<report_dir>/.active` names the run that is in progress; the write guard hook only acts while it exists.
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

RESULT_FIELDS = ["time", "case", "check", "expected", "actual", "verdict", "evidence", "note"]
CALL_FIELDS = ["n", "time", "case", "method", "url", "status", "ms", "evidence", "command"]
BUILD_FIELDS = ["time", "phase", "target", "fingerprint"]
VERDICTS = ("pass", "fail", "blocked")
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")

csv.field_size_limit(sys.maxsize)


def now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def run_dir(path: str) -> Path:
    d = Path(path)
    if not d.is_dir():
        sys.exit(f"nghiem: run folder not found: {d}")
    return d


def append_row(path: Path, fields: list[str], row: dict) -> None:
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="raise")
        if new:
            w.writeheader()
        w.writerow({k: _one_line(row.get(k, "")) for k in fields})


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _one_line(v) -> str:
    return str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def parse_hosts(value: str | None) -> list[str]:
    """`"staging.example.com, localhost:3000"` → `["staging.example.com", "localhost:3000"]`, lower-cased."""
    return [h.strip().lower() for h in (value or "").split(",") if h.strip()]


def host_allowed(url: str, hosts: list[str]) -> bool:
    """A host is allowed when it equals an entry, or an entry names host:port exactly. No wildcard, no suffix match:
    `example.com` does not allow `api.example.com`, because a suffix rule is how a staging allowlist ends up covering production."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        return False
    with_port = f"{host}:{parts.port}" if parts.port else host
    return host in hosts or with_port in hosts


SECRET_HEADER = re.compile(r"^(authorization|cookie|x-api-key|api-key|x-auth-token|proxy-authorization)$", re.I)
SECRET_PARAM = re.compile(r"(?i)\b(password|passwd|pass|token|secret|api_key|apikey|access_token)=([^&\s]+)")


def mask_header(name: str, value: str) -> str:
    return f"{name}: ***" if SECRET_HEADER.match(name.strip()) else f"{name}: {value}"


def mask_url(url: str) -> str:
    return SECRET_PARAM.sub(lambda m: f"{m.group(1)}=***", url)


def mask_body(body: str) -> str:
    """Hide values of password-like keys in a JSON or form body before it is printed or logged."""
    body = re.sub(r'(?i)("(?:password|passwd|pass|[a-z_]*token|secret|client_secret|api_key|apikey)"\s*:\s*)"[^"]*"',
                  r'\1"***"', body)
    return SECRET_PARAM.sub(lambda m: f"{m.group(1)}=***", body)


def evidence_path(run: Path, stem: str, suffix: str) -> Path:
    d = run / "evidence"
    d.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "item"
    p = d / f"{safe}{suffix}"
    i = 2
    while p.exists():
        p = d / f"{safe}-{i}{suffix}"
        i += 1
    return p


def rel(run: Path, p: Path) -> str:
    try:
        return str(p.relative_to(run))
    except ValueError:
        return str(p)
