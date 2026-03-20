"""
GEPA evaluation bridge for tau2-bench.

Exposes evaluate_for_gepa() for use with gepa.optimize_anything in generalization mode.
Supports policy_override (full policy) or agent_extra_instructions.
"""

import hashlib
import inspect
import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

import logfire

from tau2.data_model.simulation import Results, SimulationRun
from tau2.evaluator.evaluator import EvaluationType
from tau2.metrics.agent_metrics import compute_metrics, is_successful
from tau2.run import _set_span_display_name, get_tasks, run_tasks


def _gepa_eval_all_tasks_pass(results: Results) -> bool:
    """True iff every task's mean reward counts as success (same threshold as task spans)."""
    df = results.to_df()
    if df.empty or "reward" not in df.columns or "task_id" not in df.columns:
        return False
    for mean_reward in df.groupby("task_id")["reward"].mean():
        if not is_successful(float(mean_reward)):
            return False
    return True


def _serialize_message(msg: Any) -> dict[str, Any]:
    """Serialize a simulation message into a JSON-friendly dict."""
    data: dict[str, Any] = {
        "role": getattr(msg, "role", "unknown"),
    }
    content = getattr(msg, "content", None)
    if content is not None:
        data["content"] = content

    # Some tool responses may carry a tool name on the message.
    tool_name = getattr(msg, "name", None)
    if tool_name is not None:
        data["tool_name"] = tool_name

    # OpenAI-style tool calls attached to assistant messages.
    tool_calls: list[dict[str, Any]] = []
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            tool_calls.append(
                {
                    "name": getattr(tc, "name", None),
                    "arguments": getattr(tc, "arguments", None),
                }
            )
    if tool_calls:
        data["tool_calls"] = tool_calls

    return data


def _get_retail_available_tools_list() -> str:
    """Build a compact tools list for the optimizer prompt.

    The optimizer benefits most from a simple, stable list of tool names to reason about
    missing capabilities. Detailed schemas can be derived from traces when needed.
    """
    try:
        from tau2.domains.retail.tools import RetailTools
    except ImportError:
        return "(Retail tools schema unavailable: domain not loaded)"
    lines = ["Tool list available to the agent:"]
    tools: list[tuple[str, str]] = []
    excluded = {"bash", "all_todo_done"}
    for name in dir(RetailTools):
        if name.startswith("_"):
            continue
        if name in excluded:
            continue
        try:
            method = getattr(RetailTools, name)
            if callable(method) and getattr(method, "__tool__", False):
                # Include a compact view of tool arguments to make the
                # optimizer/evaluator prompts more actionable.
                sig_str = ""
                try:
                    sig = inspect.signature(method)
                    params = []
                    for p in sig.parameters.values():
                        if p.name in {"self", "cls"}:
                            continue
                        params.append(str(p))
                    sig_str = f"({', '.join(params)})"
                except Exception:
                    sig_str = "()"
                tools.append((name, sig_str))
        except Exception:
            pass
    for idx, (name, sig_str) in enumerate(sorted(tools, key=lambda x: x[0]), start=1):
        lines.append(f"{idx}) {name}{sig_str}")
    return "\n".join(lines).strip()


