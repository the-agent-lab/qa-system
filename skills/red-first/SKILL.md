---
name: red-first
description: Prove that a new or changed test actually catches the bug it was written for, by running it against the code before the fix (it must fail, and for the right reason) and after the fix (it must pass). Works with any test command. Use when a bug fix adds a regression test, when reviewing a pull request that claims a test covers a bug, or after QA reported a bug that someone has fixed.
argument-hint: "<base ref> <test command>"
---

# Red first, then green

A regression test that would also pass on the broken code proves nothing. This skill runs it on both.

```bash
python3 "${CLAUDE_SKILL_DIR}/red_first.py" --base "<ref before the fix>" --test "<command that runs the new test>"
```

- `--base` is the commit before the fix: usually the pull request's base branch (`origin/main`) or the parent of the
  fix commit (`<fix>^`).
- The test files are found automatically (test-looking files changed since `--base`, including uncommitted ones), or
  passed with `--tests <file> ...`.
- If the test needs installed dependencies, share them with `--link node_modules` (or `.venv`, `vendor`).

Read the result:

- **RED-THEN-GREEN** (exit 0): the test fails on the old code and passes with the fix. Quote both tails in your answer.
- **NOT-RED**: the test passes on the old code. It does not cover the bug; strengthen the assertion so it checks the
  behaviour that was broken.
- **WRONG-RED**: it failed on the old code only because it could not load (missing import, new symbol, compile
  error). Make it load on the old code so it fails on behaviour.
- **NOT-GREEN**: the fix does not make the test pass.

Even on RED-THEN-GREEN, read the "before the fix" tail yourself: the failure message should name the broken behaviour.
