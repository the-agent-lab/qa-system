#!/usr/bin/env python3
"""Fingerprint the build that is actually being served, at the start and at the end of a run.

    python3 pin_build.py --run <run folder> --phase start --url https://staging.example.com/
    python3 pin_build.py --run <run folder> --phase end   --url https://staging.example.com/
    python3 pin_build.py --run <run folder> --phase start --command "git -C ../api rev-parse HEAD"

A run tests whatever was deployed, not what is on your branch. The fingerprint is a SHA-256 of the page or version
endpoint body (plus ETag and Last-Modified when present), or of a command's output. If the start and end
fingerprints of a target differ, the build changed during the run and the report marks the run inconclusive.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import qa_core as q  # noqa: E402


def fingerprint_url(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        tag = r.headers.get("ETag", "") or ""
        mod = r.headers.get("Last-Modified", "") or ""
    return "sha256:" + hashlib.sha256(body).hexdigest()[:16] + (f" etag:{tag}" if tag else "") + (f" modified:{mod}" if mod else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--phase", choices=("start", "end"), required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url")
    g.add_argument("--command")
    ap.add_argument("--timeout", type=float, default=30)
    a = ap.parse_args(argv)
    run = q.run_dir(a.run)
    target = a.url or a.command
    try:
        if a.url:
            fp = fingerprint_url(a.url, a.timeout)
        else:
            out = subprocess.run(a.command, shell=True, capture_output=True, text=True, timeout=a.timeout)
            if out.returncode:
                print(f"pin_build: command failed ({out.returncode}): {out.stderr.strip()[:300]}")
                return 1
            fp = "sha256:" + hashlib.sha256(out.stdout.encode()).hexdigest()[:16] + f" out:{out.stdout.strip()[:40]}"
    except Exception as e:  # noqa: BLE001 - any failure to fingerprint is reported, not raised
        print(f"pin_build: could not fingerprint {target}: {e}")
        return 1
    q.append_row(run / "build.tsv", q.BUILD_FIELDS, {"time": q.now(), "phase": a.phase, "target": target, "fingerprint": fp})
    print(f"pin_build: {a.phase} {target} → {fp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
