#!/usr/bin/env python3
"""Check a QA plan (CASES.md) before any case is run.

    python3 check_plan.py <run folder or CASES.md>          findings, exit 1 when any is an error
    python3 check_plan.py <...> --json                      the same as JSON

Rules (P0–P9). The two that matter most:
  P4  an expected result whose oracle is the code under test cannot fail, so it is rejected
  P1  every requirement needs a case; a plan that skips a requirement reports full coverage of the wrong denominator
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from qa_plan import parse  # noqa: E402

TYPES = {"api", "ui", "db", "unit", "manual", "other"}
# Words that mean "the expected result was read off the implementation". Matched as whole phrases.
CODE_ORACLES = re.compile(
    r"^\s*(the\s+)?(code|source|source code|implementation|current (behaviou?r|output|response)|as implemented|"
    r"existing (behaviou?r|code)|what the (code|api|app) (does|returns)|the function|unit under test)\s*\.?\s*$",
    re.I)
PLACEHOLDER = re.compile(r"^<.*>$")


def check(text: str) -> list[dict]:
    p = parse(text)
    out = []

    def add(code, level, msg):
        out.append({"rule": code, "level": level, "message": msg})

    need = ["id", "covers", "type", "steps", "expected", "oracle"]
    missing = [c for c in need if c not in p["header"]]
    if missing:
        add("P0", "error", "Cases table must have the columns " + ", ".join(need) + "; missing: " + ", ".join(missing))
        return out
    if not p["requirements"]:
        add("P1", "error", "No requirements listed under '## Requirements' (lines like '- R1: ...')")
    seen, covered = set(), set()
    for c in p["cases"]:
        cid = c["id"] or "(no id)"
        if cid in seen:
            add("P5", "error", f"{cid}: duplicate case ID")
        seen.add(cid)
        refs = [r for r in re.split(r"[,\s]+", c["covers"]) if r]
        if not refs:
            add("P2", "error", f"{cid}: covers no requirement")
        for r in refs:
            if r not in p["requirements"]:
                add("P2", "error", f"{cid}: covers {r}, which is not in the requirements list")
            covered.add(r)
        for col in ("steps", "expected", "oracle"):
            v = c[col]
            if not v or PLACEHOLDER.match(v):
                add("P3", "error", f"{cid}: '{col}' is empty or still a template placeholder")
        if c["oracle"] and CODE_ORACLES.match(c["oracle"]):
            add("P4", "error", f"{cid}: the oracle is the code under test ('{c['oracle']}'); an expected result read off "
                               "the implementation cannot fail. Take it from the spec, the ticket, the data rules, a "
                               "reference screen, or ask the product owner")
        if re.match(r"^\s*(pending|ask)\b", c["oracle"], re.I):
            add("P9", "warning", f"{cid}: oracle is still an open question ('{c['oracle']}'); this case stays blocked "
                                 "until someone answers it")
        if c["type"].lower() not in TYPES:
            add("P7", "warning", f"{cid}: type '{c['type']}' is not one of {', '.join(sorted(TYPES))}")
    for r in p["requirements"]:
        if r not in covered:
            add("P1", "error", f"{r}: no case covers this requirement")
    if not p["cases"]:
        add("P6", "error", "No cases in the '## Cases' table")
    if not p["exit"]:
        add("P8", "error", "No exit criteria under '## Exit criteria'; the verdict is derived from them")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = Path(argv[0])
    if path.is_dir():
        path = path / "CASES.md"
    if not path.exists():
        print(f"check_plan: {path} not found")
        return 2
    findings = check(path.read_text(encoding="utf-8"))
    errors = [f for f in findings if f["level"] == "error"]
    if "--json" in argv:
        print(json.dumps({"file": str(path), "findings": findings, "errors": len(errors)}, indent=2))
    else:
        for f in findings:
            print(f"{f['level'].upper():7} {f['rule']}  {f['message']}")
        p = parse(path.read_text(encoding="utf-8"))
        print(f"check_plan: {len(p['requirements'])} requirements, {len(p['cases'])} cases, "
              f"{len(errors)} errors, {len(findings) - len(errors)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
