#!/usr/bin/env python3
"""
Analyze simulation traces: find all reward=0 tasks, compare with task definitions,
and output structured failure reasons for documentation.
"""
import json
import sys
from pathlib import Path

def main():
    base = Path(__file__).resolve().parent.parent
    sim_path = base / "data/simulations/2026-02-21T00:37:20.185158_retail_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1-mini.json"
    tasks_path = base / "data/tau2/domains/retail/tasks.json"

    with open(sim_path) as f:
        data = json.load(f)
    with open(tasks_path) as f:
        tasks_list = json.load(f)

    tasks_by_id = {t["id"]: t for t in tasks_list}
    simulations = data["simulations"]

    failed = []
    for sim in simulations:
        if sim.get("reward_info", {}).get("reward", 1) != 0:
            continue
        task_id = sim["task_id"]
        ri = sim["reward_info"]
        task = tasks_by_id.get(task_id)

        failure = {
            "task_id": task_id,
            "termination_reason": sim.get("termination_reason"),
            "db_match": ri.get("db_check", {}).get("db_match"),
            "reward_breakdown": ri.get("reward_breakdown"),
            "failed_actions": [],
            "expected_actions": [],
            "task_reason": None,
            "task_instructions": None,
        }
        if task and task.get("user_scenario", {}).get("instructions"):
            inst = task["user_scenario"]["instructions"]
            failure["task_reason"] = inst.get("reason_for_call")
            failure["task_instructions"] = inst.get("task_instructions")
            failure["known_info"] = inst.get("known_info")
            failure["unknown_info"] = inst.get("unknown_info")

        for check in ri.get("action_checks") or []:
            expected = check.get("action", {})
            failure["expected_actions"].append({
                "action_id": expected.get("action_id"),
                "name": expected.get("name"),
                "arguments": expected.get("arguments"),
            })
            if not check.get("action_match"):
                failure["failed_actions"].append({
                    "action_id": expected.get("action_id"),
                    "name": expected.get("name"),
                    "arguments": expected.get("arguments"),
                })

        if ri.get("communicate_checks"):
            failure["communicate_checks"] = ri["communicate_checks"]
        if ri.get("reward_basis"):
            failure["reward_basis"] = ri["reward_basis"]

        failed.append(failure)

    out = {
        "total_simulations": len(simulations),
        "total_failed": len(failed),
        "failed_tasks": failed,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
