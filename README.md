# Nghiem QA

A Claude Code plugin for QA that can fail.

Most AI test tooling generates tests and then "self-heals" them until they pass. A check that repairs itself until it
is green cannot report a bug. Nghiem works the other way round:

- **Expected results are fixed before the code is read.** Every case names where its expected result comes from
  (the ticket, the spec, a data rule, the product owner). An expectation copied from the implementation is rejected.
- **Every verdict points to evidence.** HTTP calls are logged with the exact command and status code, responses are
  kept as files, and a verdict without evidence is not recorded.
- **Failures are classified, not patched.** Each failed check is sorted by fixed rules into suspected bug,
  environment problem, broken check, unclear expectation, or intended change. Suspected bugs are challenged by a
  skeptic reviewer before the report goes out, and the report contains no code fixes.
- **Writes only go to test servers.** During a QA run, write requests to hosts outside your configured test hosts are
  refused.

## Install

```text
/plugin marketplace add the-agent-lab/qa-system
/plugin install nghiem@the-agent-lab
```

When the plugin is enabled, Claude Code asks for:

- `test_hosts` (required): comma-separated host names that may receive POST, PUT, PATCH and DELETE requests during
  QA, for example `staging.example.com,localhost:3000`. Matching is exact: `example.com` does not cover
  `api.example.com`.
- `report_dir` (default `qa`): the folder in your project where runs are written.

Requirements: Python 3.9 or later (standard library only), `git` for the red-first skill, and for UI cases a browser
tool in Claude Code, for example `playwright@claude-plugins-official`.

## Use

Ask Claude to QA something, for example "QA ticket SHOP-12" or "test the discount code feature against staging".
The plugin's skills run in this order:

| Skill | What it does |
|---|---|
| `nghiem:plan` | Writes `CASES.md`: requirements in the source's words, cases with expected results and their source, risks, exit criteria. `check_plan.py` rejects an uncovered requirement or an expected result taken from the code. |
| `nghiem:run` | Pins the deployed build, runs each case (API through `qa_http.py`, UI through your browser tool, database through a read-only command you provide), and records each verdict with its evidence. |
| `nghiem:report` | Classifies failures, sends suspected bugs to the `skeptic` agent, derives the verdict (PASS, FAIL, INCONCLUSIVE) and writes `report.md`, then checks that every evidence link exists and that no fix is proposed. |
| `nghiem:red-first` | Runs a new regression test on the code before the fix (it must fail, on behaviour rather than an import error) and after it (it must pass). |

A run folder looks like this:

```text
qa/2026-10-08-discount-code/
  CASES.md          plan
  calls.tsv         every HTTP call: method, URL, status, time, evidence file, masked curl command
  results.tsv       every check: expected, actual, verdict, evidence
  build.tsv         build fingerprint at the start and the end of the run
  classification.tsv
  evidence/         response bodies, screenshots, query output
  report.md
```

## What this plugin runs, sends, and stores

This section is complete; nothing else is executed or transmitted.

- **Network.** The plugin sends no telemetry and contacts no service of its own. `qa_http.py` sends only the HTTP
  requests that a QA case asks for, to the URLs in your plan. `pin_build.py` sends a GET request to the build URL you
  name in `CASES.md`. The skeptic agent may repeat GET requests through `qa_http.py` to re-check a finding.
- **Commands.** The scripts are plain Python in `skills/*/` and `hooks/`; `red_first.py` runs `git worktree` and the
  test command you give it; `pin_build.py --command` runs the command you give it.
- **Files.** Everything is written inside `report_dir` in your project. Password-, token- and secret-like values are
  masked in logs, printed output and saved responses. A login token you choose to keep with `--token-key` is written
  to `<run folder>/.token` with mode 600; add `report_dir` to `.gitignore` if runs should stay out of version control.
- **Hook.** A `PreToolUse` hook reads each Bash command while a run is open (`<report_dir>/.active` exists) and blocks
  `curl`, `wget` and `httpie` write requests to hosts outside `test_hosts`. It does not see writes sent from a script
  file, a programming-language one-liner, or a browser, so the run skill routes API calls through `qa_http.py`, which
  enforces the same rule itself. Outside a run, the hook exits immediately.
- **Settings.** The plugin does not change Claude Code permissions or settings.

## Develop

```bash
python3 -m unittest discover -s tests -t tests     # the plugin's own tests
python3 tools/prepublish_scan.py                   # credentials, phone numbers, ID numbers, deny-listed hosts
claude plugin validate . --strict
```

`prepublish_scan.py` exists because the predecessor of this project, the npm package `@ldtdev/qa-system` 1.x,
published an example config with real test-server accounts. A secret scanner that looks only for credentials with a
known format reported nothing; this one looks for plain passwords, phone numbers and 12-digit ID numbers, plus a
deny list of host names that you keep outside the repository.

The rules come from the QA practice of [The Agent Lab](https://github.com/the-agent-lab): ISTQB CTFL v4 for test
design, ISO/IEC/IEEE 29119-3 for plan and report structure.

## License

MIT
