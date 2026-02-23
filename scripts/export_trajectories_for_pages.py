#!/usr/bin/env python3
"""
Export per-task trajectory data for the GitHub Pages trajectory viewer.
Supports one or more simulation JSON files. Each run is exported to
docs/data/<run_id>/ (index.json + task_<id>.json). A manifest docs/data/runs.json
lists all runs so the viewer can offer a run selector.

Usage:
  python3 export_trajectories_for_pages.py
      # Exports all *.json in data/simulations/
  python3 export_trajectories_for_pages.py path/to/run1.json path/to/run2.json
      # Exports only the given files
"""
import argparse
import json
import re
from pathlib import Path


def sanitize_filename(s: str) -> str:
    """Safe filename (no path separators or problematic chars)."""
    return re.sub(r"[^\w\-.]", "_", s)


def run_id_from_path(path: Path) -> str:
    """Derive a short run id from simulation filename (no .json)."""
    return sanitize_filename(path.stem)


def label_from_path(path: Path) -> str:
    """Human-readable label from filename (e.g. timestamp + agent names)."""
    stem = path.stem
    # e.g. 2026-02-21T00:37:20.185158_retail_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1-mini
    if "_retail_" in stem or "_" in stem:
        parts = stem.replace("_", " ").split()
        # Take first 6–8 tokens as label (date/time + domain + agent hint)
        return " ".join(parts[:8]) if len(parts) >= 8 else stem.replace("_", " ")
    return stem.replace("_", " ")


def export_one(sim_path: Path, out_dir: Path) -> dict:
    """Export a single simulation file to out_dir. Returns run info for runs.json."""
    with open(sim_path) as f:
        data = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_by_id = {t["id"]: t for t in data["tasks"]}
    index = []

    for sim in data["simulations"]:
        task_id = sim["task_id"]
        task = tasks_by_id.get(task_id)
        reward_info = sim.get("reward_info") or {}
        reward = reward_info.get("reward", 0)
        reward_breakdown = reward_info.get("reward_breakdown") or {}
        db_check = reward_info.get("db_check") or {}
        scenario = ""
        if task and task.get("user_scenario", {}).get("instructions"):
            scenario = (task["user_scenario"]["instructions"].get("reason_for_call") or "")[:200]

        payload = {
            "task_id": task_id,
            "task": task,
            "run_info": {
                "simulation_id": sim.get("id"),
                "timestamp": sim.get("timestamp"),
                "duration_sec": round(sim.get("duration", 0), 2),
                "termination_reason": sim.get("termination_reason"),
                "agent_cost": sim.get("agent_cost"),
                "user_cost": sim.get("user_cost"),
            },
            "reward_info": reward_info,
            "messages": sim.get("messages") or [],
        }

        safe_id = sanitize_filename(task_id)
        out_file = out_dir / f"task_{safe_id}.json"
        with open(out_file, "w") as f:
            json.dump(payload, f, indent=2)

        index.append({
            "task_id": task_id,
            "reward": reward,
            "reward_breakdown": reward_breakdown,
            "db_match": db_check.get("db_match"),
            "scenario_preview": scenario,
            "duration_sec": round(sim.get("duration", 0), 2),
            "termination_reason": sim.get("termination_reason"),
            "num_messages": len(sim.get("messages") or []),
        })

    index.sort(key=lambda x: int(x["task_id"]) if str(x["task_id"]).isdigit() else x["task_id"])
    num_passed = sum(1 for t in index if t.get("reward") == 1.0)
    num_tasks = len(index)
    accuracy = round(100.0 * num_passed / num_tasks, 1) if num_tasks else 0

    # Domain from simulation info or parse from run_id (e.g. ..._retail_llm_... -> retail)
    run_id = run_id_from_path(sim_path)
    domain = None
    try:
        env_info = (data.get("info") or {}).get("environment_info")
        if isinstance(env_info, dict):
            domain = env_info.get("domain_name")
    except Exception:
        pass
    if not domain and run_id:
        parts = run_id.split("_")
        if len(parts) >= 2:
            domain = parts[1]

    with open(out_dir / "index.json", "w") as f:
        json.dump({"tasks": index, "run_timestamp": data.get("timestamp")}, f, indent=2)

    return {
        "domain": domain,
        "num_tasks": num_tasks,
        "num_passed": num_passed,
        "accuracy": accuracy,
        "run_timestamp": data.get("timestamp"),
    }


def main():
    base = Path(__file__).resolve().parent.parent
    sims_dir = base / "data" / "simulations"
    data_root = base / "docs" / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Export simulation runs for trajectory viewer")
    parser.add_argument(
        "simulations",
        nargs="*",
        help="Simulation JSON paths; if omitted, all data/simulations/*.json are used",
    )
    args = parser.parse_args()

    if args.simulations:
        sim_paths = [Path(p).resolve() for p in args.simulations]
    else:
        sim_paths = sorted(sims_dir.glob("*.json")) if sims_dir.exists() else []

    if not sim_paths:
        print("No simulation files found. Pass paths or add JSON files to data/simulations/")
        return

    runs = []
    for sim_path in sim_paths:
        if not sim_path.exists():
            print(f"Skip (not found): {sim_path}")
            continue
        run_id = run_id_from_path(sim_path)
        out_dir = data_root / run_id
        try:
            info = export_one(sim_path, out_dir)
            runs.append({
                "id": run_id,
                "label": label_from_path(sim_path),
                "domain": info.get("domain"),
                "timestamp": info.get("run_timestamp"),
                "num_tasks": info["num_tasks"],
                "num_passed": info.get("num_passed", 0),
                "accuracy": info.get("accuracy", 0),
            })
            print(f"Exported {info['num_tasks']} tasks → docs/data/{run_id}/")
        except Exception as e:
            print(f"Error exporting {sim_path}: {e}")
            raise

    with open(data_root / "runs.json", "w") as f:
        json.dump({"runs": runs}, f, indent=2)
    print(f"Wrote runs manifest: docs/data/runs.json ({len(runs)} runs)")


if __name__ == "__main__":
    main()
