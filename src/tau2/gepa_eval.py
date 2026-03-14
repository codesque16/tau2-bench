"""
GEPA evaluation bridge for tau2-bench.

Exposes evaluate_for_gepa() for use with gepa.optimize_anything in generalization mode.
Supports policy_override (full policy) or agent_extra_instructions.
"""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import logfire

from tau2.data_model.simulation import Results, SimulationRun
from tau2.evaluator.evaluator import EvaluationType
from tau2.metrics.agent_metrics import compute_metrics
from tau2.run import get_tasks, run_tasks


def _format_message_for_llm(msg) -> str:
    """Format a single message for LLM consumption (compact)."""
    role = getattr(msg, "role", "unknown")
    content = getattr(msg, "content", None) or ""
    parts = [f"[{role}]"]
    if content and content.strip():
        preview = content[:500] + ("..." if len(content) > 500 else "")
        parts.append(preview)
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            parts.append(f"  ToolCall: {tc.name}({json.dumps(tc.arguments)[:200]}...)")
    return " ".join(parts)


def _format_trace(messages: list, max_messages: int = 30) -> str:
    """Format conversation trace for diagnosis (truncated)."""
    lines = []
    for i, msg in enumerate(messages[:max_messages]):
        lines.append(f"{i+1}. {_format_message_for_llm(msg)}")
    if len(messages) > max_messages:
        lines.append(f"... ({len(messages) - max_messages} more messages)")
    return "\n".join(lines)


def _format_reward_info(sim: SimulationRun) -> str:
    """Format reward info for diagnosis."""
    if not sim.reward_info:
        return "No reward info"
    ri = sim.reward_info
    parts = [f"Reward: {ri.reward:.4f}", f"Termination: {sim.termination_reason}"]
    if ri.db_check:
        parts.append(f"DB check: {'match' if ri.db_check.db_match else 'MISMATCH'} (reward={ri.db_check.db_reward})")
    if ri.communicate_checks:
        for c in ri.communicate_checks:
            status = "met" if c.met else "NOT MET"
            parts.append(f"Communicate '{c.info}': {status}")
            if not c.met and c.justification:
                parts.append(f"  Justification: {c.justification}")
    if ri.action_checks:
        for ac in ri.action_checks:
            if not ac.action_match:
                parts.append(f"Action {ac.action.name}: MISMATCH - {ac.mismatch_reason}")
    return "\n".join(parts)


