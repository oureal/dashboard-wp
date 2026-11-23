#!/usr/bin/env python3
"""Report research coverage honestly; never claim unsupported verification."""
import json
import re
from pathlib import Path

html = Path("index.html").read_text(encoding="utf-8")
section = html[html.index("<!-- investment-ranking-v2:start -->"):]
match = re.search(r"const entries=(\[.*?\]);", section, flags=re.S)
if not match:
    raise SystemExit("Missing ranking dataset")
entries = json.loads(match.group(1))
if len(entries) < 36:
    raise SystemExit(f"Expected at least 36 ranking instruments, found {len(entries)}")
report = {"total": len(entries), "primary_source_verified": 0, "with_analyst_consensus": 0, "missing_primary_sources": [], "missing_consensus": []}
for entry in entries:
    a = entry.get("deepAnalysis") or {}
    if a.get("primarySourceVerified") and a.get("filingSource"):
        report["primary_source_verified"] += 1
    else:
        report["missing_primary_sources"].append(entry["name"])
    if entry.get("analystCount") and entry.get("analystTarget"):
        report["with_analyst_consensus"] += 1
    else:
        report["missing_consensus"].append(entry["name"])
Path("data/generated").mkdir(parents=True, exist_ok=True)
Path("data/generated/research-coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
