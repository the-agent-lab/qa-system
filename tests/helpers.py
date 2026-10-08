"""Test helpers: paths to the plugin's scripts and a throwaway run folder."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))


def script(rel: str) -> str:
    return str(ROOT / rel)


def py(rel: str, *args: str, cwd: str | None = None, env: dict | None = None, stdin: str | None = None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, script(rel), *args], capture_output=True, text=True, cwd=cwd, env=e,
                          input=stdin)


GOOD_PLAN = """# QA plan: discount code

Source: ticket SHOP-12
Build under test: http://127.0.0.1/version

## Requirements

- R1: a valid code takes 10% off the cart total (source: SHOP-12 acceptance 1)
- R2: an expired code is rejected with a message (source: SHOP-12 acceptance 2)

## Cases

| ID | Covers | Type | Steps | Expected | Oracle |
|---|---|---|---|---|---|
| C1 | R1 | api | apply SAVE10 to a 200.00 cart | total 180.00 | SHOP-12 acceptance 1 |
| C2 | R2 | api | apply OLD5 (expired) | HTTP 422 | SHOP-12 acceptance 2 |

## Risks

- wrong totals reach the payment provider

## Exit criteria

- E1: every case has a result
"""


class RunFolder:
    def __init__(self, plan: str = GOOD_PLAN):
        self.root = Path(tempfile.mkdtemp(prefix="nghiem-test-"))
        self.run = self.root / "qa" / "2026-01-01-test"
        (self.run / "evidence").mkdir(parents=True)
        (self.run / "CASES.md").write_text(plan, encoding="utf-8")

    def evidence(self, name: str, text: str = "x") -> str:
        p = self.run / "evidence" / name
        p.write_text(text, encoding="utf-8")
        return f"evidence/{name}"

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)
