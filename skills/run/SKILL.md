---
name: run
description: Execute the cases of a QA plan against a test server and record each verdict with its evidence. API calls are logged with the exact command and status code, writes to hosts outside the configured test hosts are refused, and the deployed build is fingerprinted at the start and end. Use after the plan skill has written and checked CASES.md, or when the user asks to run or rerun QA cases.
argument-hint: "<run folder>"
---

# Run QA cases

Every verdict this skill writes has to survive someone asking "how do you know?". So each check records what was
expected, what was observed, and a file or logged call that shows it.

Run folder: the folder named in `<run folder root>/.active`, where the root is `${user_config.report_dir}`, or
`qa` when that option is not set. Use another run folder only if the user names one.
Test hosts (the only hosts that may receive writes): `${user_config.test_hosts}`.

## 1. Pin the build

```bash
python3 "${CLAUDE_SKILL_DIR}/pin_build.py" --run "<run folder>" --phase start --url "<page or version endpoint>"
```

Use the `Build under test` line of CASES.md. For a backend with no version endpoint, fingerprint a command instead
(`--command "<command that prints the deployed version>"`). Repeat with `--phase end` after the last case.

## 2. Run each case

Work through the cases table in order. For each case:

**API**: call it through the logging wrapper, never a bare `curl`:

```bash
python3 "${CLAUDE_SKILL_DIR}/qa_http.py" --run "<run folder>" --case C1 --hosts '${user_config.test_hosts}' \
  --method POST --url "<url>" --header "Content-Type: application/json" --data '<body>' --expect-status 201
```

Keep the single quotes around the test hosts placeholder. If no test hosts are configured, the wrapper treats every
host as read-only. The wrapper refuses POST, PUT, PATCH and DELETE to any host outside the test hosts. If it refuses, do not work around
it: the target is not a test server, so stop and tell the user.

**Database**: use the read-only query command the user gave you. Save the output to `evidence/<case>-<what>.txt`,
then record it. Count rows rather than trusting an API's success message.

**UI**: use the browser tool that is available (the `playwright` plugin, Chrome DevTools, or Claude in Chrome). Save a
screenshot or the page text to `evidence/`, and reload the page before judging a saved state.

Then record the verdict:

```bash
python3 "${CLAUDE_SKILL_DIR}/record.py" --run "<run folder>" --case C2 --check "<what was checked>" \
  --expected "<from CASES.md>" --actual "<what you observed>" --evidence "<evidence file or call:N>"
```

## 3. Rules that keep the verdicts honest

- **Expected results come from CASES.md.** If the product does something else, that is a fail. Do not edit the plan
  to match the product, and do not change product code during a QA run.
- **A check that cannot see the thing cannot pass it.** For every "X is absent" check, also run a check that would
  show X if it were there (the same query without the filter, the same page as a role that should see it).
  An empty result from a broken query looks exactly like a correct absence.
- **Changed data must change the check.** If you assert a value, make sure a different value would have failed.
- **Blocked is not fail.** If the environment was down or you lacked access, record `--verdict blocked` with the
  attempted command's output as evidence and a note. Never record a pass for something you did not run.
- **Test data** you create carries the prefix `QA-<run folder name>`; list it in the report so it can be removed.

## 4. Finish

Pin the build again with `--phase end`, then continue with the `report` skill of this plugin.
