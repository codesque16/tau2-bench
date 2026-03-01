import asyncio
import json
import queue
import sys
import threading
from copy import deepcopy
from typing import Callable, List, Optional

from loguru import logger
from pydantic import BaseModel

from tau2.agent.base import (
    LocalAgent,
    ValidAgentInputMessage,
    is_valid_agent_history_message,
)
from tau2.data_model.message import (
    APICompatibleMessage,
    AssistantMessage,
    Message,
    MultiToolMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from tau2.data_model.tasks import Action, Task
from tau2.environment.tool import Tool, as_tool
from tau2.utils.llm_utils import (
    generate,
    _format_mcp_call_tool_result,
    _mcp_tools_to_openai_format,
    _MCPToolSchema,
)

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

AGENT_INSTRUCTION = """
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy.
""".strip()

SYSTEM_PROMPT = """
<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>
""".strip()

# Mermaid agent: policy only, no extra instructions
SYSTEM_PROMPT_MERMAID = "{domain_policy}"


class LLMAgentState(BaseModel):
    """The state of the agent."""

    system_messages: list[SystemMessage]
    messages: list[APICompatibleMessage]


class LLMAgent(LocalAgent[LLMAgentState]):
    """
    An LLM agent that can be used to solve a task.
    """

    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        llm: Optional[str] = None,
        llm_args: Optional[dict] = None,
    ):
        """
        Initialize the LLMAgent.
        """
        super().__init__(tools=tools, domain_policy=domain_policy)
        self.llm = llm
        self.llm_args = deepcopy(llm_args) if llm_args is not None else {}

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(
            domain_policy=self.domain_policy, agent_instruction=AGENT_INSTRUCTION
        )

    def get_init_state(
        self, message_history: Optional[list[Message]] = None
    ) -> LLMAgentState:
        """Get the initial state of the agent.

        Args:
            message_history: The message history of the conversation.

        Returns:
            The initial state of the agent.
        """
        if message_history is None:
            message_history = []
        assert all(is_valid_agent_history_message(m) for m in message_history), (
            "Message history must contain only AssistantMessage, UserMessage, or ToolMessage to Agent."
        )
        return LLMAgentState(
            system_messages=[SystemMessage(role="system", content=self.system_prompt)],
            messages=message_history,
        )

    def generate_next_message(
        self,
        message: ValidAgentInputMessage,
        state: LLMAgentState,
        trajectory_sink: Optional[Callable[[Message], None]] = None,
    ) -> tuple[AssistantMessage, LLMAgentState]:
        """
        Respond to a user or tool message.
        """
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)
        messages = state.system_messages + state.messages
        assistant_message = generate(
            model=self.llm,
            tools=self.tools,
            messages=messages,
            caller="agent",
            **self.llm_args,
        )
        state.messages.append(assistant_message)
        return assistant_message, state

    def set_seed(self, seed: int):
        """Set the seed for the LLM."""
        if self.llm is None:
            raise ValueError("LLM is not set")
        cur_seed = self.llm_args.get("seed", None)
        if cur_seed is not None:
            logger.warning(f"Seed is already set to {cur_seed}, resetting it to {seed}")
        self.llm_args["seed"] = seed


AGENT_GT_INSTRUCTION = """
You are testing that our user simulator is working correctly.
User simulator will have an issue for you to solve.
You must behave according to the <policy> provided below.
To make following the policy easier, we give you the list of resolution steps you are expected to take.
These steps involve either taking an action or asking the user to take an action.

In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy.
""".strip()

SYSTEM_PROMPT_GT = """
<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>
<resolution_steps>
{resolution_steps}
</resolution_steps>
""".strip()