def _format_conversation_dialogue(
    messages: list,
    max_messages: int | None = None,
) -> str:
    """Format conversation for the optimizer prompt and qualitative diagnosis traces.

    Target format (easy to skim):
    [User]:
      ...
    [Assistant]:
      (ToolCall : id) tool_name {...}
      assistant text...
    [Tool]:
      (Tool output: id)
        ...
    """
    def _inline_json(obj: object | None) -> str:
        try:
            return json.dumps(obj or {}, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(obj or {})

    out: list[str] = []
    iterable = messages if max_messages is None else messages[:max_messages]
    for msg in iterable:
        role = getattr(msg, "role", "unknown")
        content_raw = getattr(msg, "content", None) or ""
        content = str(content_raw).strip()

        if role == "user":
            out.append("[User]:")
            out.append(f"  {content}" if content else "  (no text)")

        elif role == "assistant":
            out.append("[Assistant]:")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    name = getattr(tc, "name", "?")
                    tool_id = getattr(tc, "id", None) or getattr(tc, "tool_id", None) or "unknown"
                    args = getattr(tc, "arguments", None)
                    out.append(f"  (ToolCall : {tool_id}) {name} {_inline_json(args)}")
            # Only show assistant free-form text when it exists; for pure
            # tool-call turns, skip the "(no assistant text)" filler.
            if content:
                out.extend([f"  {line}" for line in content.splitlines()])
            # else:
            #     out.append("  (no assistant text)")

        elif role == "tool":
            tool_id = getattr(msg, "tool_id", None) or getattr(msg, "id", None) or "unknown"
            # Drop the redundant tool name label; the tool id is enough and
            # the content that follows shows the full payload.
            out.append(f"  (Tool output: {tool_id})")
            if content:
                out.extend([f"    {line}" for line in content.splitlines()])
            else:
                out.append("    (empty)")

        else:
            out.append(f"[{str(role).title()}]:")
            out.append(f"  {content}" if content else "  (no text)")

        out.append("")

    if max_messages is not None and len(messages) > max_messages:
        out.append(f"... ({len(messages) - max_messages} more messages)")
        out.append("")

    return "\n".join(out).strip()


def _format_trace(messages: list, max_messages: int | None = None) -> str:
    """Same as ``_format_conversation_dialogue`` (block [User]/[Assistant]/[Tool] layout)."""
    return _format_conversation_dialogue(messages, max_messages=max_messages)


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
        def _dump(obj: object | None) -> str:
            try:
                return json.dumps(obj or {}, ensure_ascii=False, sort_keys=True)
            except Exception:
                return str(obj or {})

        for ac in ri.action_checks:
            if not ac.action_match:
                expected_args = getattr(ac.action, "arguments", None)
                reason = (ac.mismatch_reason or "mismatch").strip()
                if reason == "not_called":
                    parts.append(
                        f"Action {ac.action.name}: NOT CALLED (expected_args={_dump(expected_args)})"
                    )
                elif reason == "arguments_mismatch":
                    parts.append(
                        f"Action {ac.action.name}: ARGUMENTS_MISMATCH "
                        f"(expected_args={_dump(expected_args)}, actual_args={_dump(ac.actual_arguments)})"
                    )
                else:
                    parts.append(
                        f"Action {ac.action.name}: MISMATCH ({reason}) "
                        f"(expected_args={_dump(expected_args)}, actual_args={_dump(ac.actual_arguments)})"
                    )
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
        task_desc = task.ticket
        # Use full, untruncated trace for qualitative diagnosis.
        trace = _format_trace(sim.messages, max_messages=None)
        reward_info = _format_reward_info(sim)
        tools_list = _get_retail_available_tools_list()

        prompt = f"""You are an evaluator producing feedback for a retail customer-service trace.

Your goal is to analyse the <current_policy> trace and reward info and give a diagnostic analysis of what went wrong along with policy improvements to the <current_policy>, 
BUT you are only allowed to suggest changes within EXACTLY these three sections:
1) SOP Global Policies
2) SOP Node Policies
3) SOP Flowchart

You MUST output feedback for this trace (it is a failed trace) in the following <format>. 

<format>
### Diagnostic Analysis
...

### Policy Improvements
1) SOP Global Policies
    ...
2) SOP Node Policies
    ...
3) SOP Flowchart
    ...
</format>

<task>
{task_desc}
</task>

<tools_list>
{tools_list}
</tools_list>

<evaluation>
{reward_info}
</evaluation>

<conversation_trace>
{trace}
</conversation_trace>

<current_policy>
{policy_preview}
</current_policy>
"""

        try:
            resp = completion(
                model=diagnosis_lm,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            text = resp.choices[0].message.content or ""
            # Omit task id in output; multiple failures are still separated by blank lines.
            diagnoses.append(text.strip())
        except Exception as e:
            diagnoses.append(f"(Diagnosis error: {e})")

    return "\n\n".join(diagnoses) if diagnoses else ""


def evaluate_for_gepa(
    task_ids: list[str],
    agent_extra_instructions: str = "",
    policy_override: str | None = None,
    domain: str = "retail",
    task_set_name: str = "retail_solo_comms",
    agent: str = "llm_agent_solo2",
    user: str = "dummy_user",
    llm_agent: str = "gpt-5-nano",
    max_steps: int = 60,
    num_trials: int = 1,
    seed: int | None = None,
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
            communication gaps, etc.) and suggest policy improvements. The result is added to
            feedback as ``qualitative_asi`` (one block per failed task, up to 5).
        gepa_context: Optional dict from GEPA's get_gepa_eval_context() with iteration, split,
            candidate_idx. Used to enrich the Logfire span name and attributes.

    Returns:
        (score, feedback_dict) where score is pass^1 (higher is better) and
        feedback_dict contains metrics and per-task diagnostics for GEPA reflection.
    """
    import random

    # If seed is not provided, vary it per call to avoid deterministic coupling.
    effective_seed = seed if seed is not None else random.randrange(1, 1_000_000_000)

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

        try:
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
            # Attach a stable hash of the policy being used so Logfire can distinguish runs.
            if policy_override is not None:
                policy_hash = hashlib.sha256(policy_override.encode("utf-8")).hexdigest()[:12]
                span_attrs["policy_override_sha256_12"] = policy_hash
                span_name = f"{span_name} policy={policy_hash}"
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
            with logfire.span(span_name, **span_attrs) as gepa_span:
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
                    seed=effective_seed,
                    log_level=log_level,
                    solo_eval_db_only=False,
                    policy_override=policy_override,
                )
                outcome = "pass" if _gepa_eval_all_tasks_pass(results) else "fail"
                gepa_span.set_attribute("eval_outcome", outcome)
                _set_span_display_name(gepa_span, f"{span_name} [{outcome}]")
                # Run diagnostic LLM inside gepa_eval span so completion spans nest
                df = results.to_df()
                failed_tasks: list[str] = []
                if "reward" in df.columns and "task_id" in df.columns:
                    task_rewards = df.groupby("task_id")["reward"].mean()
                    failed_tasks = [tid for tid, r in task_rewards.items() if r < 0.99]
                if failed_tasks and diagnosis_lm:
                    policy_preview = (policy_override or agent_extra_instructions or "")
                    qualitative_asi = _get_qualitative_asi(
                        results=results,
                        failed_task_ids=failed_tasks,
                        policy_preview=policy_preview,
                        diagnosis_lm=diagnosis_lm,
                    )
        finally:
            pass

    metrics = compute_metrics(results)

    # Primary score: pass^1 (fraction of tasks solved)
    score = float(metrics.pass_hat_ks.get(1, 0.0))

    # Build feedback for GEPA reflection
    feedback: dict[str, Any] = {
        "score": score,
        # "avg_reward": metrics.avg_reward,
        # "pass_hat_1": metrics.pass_hat_ks.get(1),
        # "avg_agent_cost": metrics.avg_agent_cost,
        # "num_tasks": len(tasks),
        # "num_trials": num_trials,
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

    # Available tools list (retail domain): name + parameters for the optimizer prompt.
    if domain == "retail":
        feedback["tools_list"] = _get_retail_available_tools_list()

    # Per-task traces: readable dialogue and tools used (no duplicate candidate).
    # One representative simulation per task (last seen, preferring lower-reward).
    task_by_id = {t.id: t for t in results.tasks}
    sims_by_task: dict[str, SimulationRun] = {}
    for sim in results.simulations:
        if sim.task_id not in sims_by_task or (sim.reward_info and sim.reward_info.reward < 0.99):
            sims_by_task[sim.task_id] = sim

    per_task_traces: dict[str, dict[str, Any]] = {}
    for tid, sim in sims_by_task.items():
        task_obj = task_by_id.get(tid)
        ticket_text = task_obj.ticket
        messages = getattr(sim, "messages", [])
        # Conversation as readable dialogue (User / Assistant / Tool).
        conversation_text = _format_conversation_dialogue(messages)
        reward_info_text = _format_reward_info(sim)


        per_task_traces[tid] = {
            "task_description": ticket_text,
            "reward_info": reward_info_text,
            "conversation": conversation_text,
        }

    if per_task_traces:
        feedback["per_task_traces"] = per_task_traces

    # qualitative_asi: LLM-generated diagnosis of failed tasks (from diagnosis_lm) with
    # actionable policy improvement suggestions. Only present when diagnosis_lm is set
    # and some tasks failed (reward < 0.99).
    if qualitative_asi:
        feedback["qualitative_asi"] = qualitative_asi

    return score, feedback
