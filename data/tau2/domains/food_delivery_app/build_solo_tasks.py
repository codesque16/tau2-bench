#!/usr/bin/env python3
"""Build tasks_solo.json from tasks.json by adding ticket and solo_convertible."""
import json
from pathlib import Path

DIR = Path(__file__).parent
with open(DIR / "tasks.json") as f:
    tasks = json.load(f)

# Tasks that require communicating specific info to user or refusal behavior - harder for solo
SOLO_CONVERTIBLE_FALSE = {"2", "4", "6", "7", "9", "16", "19"}

for t in tasks:
    inst = t["user_scenario"]["instructions"]
    known = inst.get("known_info") or ""
    reason = inst.get("reason_for_call") or ""
    unknown = (inst.get("unknown_info") or "").strip().rstrip(".")
    note = f"Note: {unknown}." if unknown else ""
    ticket = (
        "Customer information:\n"
        + known.strip()
        + "\n\nCustomer request:\n"
        + reason.strip()
        + "\n\n"
        + (note + "\n\n" if note else "")
        + "Fulfill the request using the available tools. Assume the customer has already agreed to any required confirmations."
    )
    t["ticket"] = ticket
    t["solo_convertible"] = t["id"] not in SOLO_CONVERTIBLE_FALSE

with open(DIR / "tasks_solo.json", "w") as f:
    json.dump(tasks, f, indent=2)

print(f"Wrote {DIR / 'tasks_solo.json'} with {len(tasks)} tasks (ticket + solo_convertible).")