class LLMGTAgent(LocalAgent[LLMAgentState]):
    """
    An GroundTruth agent that can be used to solve a task.
    This agent will receive the expected actions.
    """

    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        task: Task,
        llm: Optional[str] = None,
        llm_args: Optional[dict] = None,
        provide_function_args: bool = True,
    ):
        """
        Initialize the LLMAgent.
        If provide_function_args is True, the resolution steps will include the function arguments.
        """
        super().__init__(tools=tools, domain_policy=domain_policy)
        assert self.check_valid_task(task), (
            f"Task {task.id} is not valid. Cannot run GT agent."
        )
        self.task = task
        self.llm = llm
        self.llm_args = deepcopy(llm_args) if llm_args is not None else {}
        self.provide_function_args = provide_function_args

    @classmethod
    def check_valid_task(cls, task: Task) -> bool:
        """
        Check if the task is valid.
        Only the tasks that require at least one action are valid.
        """
        if task.evaluation_criteria is None:
            return False
        expected_actions = task.evaluation_criteria.actions or []
        if len(expected_actions) == 0:
            return False
        return True

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT_GT.format(
            agent_instruction=AGENT_GT_INSTRUCTION,
            domain_policy=self.domain_policy,
            resolution_steps=self.make_agent_instructions_from_actions(),
        )

    def get_init_state(
        self, message_history: Optional[list[Message]] = None
    ) -> LLMAgentState:
        """Get the initial state of the agent.

        Args:
            message_history: The message history of the conversation.

        Returns:
            The initial state of the agent.
        """
        if message_history is None:
            message_history = []
        assert all(is_valid_agent_history_message(m) for m in message_history), (
            "Message history must contain only AssistantMessage, UserMessage, or ToolMessage to Agent."
        )
        return LLMAgentState(
            system_messages=[SystemMessage(role="system", content=self.system_prompt)],
            messages=message_history,
        )

    def generate_next_message(
        self,
        message: ValidAgentInputMessage,
        state: LLMAgentState,
        trajectory_sink: Optional[Callable[[Message], None]] = None,
    ) -> tuple[AssistantMessage, LLMAgentState]:
        """
        Respond to a user or tool message.
        """
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)
        messages = state.system_messages + state.messages
        assistant_message = generate(
            model=self.llm,
            tools=self.tools,
            messages=messages,
            caller="agent",
            **self.llm_args,
        )
        state.messages.append(assistant_message)
        return assistant_message, state

    def set_seed(self, seed: int):
        """Set the seed for the LLM."""
        if self.llm is None:
            raise ValueError("LLM is not set")
        cur_seed = self.llm_args.get("seed", None)
        if cur_seed is not None:
            logger.warning(f"Seed is already set to {cur_seed}, resetting it to {seed}")
        self.llm_args["seed"] = seed

    def make_agent_instructions_from_actions(self) -> str:
        """
        Make agent instructions from a list of actions
        """
        lines = []
        for i, action in enumerate(self.task.evaluation_criteria.actions):
            lines.append(
                f"[Step {i + 1}] {self.make_agent_instructions_from_action(action=action, include_function_args=self.provide_function_args)}"
            )
        return "\n".join(lines)

    @classmethod
    def make_agent_instructions_from_action(
        cls, action: Action, include_function_args: bool = False
    ) -> str:
        """
        Make agent instructions from an action.
        If the action is a user action, returns instructions for the agent to give to the user.
        If the action is an agent action, returns instructions for the agent to perform the action.
        """
        if action.requestor == "user":
            if include_function_args:
                return f"Instruct the user to perform the following action: {action.get_func_format()}."
            else:
                return f"User action: {action.name}."
        elif action.requestor == "assistant":
            if include_function_args:
                return f"Perform the following action: {action.get_func_format()}."
            else:
                return f"Assistant action: {action.name}."
        else:
            raise ValueError(f"Unknown action requestor: {action.requestor}")


AGENT_SOLO_INSTRUCTION = """
You are a customer service agent that helps the user according to the <policy> provided below.
You will be provided with a ticket that contains the user's request.
You will need to plan and call the appropriate tools to solve the ticket.

You cannot communicate with the user, only make tool calls.
Stop when you consider that you have solved the ticket.
To do so, send a message containing a single tool call to the `{stop_function_name}` tool. Do not include any other tool calls in this last message.

Always follow the policy.
""".strip()

SYSTEM_PROMPT_SOLO = """
<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>
<ticket>
{ticket}
</ticket>
""".strip()


