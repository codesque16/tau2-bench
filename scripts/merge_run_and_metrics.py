#!/usr/bin/env python3
"""
Merge simulation files by domain for a single run [R1][GEMINI-F3][BASE],
then compute metrics and cache-aware costing.

Usage:
  # Merge configured retail/airline files, save, and print metrics:
  python scripts/merge_run_and_metrics.py

  # Only compute and print metrics for one or more already-merged files:
  python scripts/merge_run_and_metrics.py path/to/[RETAIL][TH1][GEMINI-F3-HIGH][BASE].json
  python scripts/merge_run_and_metrics.py retail.json airline.json
"""

import argparse
from pathlib import Path

from litellm import cost_per_token

from tau2.data_model.simulation import Results, SimulationRun, Task
from tau2.metrics.agent_metrics import AgentMetrics, compute_metrics

# Paths relative to tau2-bench
SIM_DIR = Path(__file__).resolve().parent.parent / "data" / "simulations"
OUT_DIR = SIM_DIR  # same dir as input

RETAIL_FILES = [
    "2026-02-20T13:12:08.293690_retail_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",  # first 20 tasks
    "2026-02-20T13:18:11.907717_retail_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
    "2026-02-20T13:40:20.239686_retail_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
    "2026-02-20T13:47:05.265863_retail_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
]
# AIRLINE_FILES = [
#     "2026-02-20T13:23:18.334480_airline_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
#     "2026-02-20T13:30:13.536391_airline_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
# ]


AIRLINE_FILES = [
    "2026-02-20T16:46:41.781535_airline_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
    "2026-02-20T16:57:34.051912_airline_llm_agent_gemini-3-flash-preview_user_simulator_gemini-3-flash-preview.json",
]


RETAIL_OUT = "[RETAIL][R1][GEMINI-F3][BASE].json"
AIRLINE_OUT = "[AIRLINE][TH1][GEMINI-F3-HIGH][BASE].json"

MODEL = "gemini/gemini-3-flash-preview"
CACHE_DISCOUNT = 0.10  # cache tokens at 10% of base input price


def merge_results(paths: list[Path]) -> Results:
    """Merge multiple result files: union of tasks (by id), concatenate simulations."""
    all_tasks: dict[str, Task] = {}
    all_simulations: list[SimulationRun] = []
    info = None
    timestamp = None

    for p in paths:
        if not p.exists():
            raise FileNotFoundError(p)
        r = Results.load(p)
        if info is None:
            info = r.info
            timestamp = r.timestamp
        for t in r.tasks:
            all_tasks[t.id] = t
        all_simulations.extend(r.simulations)

    return Results(
        timestamp=timestamp,
        info=info,
        tasks=list(all_tasks.values()),
        simulations=all_simulations,
    )


def cache_aware_cost_and_tokens(
    results: Results, model: str = MODEL, cache_discount: float = CACHE_DISCOUNT
) -> tuple[
    float, float,
    int, int, int, int,
    int, int, int, int,
    int, int, int, int,
    int, int, int,
]:
    """
    Compute cache-aware agent cost and token totals over all simulations.

    Cache-aware costing:
    - Output tokens: same rate as base.
    - Prompt tokens: tokens read from cache at (cache_discount * base input price),
      remaining prompt tokens at full input price.

    Returns:
        (total_agent_cost_cache_aware, total_user_cost_cache_aware,
         total_prompt_tokens, total_completion_tokens, total_cached_input_tokens, total_cached_completion_tokens,
         agent_prompt, agent_completion, agent_cached_in, agent_cached_comp,
         user_prompt, user_completion, user_cached_in, user_cached_comp,
         total_reasoning_tokens, agent_reasoning_tokens, user_reasoning_tokens)
    """
    try:
        input_cost_1, _ = cost_per_token(model=model, prompt_tokens=1, completion_tokens=0)
        _, output_cost_1 = cost_per_token(model=model, prompt_tokens=0, completion_tokens=1)
    except Exception:
        input_cost_1 = 5e-7
        output_cost_1 = 3e-6
    cached_input_price = cache_discount * input_cost_1

    total_agent_cache_aware = 0.0
    total_user_cache_aware = 0.0
    total_prompt = 0
    total_completion = 0
    total_cached_input = 0
    total_cached_completion = 0
    agent_prompt = agent_completion = agent_cached_in = agent_cached_comp = 0
    user_prompt = user_completion = user_cached_in = user_cached_comp = 0
    total_reasoning = agent_reasoning = user_reasoning = 0

    for sim in results.simulations:
        for msg in sim.messages:
            role = getattr(msg, "role", None)
            if role == "tool":
                continue
            usage = getattr(msg, "usage", None) or {}
            if not usage:
                continue
            pt = int(usage.get("prompt_tokens", 0))
            ct = int(usage.get("completion_tokens", 0))
            cache_read = int(usage.get("cache_read_tokens", 0))
            cache_creation = int(usage.get("cache_creation_input_tokens", 0))
            # Reasoning/thinking tokens (e.g. Gemini completion_tokens_details.reasoning_tokens)
            comp_details = usage.get("completion_tokens_details") or {}
            raw_reasoning = (
                usage.get("reasoning_tokens")
                or comp_details.get("reasoning_tokens")
                or comp_details.get("reasoning")
            )
            reasoning = int(raw_reasoning) if raw_reasoning is not None else 0

            total_prompt += pt
            total_completion += ct
            total_cached_input += cache_read
            total_cached_completion += cache_creation
            total_reasoning += reasoning

            if role == "assistant":
                agent_prompt += pt
                agent_completion += ct
                agent_cached_in += cache_read
                agent_cached_comp += cache_creation
                agent_reasoning += reasoning
            else:
                user_prompt += pt
                user_completion += ct
                user_cached_in += cache_read
                user_cached_comp += cache_creation
                user_reasoning += reasoning

            non_cached_input = max(0, pt - cache_read)
            cost_msg = (
                non_cached_input * input_cost_1
                + cache_read * cached_input_price
                + ct * output_cost_1
            )
            if role == "assistant":
                total_agent_cache_aware += cost_msg
            else:
                total_user_cache_aware += cost_msg

    return (
        total_agent_cache_aware,
        total_user_cache_aware,
        total_prompt,
        total_completion,
        total_cached_input,
        total_cached_completion,
        agent_prompt,
        agent_completion,
        agent_cached_in,
        agent_cached_comp,
        user_prompt,
        user_completion,
        user_cached_in,
        user_cached_comp,
        total_reasoning,
        agent_reasoning,
        user_reasoning,
    )


