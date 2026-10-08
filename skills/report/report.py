#!/usr/bin/env python3
"""Write report.md for a QA run from its plan, results, calls and build fingerprints; then check it.

    python3 report.py <run folder>            classify failures, write report.md, check it, print the verdict
    python3 report.py <run folder> --check    only check an existing report.md (after a person edited it)

Verdict, derived rather than chosen:
  INCONCLUSIVE  the build fingerprint changed during the run, a planned case has no result, or a failure could not be
                pinned on the product (environment, broken check, unclear oracle). Suspected bugs are still listed.
  FAIL          at least one suspected product bug, on a build that held still, with every case accounted for.
  PASS          every planned case ran and every check passed.

Checks on the report (exit 1 when any fails):
  K1  the first line after the title is the verdict
  K2  no "Fix:" or "Suggested fix:" lines: QA reports what it found and leaves the repair to the people who own the code
  K3  every evidence path in the results table exists in the run folder
  K4  every case in the plan appears in the results table or under "Not run"
"""
from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_core as q  # noqa: E402
from qa_plan import meta, parse  # noqa: E402
from classify import CLASSES, classify  # noqa: E402

CLASS_TITLES = OrderedDict([
    ("suspected-bug", "Suspected product bugs"),
    ("environment", "Environment problems"),
    ("broken-check", "Broken checks"),
    ("unclear", "Unclear expected result"),
    ("intended-change", "Intended changes"),
])
FIX_LINE = re.compile(r"^\s*[-*]?\s*(\*\*)?(suggested fix|fix|to fix|solution|recommended fix)(\*\*)?\s*:", re.I)


def cell(v: str) -> str:
    return str(v).replace("|", "\\|").strip()


def build_state(run: Path) -> tuple[str, list[str]]:
    rows = q.read_rows(run / "build.tsv")
    if not rows:
        return "unknown", ["No build fingerprint was taken; the report cannot say which build was tested."]
    lines, changed, missing_end = [], False, False
    targets = OrderedDict()
    for r in rows:
        targets.setdefault(r["target"], {})[r["phase"]] = r["fingerprint"]
    for t, ph in targets.items():
        s, e = ph.get("start"), ph.get("end")
        if s and e and s != e:
            changed = True
            lines.append(f"`{t}` CHANGED during the run: start `{s}`, end `{e}`")
        elif s and e:
            lines.append(f"`{t}` held still: `{s}`")
        else:
            missing_end = True
            lines.append(f"`{t}`: only the {'start' if s else 'end'} fingerprint was taken (`{s or e}`)")
    return ("changed" if changed else "partial" if missing_end else "stable"), lines