class LLMSoloAgent(LocalAgent[LLMAgentState]):
    """
    An LLM agent that can be used to solve a task without any interaction with the customer.
    The task need to specify a ticket format.
    """

    STOP_FUNCTION_NAME = "done"
    TRANSFER_TOOL_NAME = "transfer_to_human_agents"
    STOP_TOKEN = "###STOP###"

    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        task: Task,
        llm: Optional[str] = None,
        llm_args: Optional[dict] = None,
    ):
        """
        Initialize the LLMAgent.
        """
        super().__init__(tools=tools, domain_policy=domain_policy)
        assert self.check_valid_task(task), (
            f"Task {task.id} is not valid. Cannot run GT agent."
        )
        self.task = task
        self.llm = llm
        self.llm_args = llm_args if llm_args is not None else {}
        self.add_stop_tool()
        self.validate_tools()

    def add_stop_tool(self) -> None:
        """Add the stop tool to the tools."""

        def done() -> str:
            """Call this function when you are done with the task."""
            return self.STOP_TOKEN

        self.tools.append(as_tool(done))

    def validate_tools(self) -> None:
        """Check if the tools are valid."""
        tool_names = {tool.name for tool in self.tools}
        if self.TRANSFER_TOOL_NAME not in tool_names:
            logger.warning(
                f"Tool {self.TRANSFER_TOOL_NAME} not found in tools. This tool is required for the agent to transfer the user to a human agent."
            )
        if self.STOP_FUNCTION_NAME not in tool_names:
            raise ValueError(f"Tool {self.STOP_FUNCTION_NAME} not found in tools.")

    @classmethod
    def check_valid_task(cls, task: Task) -> bool:
        """
        Check if the task is valid.
        Task should contain a ticket and evaluation criteria.
        If the task contains an initial state, the message history should only contain tool calls and responses.
        """
        if task.initial_state is not None:
            message_history = task.initial_state.message_history or []
            for message in message_history:
                if isinstance(message, UserMessage):
                    return False
                if isinstance(message, AssistantMessage) and not message.is_tool_call():
                    return False
            return True
        if task.ticket is None:
            return False
        if task.evaluation_criteria is None:
            return False
        expected_actions = task.evaluation_criteria.actions or []
        if len(expected_actions) == 0:
            return False
        return True

    @property
    def system_prompt(self) -> str:
        agent_instruction = AGENT_SOLO_INSTRUCTION.format(
            stop_function_name=self.STOP_FUNCTION_NAME,
            stop_token=self.STOP_TOKEN,
        )
        return SYSTEM_PROMPT_SOLO.format(
            agent_instruction=agent_instruction,
            domain_policy=self.domain_policy,
            ticket=self.task.ticket,
        )

    def _check_if_stop_toolcall(self, message: AssistantMessage) -> AssistantMessage:
        """Check if the message is a stop message.
        If the message contains a tool call with the name STOP_FUNCTION_NAME, then the message is a stop message.
        """
        is_stop = False
        for tool_call in message.tool_calls:
            if tool_call.name == self.STOP_FUNCTION_NAME:
                is_stop = True
                break
        if is_stop:
            message.content = self.STOP_TOKEN
            message.tool_calls = None
        return message

    @classmethod
    def is_stop(cls, message: AssistantMessage) -> bool:
        """Check if the message is a stop message."""
        if message.content is None:
            return False
        return cls.STOP_TOKEN in message.content

    def get_init_state(
        self, message_history: Optional[list[Message]] = None
    ) -> LLMAgentState:
        """Get the initial state of the agent.

        Args:
            message_history: The message history of the conversation.

        Returns:
            The initial state of the agent.
        """
        if message_history is None:
            message_history = []
        assert all(is_valid_agent_history_message(m) for m in message_history), (
            "Message history must contain only AssistantMessage, UserMessage, or ToolMessage to Agent."
        )
        return LLMAgentState(
            system_messages=[SystemMessage(role="system", content=self.system_prompt)],
            messages=message_history,
        )

    def generate_next_message(
        self,
        message: Optional[ValidAgentInputMessage],
        state: LLMAgentState,
        trajectory_sink: Optional[Callable[[Message], None]] = None,
    ) -> tuple[AssistantMessage, LLMAgentState]:
        """
        Respond to a user or tool message.
        """
        if isinstance(message, UserMessage):
            raise ValueError("LLMSoloAgent does not support user messages.")
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        elif message is None:
            assert len(state.messages) == 0, "Message history should be empty"
        else:
            state.messages.append(message)
        messages = state.system_messages + state.messages
        assistant_message = generate(
            model=self.llm,
            tools=self.tools,
            messages=messages,
            tool_choice="required",
            caller="agent",
            **self.llm_args,
        )
        if not assistant_message.is_tool_call():
            raise ValueError("LLMSoloAgent only supports tool calls.")
        message = self._check_if_stop_toolcall(assistant_message)
        state.messages.append(assistant_message)
        return assistant_message, state

    def set_seed(self, seed: int):
        """Set the seed for the LLM."""
        if self.llm is None:
            raise ValueError("LLM is not set")
        cur_seed = self.llm_args.get("seed", None)
        if cur_seed is not None:
            logger.warning(f"Seed is already set to {cur_seed}, resetting it to {seed}")
        self.llm_args["seed"] = seed


