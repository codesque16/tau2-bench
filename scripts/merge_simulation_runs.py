#!/usr/bin/env python3
"""
Merge two simulation runs: one with all 114 tasks (but errors on 96-113) and one
with only tasks 96-113 (good runs). Output: one run with 114 tasks, using good
data for 96-113 from the second file.

Usage:
  python3 merge_simulation_runs.py <full_run.json> <tasks_96_113_run.json> [--output path]
"""
import argparse
import json
from pathlib import Path


def task_id_num(task_id: str) -> int:
    """Parse task id to int for comparison."""
    try:
        return int(task_id)
    except (ValueError, TypeError):
        return -1


def merge_runs(full_path: Path, partial_path: Path, out_path: Path) -> None:
    with open(full_path) as f:
        full = json.load(f)
    with open(partial_path) as f:
        partial = json.load(f)

    # Tasks: 0-95 from full, 96-113 from partial
    full_tasks = {t["id"]: t for t in full["tasks"]}
    partial_tasks = {t["id"]: t for t in partial["tasks"]}

    merged_tasks = []
    for i in range(114):
        sid = str(i)
        if i < 96 and sid in full_tasks:
            merged_tasks.append(full_tasks[sid])
        elif i >= 96 and sid in partial_tasks:
            merged_tasks.append(partial_tasks[sid])
        elif sid in full_tasks:
            merged_tasks.append(full_tasks[sid])
        else:
            raise ValueError(f"Missing task id {sid} in both runs")

    # Simulations: from full where task_id in 0-95, from partial where task_id in 96-113
    merged_sims = []
    for sim in full["simulations"]:
        tid = task_id_num(sim.get("task_id", ""))
        if 0 <= tid < 96:
            merged_sims.append(sim)
    for sim in partial["simulations"]:
        tid = task_id_num(sim.get("task_id", ""))
        if 96 <= tid <= 113:
            merged_sims.append(sim)

    # Sort simulations by task_id for consistent ordering
    merged_sims.sort(key=lambda s: task_id_num(s.get("task_id", "")))

    merged = {
        "timestamp": full.get("timestamp"),
        "info": full.get("info"),
        "tasks": merged_tasks,
        "simulations": merged_sims,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Merged {len(merged_tasks)} tasks, {len(merged_sims)} simulations → {out_path}")


def main():
    base = Path(__file__).resolve().parent.parent
    sims_dir = base / "data" / "simulations"
    default_out = sims_dir / "merged_retail_114_tasks_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1-mini.json"

    parser = argparse.ArgumentParser(description="Merge full run (errors on 96-113) with partial run (96-113 only)")
    parser.add_argument("full_run", type=Path, help="JSON with all 114 tasks (errors on 96-113)")
    parser.add_argument("partial_run", type=Path, help="JSON with tasks 96-113 only (good runs)")
    parser.add_argument("--output", "-o", type=Path, default=default_out, help="Output JSON path")
    args = parser.parse_args()

    merge_runs(args.full_run.resolve(), args.partial_run.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
