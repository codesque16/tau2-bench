"""Global tools for the user simulator (e.g. verify-before-stop)."""

from typing import Callable

from tau2.environment.tool import Tool, as_tool

# Tool names that are executed by the orchestrator from the user's tool list,
# not via environment.use_user_tool (they are not domain user tools).
GLOBAL_USER_SIM_TOOL_NAMES = {"check_for_stop"}


def check_for_stop() -> str:
    """Return a checklist to verify whether the conversation can be stopped.

    Call this tool when you think the task might be complete, before outputting
    ###STOP###. Use the checklist to confirm; only output ###STOP### if all
    checks pass.

    Returns:
        A checklist string for the LLM to verify before ending the conversation.
    """
    return """Verify the following before outputting ###STOP###:

1. GOAL SATISFIED: The scenario instruction goal is fully satisfied (the customer's request has been completed as specified in your scenario).

2. NO PENDING EXECUTION: The agent has no pending action to perform. If the agent said they would do something (e.g. cancel an order, process a return), wait until they have confirmed it is done or you have seen the outcome. Do not stop while the agent might still be about to execute something.

3. CORRECT TERMINATION TYPE: You are ending because the task is complete. If you are being transferred to a human, use ###TRANSFER### instead. If the scenario does not provide enough information to continue, use ###OUT-OF-SCOPE### instead.

Only if all checks pass, output ###STOP### in your next message. If any check fails, continue the conversation (e.g. thank the agent and wait, or ask for confirmation)."""


check_for_stop_tool: Tool = as_tool(check_for_stop)

GLOBAL_USER_SIM_TOOLS: list[Tool] = [check_for_stop_tool]

# Name -> callable for executing global user tools (e.g. when replaying in set_state).
GLOBAL_USER_SIM_TOOL_FUNCS: dict[str, Callable[..., str]] = {
    "check_for_stop": check_for_stop,
}
