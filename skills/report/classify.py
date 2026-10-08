#!/usr/bin/env python3
"""Sort every failed check of a run into one class, with fixed rules, before anyone calls it a bug.

    python3 classify.py <run folder>            writes classification.tsv and prints it
    python3 classify.py <run folder> --json

Classes, tried in this order for each failed check (first rule that applies wins):
  R1  noted              a row in notes.tsv (case, class, reason) from someone who knows: the product owner says the
                         behaviour changed on purpose → intended-change, and so on. The reason is required.
  R2  broken-check       the evidence file is missing, or the actual value is empty: the check did not measure anything
  R3  environment        the linked HTTP call got no response or a 5xx status: the server, not the feature, failed
  R4  unclear            the case's oracle is still pending, so there is no agreed expected result to fail against
  R5  suspected-bug      everything else: the product did something other than what the source says

"suspected-bug" is the strongest claim QA makes, and it is still a suspicion: the skeptic agent of this plugin reviews
each one before the report goes out. Blocked checks are not failures and are listed separately as not run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
import qa_core as q  # noqa: E402
from qa_plan import parse, pending_oracle  # noqa: E402

CLASSES = ("intended-change", "broken-check", "environment", "unclear", "suspected-bug")
CLASS_FIELDS = ["case", "check", "class", "rule", "reason"]


def classify(run: Path) -> list[dict]:
    plan = parse((run / "CASES.md").read_text(encoding="utf-8")) if (run / "CASES.md").exists() else {"cases": []}
    oracle = {c.get("id", ""): c.get("oracle", "") for c in plan["cases"]}
    calls = {r["evidence"]: r for r in q.read_rows(run / "calls.tsv")}
    calls_by_n = {r["n"]: r for r in q.read_rows(run / "calls.tsv")}
    notes = {}
    for r in q.read_rows(run / "notes.tsv"):
        if r.get("class") in CLASSES and r.get("reason", "").strip():
            notes[r["case"]] = r
    out = []
    for r in q.read_rows(run / "results.tsv"):
        if r.get("verdict") != "fail":
            continue
        case, ev = r["case"], r.get("evidence", "")
        call = calls_by_n.get(ev.split(":", 1)[1]) if ev.startswith("call:") else calls.get(ev)
        ev_exists = (ev.startswith("call:") and call is not None) or (bool(ev) and (run / ev).is_file()) \
            or (bool(ev) and Path(ev).is_absolute() and Path(ev).is_file())
        status = int(call["status"]) if call and str(call.get("status", "")).isdigit() else None
        if case in notes:
            cls, rule, why = notes[case]["class"], "R1", notes[case]["reason"]
        elif not ev_exists or not r.get("actual", "").strip():
            cls, rule, why = "broken-check", "R2", "evidence missing" if not ev_exists else "actual value is empty"
        elif status is not None and (status == 0 or status >= 500):
            cls, rule, why = "environment", "R3", f"HTTP {status} from the server"
        elif pending_oracle(oracle.get(case, "")):
            cls, rule, why = "unclear", "R4", f"oracle still pending: {oracle[case]}"
        else:
            cls, rule, why = "suspected-bug", "R5", f"expected {r.get('expected')!r}, observed {r.get('actual')!r}"
        out.append({"case": case, "check": r.get("check", ""), "class": cls, "rule": rule, "reason": why})
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    run = q.run_dir(argv[0])
    rows = classify(run)
    path = run / "classification.tsv"
    if path.exists():
        path.unlink()
    for r in rows:
        q.append_row(path, CLASS_FIELDS, r)
    if "--json" in argv:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        for r in rows:
            print(f"{r['case']:6} {r['class']:16} {r['rule']}  {r['reason']}")
        print(f"classify: {len(rows)} failed checks → " + ", ".join(
            f"{c} {sum(1 for r in rows if r['class'] == c)}" for c in CLASSES if any(r["class"] == c for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
