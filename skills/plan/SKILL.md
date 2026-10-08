---
name: plan
description: Write a QA test plan for a ticket, feature, or spec before testing it. Fixes the expected result of every case, and where that expectation comes from, before the implementation is read, then checks that every requirement has a case. Use when the user asks to QA, test, or verify a ticket, pull request, feature, or release, or asks for test cases.
argument-hint: "<ticket link, spec file, or feature name>"
---

# Plan a QA run

The point of a plan is that it can fail. An expected result copied from the code under test will always agree with
that code, so this skill fixes expectations from an independent source first and reads the implementation later.

## 1. Get the source of truth

Find what the feature is supposed to do: the ticket, a spec file, acceptance criteria, a design, or the user's own
words. Quote it; do not paraphrase it into something more testable than it is. If there is no source at all, ask the
user for one before going further. A plan without a source can only restate the code.

## 2. Open a run

```bash
python3 "${CLAUDE_SKILL_DIR}/new_run.py" --root "${user_config.report_dir}" --name "<short name of the feature>"
```

This creates `<report_dir>/<date>-<name>/` with `CASES.md` from the template and marks the run active. While a run is
active, the plugin's write guard blocks HTTP write requests to hosts that are not in the configured test hosts.

## 3. Write requirements, then cases, before reading the implementation

Fill `CASES.md`:

- **Requirements**: one line each, `- R1: ...`, in the source's words, with where it says so.
- **Cases**: one row per check. `Expected` is something you can observe (a status code, a row count in the database,
  text on the screen, a file). `Oracle` says where the expected result comes from: a spec section, a data rule, a
  reference screen, the product owner. If the source does not say, write `pending: <question, and who can answer>`;
  that case stays blocked until it is answered, which is better than inventing an answer.
- Prefer checks that measure the outcome independently of the thing being tested: count the rows in the database
  instead of trusting the API's own success message; reload the page instead of trusting the toast.
- Cover the negative side: wrong role, missing field, duplicate submit, the value at each boundary.
- **Test data**: every record the run creates gets the prefix `QA-<run folder name>` so it can be found and removed.
- **Risks** and **Exit criteria**: the report derives its verdict from the exit criteria, so make them checkable.

Do not open the implementation to decide what the expected result should be. If you have already read it, take the
expected result from the source anyway.

## 4. Check the plan

```bash
python3 "${CLAUDE_SKILL_DIR}/check_plan.py" "<run folder>"
```

Fix every error and run it again until it exits 0. The rules: every requirement has a case (P1), every case covers a
listed requirement (P2), no empty or placeholder fields (P3), no oracle that is the code itself (P4), unique IDs (P5),
at least one case (P6), known types (P7), exit criteria present (P8), open oracle questions flagged (P9).

## 5. Now read the implementation, to plan how to run each case

Read the code, routes, and selectors to work out how to execute each case: which endpoint, which button, which query.
Never edit an expected result because the code does something else. A disagreement between the code and the plan is
what QA exists to find; note it and let the run skill measure it.

Show the user the requirements and cases table, and say which oracles are still pending. Then continue with the
`run` skill of this plugin.