def report(name: str, results: Results) -> None:
    """Print metrics and token/cost stats for a Results object."""
    metrics: AgentMetrics = compute_metrics(results)
    n = len(results.simulations)
    agent_costs = [s.agent_cost for s in results.simulations if s.agent_cost is not None]
    user_costs = [s.user_cost for s in results.simulations if s.user_cost is not None]
    avg_user = sum(user_costs) / len(user_costs) if user_costs else 0.0

    print(f"=== {name} ===")
    print(f"  Average reward:     {metrics.avg_reward:.4f}")
    for k, v in sorted(metrics.pass_hat_ks.items()):
        print(f"  Pass^{k}:            {v:.4f}")
    print(f"  Avg agent cost:     ${metrics.avg_agent_cost:.6f}")
    print(f"  Avg user cost:      ${avg_user:.6f}")
    print(f"  Avg total (agent+user): ${metrics.avg_agent_cost + avg_user:.6f}")

    (
        agent_ca,
        user_ca,
        tot_prompt,
        tot_comp,
        tot_cached_in,
        tot_cached_comp,
        agent_prompt,
        agent_completion,
        agent_cached_in,
        agent_cached_comp,
        user_prompt,
        user_completion,
        user_cached_in,
        user_cached_comp,
        tot_reasoning,
        agent_reasoning,
        user_reasoning,
    ) = cache_aware_cost_and_tokens(results)
    print(f"  Cache-aware avg agent cost: ${agent_ca / n:.6f}")
    print(f"  Cache-aware avg user cost:  ${user_ca / n:.6f}")
    print(f"  Cache-aware avg total:       ${(agent_ca + user_ca) / n:.6f}")
    print(f"  Total prompt tokens:        {tot_prompt}  (agent: {agent_prompt}, user: {user_prompt})")
    print(f"  Total completion tokens:    {tot_comp}  (agent: {agent_completion}, user: {user_completion})")
    print(f"  Total cached (input) tokens: {tot_cached_in}  (agent: {agent_cached_in}, user: {user_cached_in})")
    print(f"  Total cache-creation (completion) tokens: {tot_cached_comp}  (agent: {agent_cached_comp}, user: {user_cached_comp})")
    if tot_reasoning:
        print(f"  Total reasoning tokens:     {tot_reasoning}  (agent: {agent_reasoning}, user: {user_reasoning})")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge simulation files and/or compute metrics. Pass file path(s) to only compute metrics for already-merged file(s)."
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Optional: path(s) to merged JSON file(s). If given, only stats/metrics are printed (no merge).",
    )
    args = parser.parse_args()

    if args.files:
        # Metrics-only mode: load each file and report
        for p in args.files:
            p = p.resolve()
            if not p.exists():
                raise SystemExit(f"File not found: {p}")
            results = Results.load(p)
            name = p.stem  # e.g. [RETAIL][TH1][GEMINI-F3-HIGH][BASE]
            report(name, results)
        return

    # Default: merge configured files, save, then report
    retail_paths = [SIM_DIR / f for f in RETAIL_FILES]
    airline_paths = [SIM_DIR / f for f in AIRLINE_FILES]

    retail = merge_results(retail_paths)
    airline = merge_results(airline_paths)

    retail_out = OUT_DIR / RETAIL_OUT
    airline_out = OUT_DIR / AIRLINE_OUT
    retail.save(retail_out)
    airline.save(airline_out)
    print(f"Saved merged retail to {retail_out} ({len(retail.simulations)} simulations)")
    print(f"Saved merged airline to {airline_out} ({len(airline.simulations)} simulations)\n")

    report("RETAIL", retail)
    report("AIRLINE", airline)


if __name__ == "__main__":
    main()
