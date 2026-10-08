#!/usr/bin/env python3
"""Open a QA run: create `<root>/<date>-<slug>/` with a CASES.md from the template, and mark it active.

    python3 new_run.py --root qa --name checkout-discount
    python3 new_run.py --root qa --close            clear the active marker (the report skill does this at the end)

The active marker `<root>/.active` holds the run folder name. While it exists, the plugin's write guard hook
checks HTTP write commands against the configured test hosts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
from qa_core import configured  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="qa")
    ap.add_argument("--name")
    ap.add_argument("--close", action="store_true")
    a = ap.parse_args(argv)
    root = Path(configured(a.root, "qa"))
    marker = root / ".active"
    if a.close:
        if marker.exists():
            print(f"new_run: closed {marker.read_text().strip()}")
            marker.unlink()
        else:
            print("new_run: no active run")
        return 0
    if not a.name:
        ap.error("--name is required")
    slug = re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-")[:48] or "run"
    run = root / f"{dt.date.today().isoformat()}-{slug}"
    i = 2
    while run.exists():
        run = root / f"{dt.date.today().isoformat()}-{slug}-{i}"
        i += 1
    (run / "evidence").mkdir(parents=True)
    shutil.copyfile(HERE / "CASES.template.md", run / "CASES.md")
    marker.write_text(run.name + "\n", encoding="utf-8")
    print(f"new_run: {run}  (active)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