def write(run: Path) -> tuple[str, str]:
    text = (run / "CASES.md").read_text(encoding="utf-8") if (run / "CASES.md").exists() else ""
    plan, m = parse(text), meta(text)
    results = q.read_rows(run / "results.tsv")
    cls = classify(run)
    cpath = run / "classification.tsv"
    if cpath.exists():
        cpath.unlink()
    for r in cls:
        q.append_row(cpath, ["case", "check", "class", "rule", "reason"], r)
    by_case = OrderedDict()
    for r in results:
        by_case.setdefault(r["case"], []).append(r)
    planned = [c.get("id", "") for c in plan["cases"]]
    covers = {c.get("id", ""): c.get("covers", "") for c in plan["cases"]}
    case_verdict = {}
    for cid, rows in by_case.items():
        vs = {r["verdict"] for r in rows}
        case_verdict[cid] = "fail" if "fail" in vs else "blocked" if "blocked" in vs else "pass"
    not_run = [c for c in planned if c not in by_case]
    blocked = [c for c, v in case_verdict.items() if v == "blocked"]
    counts = {c: sum(1 for r in cls if r["class"] == c) for c in CLASSES}
    build, build_lines = build_state(run)

    why = []
    if build == "changed":
        why.append("the build changed during the run")
    if not_run:
        why.append(f"{len(not_run)} planned case(s) have no result")
    if blocked:
        why.append(f"{len(blocked)} case(s) blocked")
    undecided = counts["environment"] + counts["broken-check"] + counts["unclear"]
    if undecided:
        why.append(f"{undecided} failed check(s) not attributable to the product")
    if why:
        verdict = "INCONCLUSIVE"
        reason = "; ".join(why)
        if counts["suspected-bug"]:
            reason += f"; {counts['suspected-bug']} suspected product bug(s) found anyway"
    elif counts["suspected-bug"]:
        verdict, reason = "FAIL", f"{counts['suspected-bug']} suspected product bug(s)"
    elif planned and all(case_verdict.get(c) == "pass" for c in planned):
        verdict, reason = "PASS", f"all {len(planned)} planned cases passed"
    else:
        verdict, reason = "INCONCLUSIVE", "no planned cases with results"

    req = plan["requirements"]
    ran = {c for c, v in case_verdict.items() if v in ("pass", "fail")}
    req_ran = {r for c in ran for r in re.split(r"[,\s]+", covers.get(c, "")) if r in req}
    calls = q.read_rows(run / "calls.tsv")
    data_rows = [r for r in calls if r.get("method") in q.WRITE_METHODS]

    L = [f"# QA report: {m['title'] or run.name}", "", f"Verdict: **{verdict}** ({reason})", ""]
    L += [f"Source: {m['source'] or 'not stated in CASES.md'}", f"Run folder: `{run.name}`, "
          f"{len(results)} checks over {len(by_case)} cases, {len(calls)} HTTP calls", ""]
    L += ["## Build tested", ""] + [f"- {x}" for x in build_lines] + [""]
    L += ["## Results", "", "| Case | Covers | Verdict | Check | Expected | Actual | Evidence |", "|---|---|---|---|---|---|---|"]
    for cid, rows in by_case.items():
        for r in rows:
            ev = r.get("evidence", "")
            evc = f"[{ev}]({ev})" if ev and not ev.startswith("call:") else ev
            L.append(f"| {cell(cid)} | {cell(covers.get(cid, ''))} | {r['verdict']} | {cell(r['check'])} | "
                     f"{cell(r['expected'])} | {cell(r['actual'])} | {cell(evc)} |")
    L.append("")
    if cls:
        L += ["## Failures by class", ""]
        for key, title in CLASS_TITLES.items():
            items = [r for r in cls if r["class"] == key]
            if not items:
                continue
            L += [f"### {title} ({len(items)})", ""]
            for r in items:
                L.append(f"- **{r['case']}**, {r['check']}: {r['reason']} (rule {r['rule']})")
            L.append("")
    L += ["## Not run", ""]
    if not_run or blocked:
        L += ["| Case | Why | Attempt |", "|---|---|---|"]
        for c in not_run:
            L.append(f"| {cell(c)} | no result recorded | none recorded |")
        for c in blocked:
            for r in by_case[c]:
                if r["verdict"] == "blocked":
                    L.append(f"| {cell(c)} | {cell(r.get('note') or 'blocked')} | {cell(r.get('evidence', ''))} |")
    else:
        L.append("Every planned case has a result.")
    L += ["", "## Requirement coverage", "",
          f"{len(req_ran)} of {len(req)} requirements were exercised by a case that ran to a pass or fail."]
    missing = [r for r in req if r not in req_ran]
    if missing:
        L += [""] + [f"- {r} not exercised: {cell(req[r])}" for r in missing]
    L += ["", "## Data written during the run", ""]
    if data_rows:
        L += [f"- {r['method']} {r['url']} → {r['status']} (case {r['case']}, {r['evidence']})" for r in data_rows]
        L += ["", "Records created by this run carry the prefix `QA-" + run.name + "`."]
    else:
        L.append("No write requests were sent.")
    L += ["", "## Exit criteria", ""] + [x.strip() for x in plan["exit"]] + [""]
    report = "\n".join(L)
    (run / "report.md").write_text(report, encoding="utf-8")
    return verdict, reason


def check(run: Path) -> list[str]:
    p = run / "report.md"
    if not p.exists():
        return ["K0 report.md not found"]
    text = p.read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    errs = []
    if len(lines) < 2 or not lines[1].startswith("Verdict:"):
        errs.append("K1 the verdict must be the first line after the title")
    for i, l in enumerate(text.splitlines(), 1):
        if FIX_LINE.match(l):
            errs.append(f"K2 line {i}: '{l.strip()[:60]}' — QA reports findings; repairs belong to the code owners")
    for ev in re.findall(r"\]\(((?:evidence/)[^)]+)\)", text):
        if not (run / ev).is_file():
            errs.append(f"K3 evidence link '{ev}' does not exist in the run folder")
    plan = parse((run / "CASES.md").read_text(encoding="utf-8")) if (run / "CASES.md").exists() else {"cases": []}
    for c in plan["cases"]:
        cid = c.get("id", "")
        if cid and not re.search(r"\|\s*" + re.escape(cid) + r"\s*\|", text):
            errs.append(f"K4 case {cid} is in the plan but in neither the results nor 'Not run'")
    return errs


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    run = q.run_dir(argv[0])
    if "--check" not in argv:
        verdict, reason = write(run)
        print(f"report: {run / 'report.md'}\nVerdict: {verdict} ({reason})")
    errs = check(run)
    for e in errs:
        print("CHECK  " + e)
    print(f"report check: {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
