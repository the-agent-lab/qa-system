#!/usr/bin/env python3
"""Make one HTTP call for a QA case, log it, and keep the response as evidence.

    python3 qa_http.py --run <run folder> --case C1 --hosts "<test hosts>" --method GET --url https://staging.example.com/api/orders/42
    python3 qa_http.py ... --method POST --url ... --header "Content-Type: application/json" --data '{"qty": 2}' --expect-status 201

What it guarantees:
  - POST, PUT, PATCH and DELETE are refused (exit 3) unless the URL's host is in --hosts. Reads go anywhere.
  - The exact request is printed as a curl command, with Authorization, cookies and password-like values masked,
    and appended to calls.tsv together with the status code and the evidence file.
  - The response body is saved under evidence/. A call that never got a response is logged with status 0.
  - Password- and token-like values are masked in the response too, before it is printed or saved. To use a login
    token in later calls, pass --token-key access_token: the value is written to a separate file (mode 600, default
    <run>/.token) and later calls read it with --header "Authorization: Bearer $(cat <run>/.token)".
  - With --expect-status, a row is added to results.tsv: pass when the status matches, fail when it does not,
    blocked when there was no response at all.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import qa_core as q  # noqa: E402


def curl_line(method: str, url: str, headers: list[tuple[str, str]], data: str | None) -> str:
    parts = ["curl", "-sS", "-X", method, shlex.quote(q.mask_url(url))]
    for k, v in headers:
        parts += ["-H", shlex.quote(q.mask_header(k, v))]
    if data is not None:
        parts += ["--data", shlex.quote(q.mask_body(data))]
    return " ".join(parts)


def find_key(obj, key: str):
    """First value under `key` anywhere in a parsed JSON document."""
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (str, int)):
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            found = find_key(v, key)
            if found is not None:
                return found
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--hosts", default="", help="comma-separated test hosts that may receive writes")
    ap.add_argument("--method", default="GET")
    ap.add_argument("--url", required=True)
    ap.add_argument("--header", action="append", default=[])
    ap.add_argument("--data")
    ap.add_argument("--data-file")
    ap.add_argument("--expect-status", type=int)
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed test servers)")
    ap.add_argument("--token-key", help="JSON key in the response whose value is saved to --token-out")
    ap.add_argument("--token-out", help="file for the token (default <run>/.token, mode 600)")
    a = ap.parse_args(argv)

    run = q.run_dir(a.run)
    method = a.method.upper()
    data = Path(a.data_file).read_text(encoding="utf-8") if a.data_file else a.data
    headers = []
    for h in a.header:
        if ":" not in h:
            ap.error(f"header must look like 'Name: value': {h}")
        k, v = h.split(":", 1)
        headers.append((k.strip(), v.strip()))
    hosts = q.parse_hosts(a.hosts)
    cmd = curl_line(method, a.url, headers, data)

    if method in q.WRITE_METHODS and not q.host_allowed(a.url, hosts):
        print(f"qa_http: REFUSED {method} to a host that is not a configured test host.\n  {cmd}\n"
              f"  test hosts: {', '.join(hosts) or '(none configured)'}\n"
              "  Writes during QA only go to test servers. Add the host to the plugin's test_hosts setting if it is one.")
        return 3

    calls = q.read_rows(run / "calls.tsv")
    n = len(calls) + 1
    req = urllib.request.Request(a.url, method=method, data=data.encode("utf-8") if data is not None else None)
    for k, v in headers:
        req.add_header(k, v)
    ctx = ssl._create_unverified_context() if a.insecure else None
    t0 = time.monotonic()
    status, body, error, ctype = 0, b"", "", ""
    try:
        with urllib.request.urlopen(req, timeout=a.timeout, context=ctx) as r:
            status, body, ctype = r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        status, body, ctype = e.code, e.read(), e.headers.get("Content-Type", "") if e.headers else ""
    except (urllib.error.URLError, OSError, ValueError) as e:
        error = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
    ms = int((time.monotonic() - t0) * 1000)

    suffix = ".json" if "json" in ctype else ".txt"
    ev = q.evidence_path(run, f"{a.case}-call{n}", suffix)
    text = body.decode("utf-8", "replace")
    parsed = None
    if suffix == ".json":
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
        except ValueError:
            pass
    token_note = ""
    if a.token_key:
        tok = find_key(parsed, a.token_key) if parsed is not None else None
        if tok:
            out = Path(a.token_out) if a.token_out else run / ".token"
            out.write_text(str(tok), encoding="utf-8")
            os.chmod(out, 0o600)
            token_note = f"  token '{a.token_key}' saved to {out} (mode 600)"
        else:
            token_note = f"  token '{a.token_key}' not found in the response"
    text = q.mask_body(text)
    ev.write_text(f"# {cmd}\n# status {status}{' ' + error if error else ''}, {ms} ms\n\n{text}", encoding="utf-8")
    ev_rel = q.rel(run, ev)
    q.append_row(run / "calls.tsv", q.CALL_FIELDS, {"n": n, "time": q.now(), "case": a.case, "method": method,
                                                    "url": q.mask_url(a.url), "status": status, "ms": ms,
                                                    "evidence": ev_rel, "command": cmd})
    print(f"{cmd}\nstatus {status}{' (' + error + ')' if error else ''}  {ms} ms  evidence {ev_rel}{token_note}")
    print(text[:600] + ("…" if len(text) > 600 else ""))

    if a.expect_status is not None:
        verdict = "blocked" if status == 0 else ("pass" if status == a.expect_status else "fail")
        q.append_row(run / "results.tsv", q.RESULT_FIELDS, {
            "time": q.now(), "case": a.case, "check": f"{method} {q.mask_url(a.url)} status",
            "expected": a.expect_status, "actual": status or error, "verdict": verdict, "evidence": ev_rel,
            "note": "no response" if status == 0 else ""})
        print(f"result: {a.case} {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
