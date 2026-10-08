---
name: report
description: Turn a finished QA run into a report developers and leads can trust. Classifies every failed check with fixed rules (suspected bug, environment, broken check, unclear expectation, intended change), has each suspected bug challenged by a skeptic reviewer, derives the verdict from the data, and checks that every claim links to evidence and that the report proposes no code fixes. Use after the run skill, or when the user asks for a QA report or verdict.
argument-hint: "<run folder>"
---

# Report a QA run

Run folder: the folder named in `<run folder root>/.active`, where the root is `${user_config.report_dir}`, or
`qa` when that option is not set. Use another run folder only if the user names one.

## 1. Classify the failures

```bash
python3 "${CLAUDE_SKILL_DIR}/classify.py" "<run folder>"
```

Each failed check gets one class, by the first rule that applies: a note from someone who knows (R1), missing
evidence or an empty observation means the check is broken (R2), no response or a 5xx means the environment failed
(R3), a pending oracle means the expectation is unclear (R4), and only then a suspected product bug (R5).

If the product owner or the ticket says a behaviour changed on purpose, add a line to `notes.tsv` in the run folder
(columns `case`, `class`, `reason`; class `intended-change`; reason quoting who said so) and classify again.

## 2. Challenge every suspected bug

For each `suspected-bug`, hand the case, its expected result and oracle, the actual result, and the evidence file to
the `skeptic` agent of this plugin. It looks for another explanation: wrong test data, stale cache, wrong role, a
measurement that could not have seen the value, an oracle that is out of date. Apply its outcome:

- **holds**: keep it as a suspected bug.
- **measurement doubt**: rerun the check with the fix the skeptic named, then classify again. If the rerun cannot be
  done now (no access to the test server, no time), record the doubt in `notes.tsv` with class `unclear` and the
  skeptic's reason, and go on to step 3.
- **needs an answer**: change the oracle in CASES.md to `pending: <question>` and classify again.

Whatever the skeptic says, the run ends with a written report. An open doubt makes the verdict INCONCLUSIVE and is
listed in the report with the rerun that would settle it; it never means stopping without a report.

## 3. Write and check the report

```bash
python3 "${CLAUDE_SKILL_DIR}/report.py" "<run folder>"
```

The verdict is derived, not chosen: INCONCLUSIVE when the build changed mid-run, a planned case has no result, or a
failure is not attributable to the product; FAIL when a suspected bug survived on a stable build; PASS only when
every planned case ran and passed. The script then checks the report: verdict first (K1), no fix proposals (K2),
every evidence link exists (K3), every planned case accounted for (K4).

If you edit report.md by hand, run `python3 "${CLAUDE_SKILL_DIR}/report.py" "<run folder>" --check` again.

## 4. Close the run and hand over

```bash
python3 "${CLAUDE_SKILL_DIR}/../plan/new_run.py" --root '${user_config.report_dir}' --close
```

Tell the user the verdict and the reason in one sentence, then list the suspected bugs with their evidence files and
the cases that did not run. Do not offer to fix the product code in the same breath: QA found these; whoever owns the
code decides the fix. If the user asks you to fix one afterwards, that is a separate task, and the `red-first` skill
of this plugin checks that the new test fails before the fix and passes after it.
