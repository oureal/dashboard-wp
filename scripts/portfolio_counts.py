#!/usr/bin/env python3
"""Derived transaction-ledger counts. Never hard-code totals that change when a transaction is added."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
TX1=ROOT/"data/transactions-depot1.json"; TX2=ROOT/"data/transactions.json"
def source_transactions():
    return (json.loads(TX1.read_text(encoding="utf-8")).get("transactions",[]),
            json.loads(TX2.read_text(encoding="utf-8")).get("transactions",[]))
def source_counts():
    d1,d2=source_transactions()
    return len(d1),len(d2),len(d1)+len(d2)
