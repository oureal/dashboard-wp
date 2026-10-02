#!/usr/bin/env python3
"""Persist security value snapshots and embed top movers for day/week/month/total."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
PORTFOLIO = ROOT / "data/generated/dry-run-portfolio.json"
PRICES = ROOT / "data/prices/latest.json"
HISTORY = ROOT / "data/history/security-history.json"
TX_FILES = [ROOT / "data/transactions-depot1.json", ROOT / "data/transactions.json"]
LEGACY_DIR = ROOT / "dashboard/history"

NAME_TO_ID = {
    "Berkshire Hathaway": "berkshire-hathaway-b",
    "Xetra Gold": "xetra-gold",
    "Allianz": "allianz",
    "Microsoft": "microsoft",
    "Eli Lilly": "eli-lilly",
    "Siemens": "siemens",
    "HSBC": "hsbc",
    "Apple": "apple",
    "Linde": "linde",
    "boerse.de-Aktienfonds": "boerse-de-aktienfonds",
    "Global Titans 50": "ishares-global-titans-50",
    "boerse.de-Technologiefonds": "boerse-de-technologiefonds",
    "Nvidia": "nvidia",
    "AMD": "amd",
    "MSCI World": "ishares-core-msci-world",
    "Alphabet": "alphabet-c",
    "Micron Technology": "micron-technology",
    "World Value": "ishares-msci-world-value-factor",
    "WisdomTree Physical Bitcoin": "wisdomtree-physical-bitcoin",
    "Marvell Technology": "marvell-technology",
    "TSMC": "tsmc-adr",
    "Broadcom": "broadcom",
    "Siemens Energy": "siemens-energy",
    "boerse.de-Aktienfonds - V EUR ACC": "boerse-de-aktienfonds",
}
ID_TO_NAME = {v: k for k, v in NAME_TO_ID.items()}

MOVERS_UI = r'''/* movers-dashboard-v1 */
(function(){
  const m=DATA.movers, grid=document.getElementById('moversGrid');
  if(!m||!grid){return;}
  const badge=document.getElementById('moversAsOf');
  if(badge)badge.textContent=`Stand ${m.asof}${m.time?', '+m.time+' Uhr':''}`;
  const defs=[['day','Aktueller Tag'],['week','Aktuelle Woche'],['month','Aktueller Monat'],['total','Gesamtzeitraum']];
  const signedPct=v=>(v>=0?'+':'')+pct.format(v);
  const signedEur=v=>(v>=0?'+':'')+eur.format(v);
  const side=(rows,kind,hasBaseline)=>{
    const title=kind==='plus'?'Top 3 PLUS':'Top 3 MINUS';
    if(!hasBaseline)return `<div class="mover-side ${kind}"><h4>${title}</h4><div class="mover-empty">Noch kein geeigneter Vergleichsstichtag.</div></div>`;
    if(!rows||!rows.length){const msg=kind==='plus'?'Keine positiven Veränderungen.':'Keine negativen Veränderungen.';return `<div class="mover-side ${kind}"><h4>${title}</h4><div class="mover-empty">${msg}</div></div>`;}
    const max=Math.max(...rows.map(r=>Math.abs(r.pct)),.000001);
    return `<div class="mover-side ${kind}"><h4>${title}</h4>${rows.map(r=>`<div class="mover-row"><div class="mover-name" title="${r.name}">${r.name}</div><div class="mover-pct">${signedPct(r.pct)}</div><div class="mover-eur">${signedEur(r.value)}</div><div class="mover-barbox"><div class="mover-bar" style="width:${Math.max(3,100*Math.abs(r.pct)/max)}%"></div></div></div>`).join('')}</div>`;
  };
  grid.innerHTML=defs.map(([key,title])=>{const p=m.periods[key]||{};const hasBaseline=!!p.from;const range=hasBaseline?`${p.from} → ${p.to}`:'Vergleich noch nicht verfügbar';return `<div class="card mover-card"><div class="mover-period"><h3>${title}</h3><div class="mover-range">${range}</div></div><div class="mover-columns">${side(p.gainers,'plus',hasBaseline)}${side(p.losers,'minus',hasBaseline)}</div></div>`}).join('');
})();'''


def load_inline(path: Path) -> tuple[str, re.Match[str], dict]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"const DATA=(\{.*?\});", text, flags=re.S)
    if not match:
        raise SystemExit(f"DATA object missing in {path}")
    return text, match, json.loads(match.group(1))


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%d.%m.%Y")


def load_existing() -> list[dict]:
    if HISTORY.exists():
        doc = json.loads(HISTORY.read_text(encoding="utf-8"))
        return list(doc.get("snapshots", []))
    return []


def legacy_snapshots() -> list[dict]:
    out = []
    if not LEGACY_DIR.exists():
        return out
    for path in sorted(LEGACY_DIR.glob("*.html")):
        try:
            _, _, data = load_inline(path)
        except (Exception, SystemExit):
            continue
        date = str(data.get("meta", {}).get("asof", "")).strip()
        if not date:
            continue
        values = {}
        for row in data.get("assets", []):
            iid = NAME_TO_ID.get(row.get("name"))
            if iid:
                values[iid] = float(row.get("value", 0) or 0)
        if values:
            out.append({"date": date, "time": None, "values": values, "source": "legacy-dashboard"})
    return out


def current_time(prices: dict) -> tuple[str, str]:
    stamps = [x.get("fetched_at") for x in prices.get("prices", []) if x.get("fetched_at")]
    if stamps:
        newest = max(datetime.fromisoformat(s.replace("Z", "+00:00")) for s in stamps)
        local = newest.astimezone(ZoneInfo("Europe/Vienna"))
    else:
        local = datetime.now(ZoneInfo("Europe/Vienna"))
    return local.strftime("%d.%m.%Y"), local.strftime("%H:%M")


def current_values(portfolio: dict) -> tuple[dict[str, float], dict[str, float]]:
    values: dict[str, float] = {}
    quantities: dict[str, float] = {}
    for row in portfolio.get("positions", []):
        iid = str(row.get("instrument_id") or "").strip()
        if iid and iid != "cash":
            value = float(row.get("market_value_eur", 0) or 0)
            quantity = float(row.get("quantity", 0) or 0)
            if value > 0:
                values[iid] = values.get(iid, 0.0) + value
            if quantity > 0:
                quantities[iid] = quantities.get(iid, 0.0) + quantity
    return values, quantities


def normalize(points: list[dict]) -> list[dict]:
    by_date = {}
    for p in points:
        date = p.get("date")
        if not date:
            continue
        try:
            parse_date(date)
        except ValueError:
            continue
        old = by_date.get(date)
        if old is None or p.get("source") == "current":
            by_date[date] = p
    return [by_date[d] for d in sorted(by_date, key=parse_date)]


def has_overlap(snapshot: dict, current: dict) -> bool:
    base = snapshot.get("values", {})
    return any(float(base.get(iid, 0) or 0) > 0 and float(now or 0) > 0 for iid, now in current.get("values", {}).items())


def baseline_for(period: str, snaps: list[dict], current: dict) -> dict | None:
    cur_dt = parse_date(current["date"])
    previous = [s for s in snaps if parse_date(s["date"]) < cur_dt and has_overlap(s, current)]
    if not previous:
        return None
    if period == "day":
        return previous[-1]
    if period == "week":
        same = [s for s in previous if parse_date(s["date"]).isocalendar()[:2] == cur_dt.isocalendar()[:2]]
        return same[0] if same else previous[-1]
    if period == "month":
        same = [s for s in previous if (parse_date(s["date"]).year, parse_date(s["date"]).month) == (cur_dt.year, cur_dt.month)]
        return same[0] if same else previous[-1]
    return previous[0]


def security_transactions() -> list[dict]:
    rows = []
    for path in TX_FILES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for tx in doc.get("transactions", []):
            iid = NAME_TO_ID.get(str(tx.get("name", "")).strip())
            qty = float(tx.get("quantity", 0) or 0)
            if iid and qty > 0 and tx.get("type") in ("Kauf", "Verkauf"):
                rows.append({"date": tx["date"], "id": iid, "type": tx["type"], "quantity": qty})
    # Confirmed 9 Sep transactions are still display-only legacy entries in
    # update_transactions_data.py. Include the Aktienfonds sale here so a
    # long-period price comparison reconstructs the correct historical units.
    manual = {"date": "2026-09-09", "id": "boerse-de-aktienfonds", "type": "Verkauf", "quantity": 100.0}
    if not any(r == manual for r in rows):
        rows.append(manual)
    return rows


def quantity_at(base_date: str, iid: str, current_qty: float, txs: list[dict]) -> float:
    """Reverse later trades from today's quantity to recover comparable baseline units."""
    q = current_qty
    base_dt = datetime.strptime(base_date, "%d.%m.%Y").date()
    for tx in txs:
        tx_dt = datetime.strptime(tx["date"], "%Y-%m-%d").date()
        if tx["id"] != iid or tx_dt <= base_dt:
            continue
        q += tx["quantity"] if tx["type"] == "Verkauf" else -tx["quantity"]
    return q


