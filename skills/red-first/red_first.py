#!/usr/bin/env python3
"""Prove a new test catches the bug: it must fail on the code before the fix and pass on the code after it.

    python3 red_first.py --base main --test "pytest tests/test_discount.py -q"
    python3 red_first.py --base origin/develop --test "npx vitest run src/cart" --link node_modules
    python3 red_first.py --base abc1234 --test "go test ./pricing/..." --tests pricing/discount_test.go

How: the test files (given with --tests, or every test-looking file changed since --base) are copied into a temporary
git worktree of --base, the test command runs there and must FAIL, then it runs in the current tree and must PASS.
The worktree is removed afterwards. --link shares heavy folders such as node_modules or .venv with the worktree.

Outcomes (exit code):
  0  RED-THEN-GREEN   the test detects the bug and the fix makes it pass
  1  NOT-RED          the test passes without the fix: it does not detect the bug
  1  NOT-GREEN        the test still fails with the fix
  1  WRONG-RED        it failed before the fix, but with an import, syntax or compile error: that proves nothing
  2  setup problem    not a git repo, unknown ref, no test files found
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_FILE = re.compile(r"(^|/)(tests?/|__tests__/)|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$")
WRONG_RED = re.compile(r"ModuleNotFoundError|ImportError|SyntaxError|IndentationError|Cannot find module|"
                       r"Failed to resolve import|error TS\d+|cannot find package|undefined: \w+|no tests ran|"
                       r"collected 0 items|No test files found", re.I)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def changed_tests(repo: Path, base: str) -> list[str]:
    names = set(git(repo, "diff", "--name-only", f"{base}...HEAD").stdout.split())
    names |= set(git(repo, "diff", "--name-only", "HEAD").stdout.split())
    names |= set(git(repo, "ls-files", "--others", "--exclude-standard").stdout.split())
    return sorted(n for n in names if TEST_FILE.search(n) and (repo / n).is_file())


def run(cmd: str, cwd: Path, timeout: float) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} s"


def tail(text: str, n: int = 15) -> str:
    return "\n".join(text.rstrip().splitlines()[-n:])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="git ref of the code before the fix")
    ap.add_argument("--test", required=True, help="command that runs the new test(s)")
    ap.add_argument("--tests", nargs="*", help="test files to carry over (default: test files changed since --base)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--link", action="append", default=[], help="folder to share with the worktree, e.g. node_modules")
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args(argv)
    repo = Path(git(Path(a.repo), "rev-parse", "--show-toplevel").stdout.strip() or ".")
    if not (repo / ".git").exists():
        print(f"red_first: {a.repo} is not inside a git repository")
        return 2
    if git(repo, "rev-parse", "--verify", f"{a.base}^{{commit}}").returncode:
        print(f"red_first: unknown ref {a.base}")
        return 2
    tests = a.tests or changed_tests(repo, a.base)
    if not tests:
        print("red_first: no test files found; pass them with --tests")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="red-first-"))
    wt = tmp / "base"
    try:
        add = git(repo, "worktree", "add", "--detach", str(wt), a.base)
        if add.returncode:
            print(f"red_first: could not create a worktree of {a.base}: {add.stderr.strip()}")
            return 2
        for t in tests:
            dst = wt / t
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / t, dst)
        for d in a.link:
            src, dst = repo / d, wt / d
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(src.resolve(), dst)
        print(f"red_first: {len(tests)} test file(s) carried to {a.base}: {', '.join(tests)}")
        rc_base, out_base = run(a.test, wt, a.timeout)
        rc_fix, out_fix = run(a.test, repo, a.timeout)
    finally:
        git(repo, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n--- before the fix ({a.base}): exit {rc_base}\n{tail(out_base)}")
    print(f"\n--- after the fix (working tree): exit {rc_fix}\n{tail(out_fix)}\n")
    if rc_base == 0:
        print("NOT-RED: the test passes without the fix, so it does not detect the bug.")
        return 1
    if WRONG_RED.search(out_base):
        print("WRONG-RED: it failed before the fix with an import, syntax or compile error, not an assertion. "
              "Make the test load on the old code (or stub the new symbol) so it fails on behaviour.")
        return 1
    if rc_fix != 0:
        print("NOT-GREEN: the test still fails with the fix.")
        return 1
    print("RED-THEN-GREEN: the test fails on the old code and passes with the fix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