def _get_qualitative_asi(
    results: Results,
    failed_task_ids: list[str],
    policy_preview: str,
    diagnosis_lm: str,
) -> str:
    """Call LLM to diagnose failed tasks and suggest policy improvements."""
    try:
        import litellm
        from litellm import completion
    except ImportError:
        return "(qualitative ASI skipped: litellm not available)"

    task_by_id = {t.id: t for t in results.tasks}
    sims_by_task = {}
    for sim in results.simulations:
        if sim.task_id not in sims_by_task or (sim.reward_info and sim.reward_info.reward < 0.99):
            sims_by_task[sim.task_id] = sim

    diagnoses = []
    for tid in failed_task_ids[:5]:  # Limit to 5 to control cost
        task = task_by_id.get(tid)
        sim = sims_by_task.get(tid)
        if not task or not sim:
            continue
        task_desc = str(task.user_scenario) if hasattr(task, "user_scenario") and task.user_scenario else f"Task {tid}"
        trace = _format_trace(sim.messages)
        reward_info = _format_reward_info(sim)

        prompt = f"""You are analyzing a failed retail customer-service task for GEPA policy optimization.

## Task
{task_desc[:1500]}

## What went wrong (evaluation)
{reward_info}

## Conversation trace (truncated)
{trace}

## Current policy (preview)
{policy_preview[:2000]}

Analyze:
1. Why did the task fail? (db mismatch, missing communication, wrong action, etc.)
2. What could the policy clarify or add to prevent this?
3. Any specific improvement suggestions for the policy?

Be concise. Focus on actionable policy changes."""

        try:
            resp = completion(
                model=diagnosis_lm,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            text = resp.choices[0].message.content or ""
            diagnoses.append(f"### Task {tid}\n{text}")
        except Exception as e:
            diagnoses.append(f"### Task {tid}\n(Diagnosis error: {e})")

    return "\n\n".join(diagnoses) if diagnoses else ""


def evaluate_for_gepa(
    task_ids: list[str],
    agent_extra_instructions: str = "",
    policy_override: str | None = None,
    domain: str = "retail",
    task_set_name: str = "retail_solo_comms",
    agent: str = "llm_agent_solo2",
    user: str = "dummy_user",
    llm_agent: str = "gpt-5-mini",
    max_steps: int = 60,
    num_trials: int = 1,
    seed: int = 7789797979,
    log_level: str = "WARNING",
    solo_comms_only: bool = False,
    diagnosis_lm: str | None = None,
    gepa_context: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Run tau2 simulations for the given task IDs and return (score, feedback).

    Used by GEPA optimize_anything. Supports two modes:
    - policy_override: Full policy content (optimizing policy_solo.md). Written to temp file, set via TAU2_POLICY_SOLO_OVERRIDE.
    - agent_extra_instructions: Extra instructions appended to agent prompt via TAU2_AGENT_EXTRA_INSTRUCTIONS.

    Args:
        task_ids: Task IDs to evaluate (from split_tasks.json train/test).
        agent_extra_instructions: Extra instructions (when not using policy_override).
        policy_override: Full policy content. When set, overrides policy_solo.md for this eval.
        domain: Tau2 domain (default: retail).
        task_set_name: Task set (default: retail_solo_comms).
        agent: Agent type (default: llm_agent_solo2).
        user: User simulator (default: dummy_user).
        llm_agent: Model for the agent (default: gpt-5-mini).
        max_steps: Max simulation steps.
        num_trials: Trials per task.
        seed: Random seed.
        log_level: Log level to reduce noise.
        solo_comms_only: When True and task_set is retail_solo_comms, run only
            tasks with communicate_info.
        diagnosis_lm: When set and tasks fail, call this LLM to diagnose (db mismatch,
            communication gaps, etc.) and suggest policy improvements. Added to feedback as qualitative_asi.
        gepa_context: Optional dict from GEPA's get_gepa_eval_context() with iteration, split,
            candidate_idx. Used to enrich the Logfire span name and attributes.

    Returns:
        (score, feedback_dict) where score is pass^1 (higher is better) and
        feedback_dict contains metrics and per-task diagnostics for GEPA reflection.
    """
    tasks = get_tasks(
        task_set_name=task_set_name,
        task_split_name="base",
        task_ids=task_ids,
    )
    if not tasks:
        return 0.0, {"error": f"No valid tasks for ids {task_ids}", "task_ids": task_ids}

    # Filter for solo_comms_only when applicable
    if solo_comms_only and task_set_name == "retail_solo_comms":
        from tau2.agent.llm_agent import LLMSoloAgent2

        tasks = [
            t
            for t in tasks
            if t.evaluation_criteria and len(t.evaluation_criteria.communicate_info or []) > 0
        ]
        if not tasks:
            return 0.0, {"error": "No tasks with communicate_info after filter", "task_ids": task_ids}

    # Use temp dir for save_to to avoid interactive resume prompt
    run_id = f"gepa_eval_{uuid.uuid4().hex[:12]}"
    qualitative_asi: str | None = None
    with tempfile.TemporaryDirectory() as tmpdir:
        save_to = Path(tmpdir) / f"{run_id}.json"

        prev_policy_override = os.environ.get("TAU2_POLICY_SOLO_OVERRIDE")
        prev_extra = os.environ.get("TAU2_AGENT_EXTRA_INSTRUCTIONS")

        try:
            if policy_override is not None:
                policy_path = Path(tmpdir) / "policy_solo_override.md"
                policy_path.write_text(policy_override, encoding="utf-8")
                os.environ["TAU2_POLICY_SOLO_OVERRIDE"] = str(policy_path)
                os.environ.pop("TAU2_AGENT_EXTRA_INSTRUCTIONS", None)
            else:
                os.environ["TAU2_AGENT_EXTRA_INSTRUCTIONS"] = agent_extra_instructions or ""
                os.environ.pop("TAU2_POLICY_SOLO_OVERRIDE", None)

            # Build descriptive span name: always include task_id(s) when available
            if len(task_ids) == 1:
                task_str = f" task_id:{task_ids[0]}"
            elif len(task_ids) > 1:
                task_str = f" task_ids:[{','.join(str(t) for t in task_ids)}]"
            else:
                task_str = ""
            span_name = f"gepa_eval{task_str}"
            span_attrs: dict[str, Any] = {
                "task_ids": task_ids,
                "domain": domain,
                "task_set_name": task_set_name,
            }
            if gepa_context:
                span_attrs["iteration"] = gepa_context.get("iteration")
                span_attrs["split"] = gepa_context.get("split")
                span_attrs["candidate_idx"] = gepa_context.get("candidate_idx")
                span_attrs["eval_type"] = gepa_context.get("eval_type")
                span_attrs["minibatch_size"] = gepa_context.get("minibatch_size")
                iter_ = gepa_context.get("iteration")
                split_ = gepa_context.get("split")
                eval_type_ = gepa_context.get("eval_type")
                minibatch_size_ = gepa_context.get("minibatch_size")
                if iter_ is not None and split_ is not None:
                    suffix_map = {"seed": " (seed)", "minibatch": " (minibatch)", "val": " (val)"}
                    suffix = suffix_map.get(eval_type_, f" ({eval_type_})" if eval_type_ else "")
                    mb_str = f" minibatch_size={minibatch_size_}" if minibatch_size_ is not None else ""
                    span_name = f"gepa_eval iter={iter_} ({split_}){suffix}{task_str}{mb_str}"
            with logfire.span(span_name, **span_attrs):
                results = run_tasks(
                    domain=domain,
                    tasks=tasks,
                    agent=agent,
                    user=user,
                    llm_agent=llm_agent,
                    num_trials=num_trials,
                    max_steps=max_steps,
                    save_to=save_to,
                    console_display=False,
                    evaluation_type=EvaluationType.ALL,
                    max_concurrency=1,
                    seed=seed,
                    log_level=log_level,
                    solo_eval_db_only=False,
                )
                # Run diagnostic LLM inside gepa_eval span so completion spans nest
                df = results.to_df()
                failed_tasks: list[str] = []
                if "reward" in df.columns and "task_id" in df.columns:
                    task_rewards = df.groupby("task_id")["reward"].mean()
                    failed_tasks = [tid for tid, r in task_rewards.items() if r < 0.99]
                if failed_tasks and diagnosis_lm:
                    policy_preview = (policy_override or agent_extra_instructions or "")[:3000]
                    qualitative_asi = _get_qualitative_asi(
                        results=results,
                        failed_task_ids=failed_tasks,
                        policy_preview=policy_preview,
                        diagnosis_lm=diagnosis_lm,
                    )
        finally:
            if prev_policy_override is not None:
                os.environ["TAU2_POLICY_SOLO_OVERRIDE"] = prev_policy_override
            else:
                os.environ.pop("TAU2_POLICY_SOLO_OVERRIDE", None)
            if prev_extra is not None:
                os.environ["TAU2_AGENT_EXTRA_INSTRUCTIONS"] = prev_extra
            else:
                os.environ.pop("TAU2_AGENT_EXTRA_INSTRUCTIONS", None)

    metrics = compute_metrics(results)

    # Primary score: pass^1 (fraction of tasks solved)
    score = float(metrics.pass_hat_ks.get(1, 0.0))

    # Build feedback for GEPA reflection
    feedback: dict[str, Any] = {
        "score": score,
        "avg_reward": metrics.avg_reward,
        "pass_hat_1": metrics.pass_hat_ks.get(1),
        "avg_agent_cost": metrics.avg_agent_cost,
        "num_tasks": len(tasks),
        "num_trials": num_trials,
    }

    # Per-task diagnostics (what went wrong)
    df = results.to_df()
    failed_tasks: list[str] = []
    if "reward" in df.columns and "task_id" in df.columns:
        task_rewards = df.groupby("task_id")["reward"].mean()
        failed_tasks = [tid for tid, r in task_rewards.items() if r < 0.99]
        if failed_tasks:
            feedback["failed_task_ids"] = failed_tasks
            # Include termination reasons for failed runs
            failed_df = df[df["task_id"].isin(failed_tasks)]
            if "termination_reason" in failed_df.columns:
                feedback["termination_reasons"] = (
                    failed_df.groupby("task_id")["termination_reason"].first().to_dict()
                )

    # Qualitative ASI (computed inside gepa_eval span for proper nesting)
    if qualitative_asi:
        feedback["qualitative_asi"] = qualitative_asi

    return score, feedback