class LLMMermaidAgent(LLMAgent):
    """
    LLM agent that adds MCP SOP tools (e.g. goto_node, todo) and runs them via the MCP server.

    Follows the same MCP initializing and calling patterns as agent/agent_mermaid/agent.py:
    streamable_http_client(url), ClientSession, initialize(), load_graph(sop_file), list_tools();
    tool schemas from _mcp_tools_to_openai_format (stripping session_id/ctx); load_graph excluded
    from tools exposed to the LLM; tool results formatted via _format_mcp_call_tool_result.
    We call list_tools() before load_graph() to avoid ClosedResourceError when the server
    returns 202 for load_graph. Assumes the MCP server is already running.
    """

    def __init__(
        self,
        tools: List[Tool],
        domain_policy: str,
        llm: Optional[str] = None,
        llm_args: Optional[dict] = None,
        mcp_server_url: str = "",
        sop_file: str = "retail",
    ):
        super().__init__(tools=tools, domain_policy=domain_policy, llm=llm, llm_args=llm_args)
        self._mcp_server_url = (mcp_server_url or "").strip() or None
        self._sop_file = sop_file or "retail"
        self._mcp_tool_names: set[str] = set()
        self._mcp_call_sync: Optional[callable] = None  # (name, arguments) -> str
        self._mermaid_system_prompt: Optional[str] = None  # set from load_graph result when MCP is used

        # Unconditional print so we see something even when log_level=ERROR filters everything else
        print(f"[LLMMermaidAgent] init mcp_server_url={mcp_server_url!r} will_init_mcp={bool(self._mcp_server_url)}", file=sys.stderr, flush=True)
        # Use error level so logs appear when default log_level is ERROR (WARNING is filtered out)
        logger.error(
            "LLMMermaidAgent: mcp_server_url={!r} (will init MCP: {})",
            mcp_server_url,
            bool(self._mcp_server_url),
        )
        if self._mcp_server_url:
            self._init_mcp_and_tools()

    @property
    def system_prompt(self) -> str:
        if self._mermaid_system_prompt is not None and (s := self._mermaid_system_prompt.strip()):
            return s
        return SYSTEM_PROMPT_MERMAID.format(domain_policy=self.domain_policy)

    def _init_mcp_and_tools(self) -> None:
        """Connect to MCP and set up SOP tools, following agent_mermaid MCP patterns.

        Matches agent/agent_mermaid/agent.py: streamable_http_client(url), ClientSession,
        session.initialize(), load_graph(sop_file), list_tools(); then expose tools (excluding
        load_graph) and run tool calls via the session. We call list_tools() before load_graph()
        so the tool list is received over normal request/response; if load_graph returns 202 the
        response is delivered via the GET stream and the transport may close afterward, which
        would make a subsequent list_tools() raise ClosedResourceError.
        """
        url = self._mcp_server_url.rstrip("/") + "/mcp" if "/mcp" not in self._mcp_server_url else self._mcp_server_url
        logger.error("LLMMermaidAgent: _init_mcp_and_tools started sop_file={!r} url={!r}", self._sop_file, url)
        init_queue: queue.Queue = queue.Queue()
        request_queue: queue.Queue = queue.Queue()
        result_queue: queue.Queue = queue.Queue()

        async def _mcp_worker_async() -> None:
            try:
                logger.error("LLMMermaidAgent: connecting to MCP url={!r}", url)
                async with streamable_http_client(url) as (read_stream, write_stream, _):
                    logger.error("LLMMermaidAgent: streamable_http_client connected")
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        logger.error("LLMMermaidAgent: session.initialize() done")
                        # Call list_tools before load_graph so we get the tool list over normal
                        # request/response. load_graph often returns 202 and the response is delivered
                        # via the GET stream; when that stream ends the transport can close and
                        # list_tools would then raise ClosedResourceError.
                        tools_response = await session.list_tools()
                        num_tools = len(getattr(tools_response, "tools", []) or [])
                        logger.error(
                            "LLMMermaidAgent: list_tools() returned {} tools",
                            num_tools,
                        )
                        mcp_schemas = _mcp_tools_to_openai_format(tools_response)
                        mcp_names = [s.get("function", {}).get("name") for s in mcp_schemas]
                        logger.error(
                            "LLMMermaidAgent: converted to {} OpenAI schemas names={}",
                            len(mcp_schemas),
                            mcp_names,
                        )
                        load_result = await session.call_tool(
                            "load_graph",
                            arguments={"sop_file": self._sop_file},
                        )
                        logger.error(
                            "LLMMermaidAgent: load_graph(sop_file={!r}) done isError={}",
                            self._sop_file,
                            getattr(load_result, "isError", False),
                        )
                        if getattr(load_result, "isError", False):
                            content = getattr(load_result, "content", []) or []
                            err_text = content[0].text if content else str(load_result)
                            init_queue.put(("error", RuntimeError(f"load_graph failed: {err_text}")))
                            return
                        # Extract system_prompt from load_graph result (AGENTS.md minus frontmatter minus Node Prompts)
                        load_content = getattr(load_result, "content", []) or []
                        load_text = (load_content[0].text if load_content and hasattr(load_content[0], "text") else None) or ""
                        try:
                            load_data = json.loads(load_text) if load_text.strip().startswith("{") else {}
                        except json.JSONDecodeError:
                            load_data = {}
                        mermaid_system_prompt = load_data.get("system_prompt")
                        mcp_schemas = [
                            s for s in mcp_schemas
                            if (s.get("function") or {}).get("name") != "load_graph"
                        ]
                        mcp_tool_names = {s["function"]["name"] for s in mcp_schemas}
                        logger.error(
                            "LLMMermaidAgent: after filter load_graph {} tools names={}",
                            len(mcp_schemas),
                            sorted(mcp_tool_names),
                        )
                        if len(mcp_schemas) == 0:
                            logger.warning(
                                "LLMMermaidAgent: no MCP tools after filtering load_graph; server may only expose load_graph"
                            )
                        init_queue.put(("ok", (mcp_schemas, mcp_tool_names, mermaid_system_prompt)))
                        logger.error("LLMMermaidAgent: put (ok) on init_queue; entering tool-call loop")
                        while True:
                            item = request_queue.get()
                            if item is None:
                                break
                            name, arguments = item
                            try:
                                result = await session.call_tool(name, arguments=arguments)
                                result_queue.put(_format_mcp_call_tool_result(result))
                            except Exception as e:
                                result_queue.put(json.dumps({"error": str(e)}))
            except Exception as e:
                logger.exception("LLMMermaidAgent: MCP worker failed before putting result")
                init_queue.put(("error", e))

        def run_worker() -> None:
            asyncio.run(_mcp_worker_async())

        thread = threading.Thread(target=run_worker, daemon=True)
        thread.start()
        kind, payload = init_queue.get()
        logger.error("LLMMermaidAgent: init_queue.get() -> kind={!r}", kind)
        if kind == "error":
            raise payload
        mcp_schemas, mcp_tool_names, mermaid_system_prompt = payload[0], payload[1], (payload[2] if len(payload) > 2 else None)
        self._mermaid_system_prompt = mermaid_system_prompt
        domain_tool_count = len(self.tools)
        self.tools = list(self.tools) + [_MCPToolSchema(s) for s in mcp_schemas]
        self._mcp_tool_names = mcp_tool_names
        logger.error(
            "LLMMermaidAgent: added {} MCP tools (domain={} total={}) MCP_names={}",
            len(mcp_schemas),
            domain_tool_count,
            len(self.tools),
            sorted(self._mcp_tool_names),
        )
        print(
            f"[LLMMermaidAgent] tools: domain={domain_tool_count} mcp={len(mcp_schemas)} total={len(self.tools)} names={sorted(self._mcp_tool_names)}",
            file=sys.stderr,
            flush=True,
        )

        def _call_sync(name: str, arguments: dict) -> str:
            request_queue.put((name, arguments))
            return result_queue.get()

        self._mcp_call_sync = _call_sync

    def _call_mcp_sync(self, name: str, arguments: dict) -> str:
        """Call MCP tool and return result as string (content text or JSON)."""
        if self._mcp_call_sync is None:
            return json.dumps({"error": "MCP not initialized"})
        return self._mcp_call_sync(name, arguments)

    def generate_next_message(
        self,
        message: ValidAgentInputMessage,
        state: LLMAgentState,
        trajectory_sink: Optional[Callable[[Message], None]] = None,
    ) -> tuple[AssistantMessage, LLMAgentState]:
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)
        messages = state.system_messages + state.messages

        while True:
            assistant_message = generate(
                model=self.llm,
                tools=self.tools,
                messages=messages,
                caller="agent",
                **self.llm_args,
            )
            state.messages.append(assistant_message)

            if not assistant_message.is_tool_call():
                return assistant_message, state
            mcp_only = all(t.name in self._mcp_tool_names for t in assistant_message.tool_calls)
            if not mcp_only:
                return assistant_message, state

            if trajectory_sink is not None:
                trajectory_sink(assistant_message)
            for tc in assistant_message.tool_calls:
                result = self._call_mcp_sync(tc.name, tc.arguments)
                tool_msg = ToolMessage(
                    id=tc.id,
                    content=result,
                    requestor="assistant",
                    role="tool",
                )
                state.messages.append(tool_msg)
                if trajectory_sink is not None:
                    trajectory_sink(tool_msg)
            messages = state.system_messages + state.messages