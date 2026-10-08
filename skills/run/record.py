#!/usr/bin/env python3
"""Record the verdict of one check, with its evidence.

    python3 record.py --run <run folder> --case C2 --check "orders row count after submit" \
        --expected 1 --actual 1 --evidence evidence/C2-count.txt
    python3 record.py ... --verdict blocked --note "staging returned 502 for 20 minutes" --evidence call:7

Rules:
  - No evidence, no verdict. --evidence must be a file (relative to the run folder or absolute) that exists, or
    `call:<n>` pointing at a row of calls.tsv. A check you could not run is `blocked`, and still needs the output of
    the attempt as evidence.
  - Without --verdict, pass means expected equals actual after trimming whitespace; anything else is fail. Give
    --verdict explicitly for checks that are not equality ("contains", "at most") and say why in --note.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import qa_core as q  # noqa: E402


def evidence_ok(run: Path, ev: str) -> bool:
    if ev.startswith("call:"):
        n = ev.split(":", 1)[1]
        return any(r.get("n") == n for r in q.read_rows(run / "calls.tsv"))
    p = Path(ev)
    return (p if p.is_absolute() else run / p).is_file()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--check", required=True)
    ap.add_argument("--expected", required=True)
    ap.add_argument("--actual", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--verdict", choices=q.VERDICTS)
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    run = q.run_dir(a.run)
    if not evidence_ok(run, a.evidence):
        print(f"record: evidence '{a.evidence}' not found in {run}; a verdict without evidence is not recorded")
        return 2
    verdict = a.verdict or ("pass" if a.expected.strip() == a.actual.strip() else "fail")
    if a.verdict and a.verdict != "blocked" and not a.note:
        expected_by_equality = "pass" if a.expected.strip() == a.actual.strip() else "fail"
        if a.verdict != expected_by_equality:
            print("record: --verdict differs from a plain comparison of expected and actual; say why in --note")
            return 2
    q.append_row(run / "results.tsv", q.RESULT_FIELDS, {
        "time": q.now(), "case": a.case, "check": a.check, "expected": a.expected, "actual": a.actual,
        "verdict": verdict, "evidence": a.evidence, "note": a.note})
    print(f"result: {a.case} {verdict}  ({a.check})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
