#!/usr/bin/env python3
"""
Build tasks_solo.json from tasks_verified.json for retail solo mode.
- Adds a "ticket" field (one-shot problem description) from reason_for_call, known_info, unknown_info.
- Sets solo_convertible: false for tasks that require communicating specific info to the user
  (non-empty communicate_info), since those cannot be fully solved without a conversational response.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "tau2" / "domains" / "retail"
VERIFIED_PATH = DATA_DIR / "tasks_verified.json"
SOLO_PATH = DATA_DIR / "tasks_solo.json"


def build_ticket(task: dict) -> str:
    """Build a one-shot ticket from user_scenario.instructions."""
    instructions = task.get("user_scenario", {}).get("instructions", {})
    if isinstance(instructions, str):
        return instructions
    reason = instructions.get("reason_for_call", "")
    known = instructions.get("known_info", "")
    unknown = instructions.get("unknown_info", "")
    lines = [
        "Customer request:",
        reason,
        "",
        "Customer information:",
        known,
    ]
    if unknown:
        lines.append("")
        lines.append("Note: " + unknown)
    lines.append("")
    lines.append(
        "Fulfill the request using the available tools. "
        "Assume the customer has already agreed to any required confirmations."
    )
    return "\n".join(lines).strip()


def main() -> None:
    with open(VERIFIED_PATH) as f:
        tasks = json.load(f)

    solo_tasks = []
    excluded_ids = []

    for task in tasks:
        ec = task.get("evaluation_criteria") or {}
        communicate_info = ec.get("communicate_info") or []
        cannot_convert = len(communicate_info) > 0

        new_task = {k: v for k, v in task.items()}
        new_task["ticket"] = build_ticket(task)
        new_task["solo_convertible"] = not cannot_convert

        if cannot_convert:
            excluded_ids.append(task["id"])
            # Add note to description for clarity
            desc = new_task.get("description") or {}
            if not isinstance(desc, dict):
                desc = {}
            notes = desc.get("notes") or ""
            if notes:
                notes += " "
            notes += (
                "Excluded from solo: task requires communicating specific information "
                "to the user (communicate_info is non-empty), which is not one-shot solvable."
            )
            new_task["description"] = {**desc, "notes": notes.strip()}

        solo_tasks.append(new_task)

    with open(SOLO_PATH, "w") as f:
        json.dump(solo_tasks, f, indent=4)

    print(f"Wrote {len(solo_tasks)} tasks to {SOLO_PATH}")
    print(f"  Convertible (solo_convertible=true): {len(solo_tasks) - len(excluded_ids)}")
    print(f"  Excluded (solo_convertible=false): {len(excluded_ids)}")
    print(f"  Excluded task ids: {excluded_ids}")


if __name__ == "__main__":
    main()
