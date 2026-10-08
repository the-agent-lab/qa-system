"""Read a CASES.md plan into requirements, cases, and exit criteria. Shared by the plan and report skills."""
from __future__ import annotations

import re


def parse(text: str) -> dict:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    reqs = {}
    for line in sections.get("requirements", []):
        m = re.match(r"^\s*[-*]\s*(R[\w.-]*)\s*[:.)-]\s*(.+)$", line)
        if m:
            reqs[m.group(1)] = m.group(2).strip()
    cases, header = [], None
    for line in sections.get("cases", []):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        cases.append(dict(zip(header, cells + [""] * (len(header) - len(cells)))))
    exits = [l for l in sections.get("exit criteria", []) if re.match(r"^\s*[-*]\s+\S", l)]
    return {"requirements": reqs, "cases": cases, "header": header or [], "exit": exits}


def meta(text: str) -> dict:
    """Title, source and build lines from the top of CASES.md."""
    out = {"title": "", "source": "", "build": ""}
    for line in text.splitlines():
        m = re.match(r"^#\s+(?:QA plan:\s*)?(.+?)\s*$", line)
        if m and not out["title"]:
            out["title"] = m.group(1)
        m = re.match(r"^Source:\s*(.+)$", line)
        if m:
            out["source"] = m.group(1).strip()
        m = re.match(r"^Build under test:\s*(.+)$", line)
        if m:
            out["build"] = m.group(1).strip()
    return out


def pending_oracle(oracle: str) -> bool:
    return bool(re.match(r"^\s*(pending|ask)\b", oracle or "", re.I))
