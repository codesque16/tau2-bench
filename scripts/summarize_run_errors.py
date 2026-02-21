#!/usr/bin/env python3
"""
Summarize failure reasons per task for a trajectory viewer run.
Outputs a table: task_id | reward | db_error | communicate_fail | not_called | arguments_mismatch | other

Usage:
  python scripts/summarize_run_errors.py 2026-02-21T00_37_20.185158_retail_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1-mini
"""
import json
import re
import sys
from pathlib import Path


def sanitize(s: str) -> str:
    return re.sub(r"[^\w\-.]", "_", s)


def main():
    base = Path(__file__).resolve().parent.parent
    if len(sys.argv) < 2:
        print("Usage: summarize_run_errors.py <run_id>")
        print("Example: summarize_run_errors.py 2026-02-21T00_37_20.185158_retail_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1-mini")
        sys.exit(1)
    run_id = sys.argv[1]
    run_dir = base / "docs" / "data" / run_id
    if not run_dir.is_dir():
        print(f"Run directory not found: {run_dir}")
        sys.exit(1)

    index_path = run_dir / "index.json"
    with open(index_path) as f:
        index = json.load(f)
    task_ids = [t["task_id"] for t in index["tasks"]]

    rows = []
    for task_id in sorted(task_ids, key=lambda x: (int(x) if x.isdigit() else 0)):
        safe_id = sanitize(task_id)
        task_path = run_dir / f"task_{safe_id}.json"
        if not task_path.exists():
            rows.append((task_id, "?", 0, 0, 0, 0, 0))
            continue
        with open(task_path) as f:
            data = json.load(f)
        ri = data.get("reward_info") or {}
        reward = ri.get("reward", 0)
        db_match = True
        if ri.get("db_check") is not None:
            db_match = ri["db_check"].get("db_match", True)
        db_error = 0 if db_match else 1
        breakdown = ri.get("reward_breakdown") or {}
        communicate_fail = 0 if breakdown.get("COMMUNICATE", 1) == 1 else 1

        not_called = 0
        arguments_mismatch = 0
        other = 0
        for c in ri.get("action_checks") or []:
            if not c.get("action_match"):
                reason = c.get("mismatch_reason") or "other"
                if reason == "not_called":
                    not_called += 1
                elif reason == "arguments_mismatch":
                    arguments_mismatch += 1
                else:
                    other += 1

        rows.append((task_id, reward, db_error, communicate_fail, not_called, arguments_mismatch, other))

    # Print markdown table
    headers = ("task_id", "reward", "db_error", "communicate_fail", "not_called", "arguments_mismatch", "other")
    col_widths = [max(len(str(h)), 4) for h in headers]
    for r in rows:
        for i, v in enumerate(r):
            col_widths[i] = max(col_widths[i], len(str(v)))

    def fmt_row(cells, widths):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"

    print(f"\n## Run: {run_id}\n")
    print(fmt_row(headers, col_widths))
    print("|" + "|".join("-" * (w + 2) for w in col_widths) + "|")
    for r in rows:
        print(fmt_row(r, col_widths))

    # Summary counts
    total = len(rows)
    failed = sum(1 for r in rows if r[1] != 1.0)
    with_db = sum(r[2] for r in rows)
    with_comm = sum(r[3] for r in rows)
    total_not_called = sum(r[4] for r in rows)
    total_args = sum(r[5] for r in rows)
    total_other = sum(r[6] for r in rows)
    print()
    print("Summary:")
    print(f"  Tasks: {total} total, {failed} failed (reward < 1)")
    print(f"  Tasks with DB error: {with_db}")
    print(f"  Tasks with communicate fail: {with_comm}")
    print(f"  Action check failures: not_called={total_not_called}, arguments_mismatch={total_args}, other={total_other}")


if __name__ == "__main__":
    main()