def ranking(base: dict | None, current: dict, txs: list[dict]) -> dict:
    if not base:
        return {"from": None, "to": current["date"], "coverage": 0, "gainers": [], "losers": []}
    rows = []
    for iid, now in current["values"].items():
        before = float(base.get("values", {}).get(iid, 0) or 0)
        now = float(now or 0)
        current_qty = float(current.get("quantities", {}).get(iid, 0) or 0)
        base_qty = quantity_at(base["date"], iid, current_qty, txs)
        if before <= 0 or now <= 0 or current_qty <= 0 or base_qty <= 0:
            continue
        base_price = before / base_qty
        current_price = now / current_qty
        change = current_price / base_price - 1
        # Euro figure is the price-driven effect on the baseline holding, not cash flow from trades.
        delta = before * change
        rows.append({"id": iid, "name": ID_TO_NAME.get(iid, iid), "pct": change, "value": delta, "current": now, "base": before})
    gainers = sorted((r for r in rows if r["pct"] > 0), key=lambda r: (r["pct"], r["value"]), reverse=True)[:3]
    losers = sorted((r for r in rows if r["pct"] < 0), key=lambda r: (r["pct"], r["value"]))[:3]
    return {"from": base["date"], "to": current["date"], "coverage": len(rows), "gainers": gainers, "losers": losers}


