#!/usr/bin/env python3
"""
Standalone script to run the DB match check (same logic as EnvironmentEvaluator).

Compares:
  - Gold DB state: initial state + apply only the task's golden actions in order.
  - Predicted DB state: initial state + replay the full conversation trajectory.

Usage:
  From tau2-bench with PYTHONPATH including src:
    python scripts/run_db_check.py --simulation path/to/simulation.json --task-id 27

  Optional:
    --tasks path/to/tasks.json   Use this task set instead of the simulation's embedded tasks.
    --verbose                    When db_match is False, print agent/user hashes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tau2.data_model.message import AssistantMessage, Message, UserMessage
    from tau2.data_model.simulation import Results
    from tau2.data_model.tasks import Task
    from tau2.domains.retail.environment import get_environment
    from tau2.environment.environment import Environment
except ImportError:
    print("Set PYTHONPATH to tau2-bench/src (e.g. PYTHONPATH=src python scripts/run_db_check.py ...)", file=sys.stderr)
    sys.exit(1)


def run_db_check(
    task: Task,
    full_trajectory: list[Message],
    environment_constructor: callable,
    solo_mode: bool = False,
    verbose: bool = False,
) -> tuple[bool, float, dict]:
    if task.evaluation_criteria is None:
        return True, 1.0, {"note": "No evaluation criteria"}
    expected_actions = task.evaluation_criteria.actions
    if expected_actions is None:
        return True, 1.0, {"note": "No expected actions"}

    initialization_data = getattr(task.initial_state, "initialization_data", None) if task.initial_state else None
    initialization_actions = getattr(task.initial_state, "initialization_actions", None) if task.initial_state else None
    message_history_gold = getattr(task.initial_state, "message_history", None) or []
    if task.initial_state and task.initial_state.message_history is not None:
        message_history_gold = task.initial_state.message_history

    predicted_environment: Environment = environment_constructor(solo_mode=solo_mode)
    try:
        predicted_environment.set_state(
            initialization_data=initialization_data,
            initialization_actions=initialization_actions,
            message_history=full_trajectory,
        )
    except Exception as e:
        return False, 0.0, {"error": "predicted set_state failed", "message": str(e)}

    gold_environment: Environment = environment_constructor()
    gold_environment.set_state(
        initialization_data=initialization_data,
        initialization_actions=initialization_actions,
        message_history=message_history_gold,
    )
    for action in expected_actions:
        try:
            gold_environment.make_tool_call(
                tool_name=action.name,
                requestor=action.requestor,
                **action.arguments,
            )
        except Exception as e:
            return False, 0.0, {"error": "gold make_tool_call failed", "action": action.name, "message": str(e)}

    agent_db_hash = gold_environment.get_db_hash()
    user_db_hash = gold_environment.get_user_db_hash()
    predicted_agent_db_hash = predicted_environment.get_db_hash()
    predicted_user_db_hash = predicted_environment.get_user_db_hash()

    agent_db_match = agent_db_hash == predicted_agent_db_hash
    user_db_match = (user_db_hash == predicted_user_db_hash) if (user_db_hash is not None and predicted_user_db_hash is not None) else (user_db_hash is None and predicted_user_db_hash is None)

    db_match = agent_db_match and user_db_match
    db_reward = 1.0 if db_match else 0.0

    info = {"agent_db_match": agent_db_match, "user_db_match": user_db_match}
    if verbose or not db_match:
        info["gold_agent_db_hash"] = agent_db_hash
        info["predicted_agent_db_hash"] = predicted_agent_db_hash
        info["gold_user_db_hash"] = user_db_hash
        info["predicted_user_db_hash"] = predicted_user_db_hash

    return db_match, db_reward, info


def load_tasks_from_json(path: Path) -> list[Task]:
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [Task.model_validate(t) for t in data]
    if isinstance(data, dict) and "tasks" in data:
        return [Task.model_validate(t) for t in data["tasks"]]
    raise ValueError(f"Expected list of tasks or {{'tasks': [...]}} in {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DB match check using tasks and simulation JSON.")
    parser.add_argument("--simulation", type=Path, required=True, help="Path to simulation Results JSON.")
    parser.add_argument("--task-id", type=str, required=True, help="Task ID (e.g. 27).")
    parser.add_argument("--tasks", type=Path, default=None, help="Optional path to tasks.json (else use simulation's tasks).")
    parser.add_argument("--verbose", action="store_true", help="Print hashes when db_match is False.")
    args = parser.parse_args()

    if not args.simulation.exists():
        print(f"Error: simulation file not found: {args.simulation}", file=sys.stderr)
        sys.exit(1)

    results = Results.load(args.simulation)

    if args.tasks is not None:
        if not args.tasks.exists():
            print(f"Error: tasks file not found: {args.tasks}", file=sys.stderr)
            sys.exit(1)
        tasks_list = load_tasks_from_json(args.tasks)
        task = next((t for t in tasks_list if t.id == args.task_id), None)
    else:
        task = next((t for t in results.tasks if t.id == args.task_id), None)

    if task is None:
        print(f"Error: task_id {args.task_id} not found.", file=sys.stderr)
        sys.exit(1)

    run = next((s for s in results.simulations if s.task_id == args.task_id), None)
    if run is None:
        print(f"Error: no simulation run for task_id {args.task_id}.", file=sys.stderr)
        sys.exit(1)

    def env_constructor(solo_mode: bool = False):
        return get_environment(solo_mode=solo_mode)

    db_match, db_reward, info = run_db_check(
        task=task,
        full_trajectory=run.messages,
        environment_constructor=env_constructor,
        solo_mode=False,
        verbose=args.verbose,
    )

    print("db_match:", db_match)
    print("db_reward:", db_reward)
    for k, v in info.items():
        if k.endswith("_hash") and v is not None and len(str(v)) > 64:
            print(f"{k}: {str(v)[:32]}...")
        else:
            print(f"{k}: {v}")

    sys.exit(0 if db_match else 1)


if __name__ == "__main__":
    main()