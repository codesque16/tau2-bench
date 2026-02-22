#!/usr/bin/env python3
"""Extract task_id, trial, and pass/fail (1/0) from a trajectory JSON into CSV."""
import json
import sys
from pathlib import Path


def main():
    json_path = Path(__file__).parent.parent / (
        "web/leaderboard/public/submissions/qwen3-max_qwen_2026-01-23/trajectories/"
        "retail_llm_agent_qwen3-max-2026-01-23_user_simulator_gpt-4.1-2025-04-14.json"
    )
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])

    out_path = json_path.with_suffix(".runs.csv")
    if len(sys.argv) > 2:
        out_path = Path(sys.argv[2])

    print(f"Loading {json_path}...", file=sys.stderr)
    with open(json_path) as f:
        data = json.load(f)

    rows = []
    for sim in data["simulations"]:
        task_id = sim["task_id"]
        trial = sim["trial"]
        reward = sim.get("reward_info", {}).get("reward", 0.0)
        passed = 1 if reward >= 1.0 else 0
        rows.append((task_id, trial, passed))

    print(f"Writing {len(rows)} rows to {out_path}...", file=sys.stderr)
    with open(out_path, "w") as f:
        f.write("task_id,trial,passed\n")
        for task_id, trial, passed in rows:
            f.write(f"{task_id},{trial},{passed}\n")

    print(f"Done. Output: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