def patch_movers_ui(text: str) -> str:
    # The marker also exists in the movers CSS. Patch the JavaScript block,
    # which is the final marker occurrence in the generated dashboard.
    start = text.rfind("/* movers-dashboard-v1 */")
    if start < 0:
        raise SystemExit("Movers UI block missing")
    end_marker = "})();"
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit("Movers UI block end missing")
    end += len(end_marker)
    return text[:start] + MOVERS_UI + text[end:]


def main() -> int:
    portfolio = json.loads(PORTFOLIO.read_text(encoding="utf-8"))
    prices = json.loads(PRICES.read_text(encoding="utf-8"))
    date, time = current_time(prices)
    values, quantities = current_values(portfolio)
    current = {"date": date, "time": time, "values": values, "quantities": quantities, "source": "current"}
    if not current["values"]:
        raise SystemExit("Current security values are empty")

    snaps = normalize(legacy_snapshots() + load_existing() + [current])
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps({"schema_version": 2, "snapshots": snaps}, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")

    txs = security_transactions()
    periods = {key: ranking(baseline_for(key, snaps, current), current, txs) for key in ("day", "week", "month", "total")}
    empty = [key for key, value in periods.items() if not value.get("from") or int(value.get("coverage", 0)) <= 0]
    if empty:
        raise SystemExit(f"Movers have no comparable securities for: {', '.join(empty)}")

    text, match, data = load_inline(INDEX)
    data["movers"] = {"asof": date, "time": time, "periods": periods}
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = text[:match.start(1)] + encoded + text[match.end(1):]
    text = patch_movers_ui(text)
    INDEX.write_text(text, encoding="utf-8")
    coverage = ", ".join(f"{key}={periods[key]['coverage']}" for key in ("day", "week", "month", "total"))
    print(f"Stored {len(snaps)} security snapshots and embedded movers for {date} {time}; coverage {coverage}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


