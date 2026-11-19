#!/usr/bin/env python3
"""Daily all-or-nothing fundamental research; requires OPENAI_API_KEY.
No partial HTML writes. Every instrument must have fresh sourced research.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
START = "<!-- investment-ranking-v2:start -->"
MODEL = os.environ.get("RESEARCH_MODEL", "gpt-4.1")
API_KEY = os.environ.get("OPENAI_API_KEY")
REQUIRED = ("businessDrivers", "monitoring", "portfolioOverlap", "bear", "base",
            "bull", "filing", "filingSource", "fundamentalConclusion",
            "valuationModel", "analystDisagreement", "analystContext")

def request_research(name, sector, country, today):
    prompt = (
        "Conduct rigorous, current fundamental investment research as of " + today +
        " for " + name + " (" + sector + ", " + country + "). Horizon 2033-12-31. "
        "Use web search for the most recent issuer filings and credible public analyst research. "
        "Do not invent analyst identities, targets, figures, sources, or opinions. "
        "Explain revenue, profit, cash flow, debt, valuation (with dated share price and valuation multiples), "
        "competitive advantage, risks, portfolio overlap, and bear/base/bull 2033 assumptions. "
        "Provide named analysts and their disagreements only when directly sourced; otherwise "
        "explicitly state that individual research is unavailable. "
        "Return ONLY a JSON object with nonempty string keys: " + ", ".join(REQUIRED) +
        ". filingSource must be an HTTPS URL for the actual primary issuer filing, "
        "and analystContext must contain citations/URLs. valuationModel must include numeric "
        "assumptions and explain limitations. Use concrete dated data, not generic boilerplate. "
        "For ETFs, use issuer factsheet and underlying holdings instead of corporate filings."
    )
    payload = json.dumps({
        "model": MODEL,
        "tools": [{"type": "web_search_preview"}],
        "input": prompt,
        "max_output_tokens": 4200,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses", data=payload,
        headers={"Authorization": "Bearer " + API_KEY,
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    parts = []
    for item in result.get("output", []):
        if item.get("type") == "message":
            for segment in item.get("content", []):
                if segment.get("type") == "output_text":
                    parts.append(segment.get("text", ""))
    raw = "\n".join(parts).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", raw)
    return json.loads(raw)

def main():
    if not API_KEY:
        sys.exit("Full research unavailable: configure OPENAI_API_KEY in repository Actions secrets.")
    html = HTML.read_text(encoding="utf-8")
    anchor = html.index(START)
    match = re.search(r"const entries=(\[.*?\]);", html[anchor:], re.S)
    if not match:
        sys.exit("Cannot find ranking entries")
    entries = json.loads(match.group(1))
    if len(entries) != 36:
        sys.exit(f"Expected 36 instruments, found {len(entries)}")
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    failures = []
    for entry in entries:
        name = entry["name"]
        try:
            data = request_research(name, entry.get("sector", ""), entry.get("country", ""), today)
            missing = [k for k in REQUIRED if not isinstance(data.get(k), str) or len(data[k].strip()) < 40]
            if missing:
                raise ValueError("Insufficient research fields: " + ", ".join(missing))
            if not data["filingSource"].startswith("https://"):
                raise ValueError("Missing HTTPS issuer primary source")
            # Check that cited primary source resolves. Do not confuse reachability with truth verification.
            req = urllib.request.Request(data["filingSource"], headers={"User-Agent": "PortfolioResearch/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status >= 400:
                    raise ValueError("Primary source unreachable")
            entry.setdefault("deepAnalysis", {}).update(data)
            entry["deepAnalysis"]["researchAsOf"] = today
            entry["deepAnalysis"]["primarySourceVerified"] = True
            entry["deepAnalysis"]["quality"] = "Automatisch recherchiert; Primärquellen-URL erreichbar; inhaltliche Zahlenprüfung durch Menschen nicht bestätigt."
            print("Research completed:", name, flush=True)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print("Research failed:", failures[-1], file=sys.stderr, flush=True)
        time.sleep(1)
    if failures:
        sys.exit("FULL RESEARCH FAILED; NO FILE MODIFIED:\n" + "\n".join(failures))
    replacement = "const entries=" + json.dumps(entries, ensure_ascii=False, separators=(",", ":")) + ";"
    new_html = html[:anchor + match.start()] + replacement + html[anchor + match.end():]
    HTML.write_text(new_html, encoding="utf-8")
    print("All 36 instruments researched; HTML updated atomically.")

if __name__ == "__main__":
    main()
