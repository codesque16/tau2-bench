import json
import re
import time
from typing import Any, Literal, Optional

import litellm
import logfire
from litellm.caching.caching import Cache
from litellm.main import ModelResponse, Usage
from loguru import logger

# Application-level retries for 503/timeout (after LiteLLM's own retries are exhausted)
TRANSIENT_ERROR_MAX_RETRIES = 3
TRANSIENT_ERROR_BASE_DELAY = 5

from tau2.config import (
    DEFAULT_LLM_CACHE_TYPE,
    DEFAULT_LLM_REQUEST_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    LLM_CACHE_ENABLED,
    REDIS_CACHE_TTL,
    REDIS_CACHE_VERSION,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_PREFIX,
    USE_LANGFUSE,
)
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool
from tau2.utils.key_pool import key_pool_from_env, is_transient_error

# litellm._turn_on_debug()

if USE_LANGFUSE:
    # set callbacks
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

litellm.drop_params = True

if LLM_CACHE_ENABLED:
    if DEFAULT_LLM_CACHE_TYPE == "redis":
        logger.info(f"LiteLLM: Using Redis cache at {REDIS_HOST}:{REDIS_PORT}")
        litellm.cache = Cache(
            type=DEFAULT_LLM_CACHE_TYPE,
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            namespace=f"{REDIS_PREFIX}:{REDIS_CACHE_VERSION}:litellm",
            ttl=REDIS_CACHE_TTL,
        )
    elif DEFAULT_LLM_CACHE_TYPE == "local":
        logger.info("LiteLLM: Using local cache")
        litellm.cache = Cache(
            type="local",
            ttl=REDIS_CACHE_TTL,
        )
    else:
        raise ValueError(
            f"Invalid cache type: {DEFAULT_LLM_CACHE_TYPE}. Should be 'redis' or 'local'"
        )
    litellm.enable_cache()
else:
    logger.info("LiteLLM: Cache is disabled")
    litellm.disable_cache()


ALLOW_SONNET_THINKING = False

if not ALLOW_SONNET_THINKING:
    logger.warning("Sonnet thinking is disabled")


OPENAI_KEY_POOL = key_pool_from_env(
    primary_env="OPENAI_API_KEY",
    pool_envs=("OPENAI_API_KEYS",),
    cooldown_env="OPENAI_KEY_FAILOVER_COOLDOWN_S",
)
GEMINI_KEY_POOL = key_pool_from_env(
    primary_env="GOOGLE_API_KEY",
    fallback_primary_envs=("GEMINI_API_KEY",),
    pool_envs=("GOOGLE_API_KEYS", "GEMINI_API_KEYS"),
    cooldown_env="GEMINI_KEY_FAILOVER_COOLDOWN_S",
)


def _provider_for_model(model: str) -> str | None:
    m = (model or "").lower().strip()
    if not m:
        return None
    if m.startswith("openai/") or m.startswith("gpt-") or "openai" in m:
        return "openai"
    if m.startswith("gemini/") or m.startswith("gemini-") or "gemini" in m:
        return "gemini"
    return None


def _mask_key(api_key: str | None) -> str:
    if not api_key:
        return "none"
    if len(api_key) <= 8:
        return f"{api_key[:2]}***"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _short_id(s: str, max_len: int = 24) -> str:
    s = s or ""
    if not s:
        return "none"
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


def _sanitize_tool_call_id(tool_call_id: str | None, *, fallback: str) -> str:
    """Strip any model-injected suffixes (e.g. '__thought__...') from tool-call ids."""
    raw = (tool_call_id or "").strip()
    if not raw:
        return fallback
    if "__thought__" in raw:
        raw = raw.split("__thought__", 1)[0].strip()
    return raw or fallback


def _parse_ft_model_name(model: str) -> str:
    """
    Parse the ft model name from the litellm model name.
    e.g: "ft:gpt-4.1-mini-2025-04-14:sierra::BSQA2TFg" -> "gpt-4.1-mini-2025-04-14"
    """
    pattern = r"ft:(?P<model>[^:]+):(?P<provider>\w+)::(?P<id>\w+)"
    match = re.match(pattern, model)
    if match:
        return match.group("model")
    else:
        return model


def get_response_cost(response: ModelResponse) -> float:
    """
    Get the cost of the response from the litellm completion.
    """
    response.model = _parse_ft_model_name(
        response.model
    )  # FIXME: Check Litellm, passing the model to completion_cost doesn't work.
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception as e:
        logger.error(e)
        return 0.0
    return cost


def get_response_usage(response: ModelResponse) -> Optional[dict]:
    usage: Optional[Usage] = response.get("usage")
    if usage is None:
        return None
    out: dict[str, Any] = {
        "completion_tokens": usage.completion_tokens,
        "prompt_tokens": usage.prompt_tokens,
    }
    if getattr(usage, "total_tokens", None) is not None:
        out["total_tokens"] = usage.total_tokens
    # Cache-related fields when available (provider-specific keys: Gemini=cache_input, OpenAI=cache_read, LiteLLM=cached_tokens)
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details is not None:
        details = (
            prompt_details.model_dump(mode="json")
            if hasattr(prompt_details, "model_dump")
            else dict(prompt_details)
            if hasattr(prompt_details, "keys")
            else {k: getattr(prompt_details, k, None) for k in ("cached_tokens", "cache_read", "cache_input")}
        )
        # Drop None values so JSON only has present keys
        out["prompt_tokens_details"] = {k: v for k, v in details.items() if v is not None}
        cached = (
            details.get("cached_tokens")
            or details.get("cache_read")
            or details.get("cache_input")
        )
        if cached is not None:
            out["cache_read_tokens"] = int(cached)
    if getattr(usage, "cache_creation_input_tokens", None) is not None:
        out["cache_creation_input_tokens"] = usage.cache_creation_input_tokens
    elif usage.get("cache_creation_input_tokens") is not None:
        out["cache_creation_input_tokens"] = usage.get("cache_creation_input_tokens")
    # Reasoning/thinking token count (e.g. Gemini 3 completion_details.reasoning)
    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details is not None:
        reasoning_tokens = getattr(completion_details, "reasoning_tokens", None)
        if reasoning_tokens is not None:
            out["reasoning_tokens"] = int(reasoning_tokens)
        # Include full details in result JSON when present (matches llm.token_count.completion_details.*)
        if hasattr(completion_details, "model_dump"):
            details = completion_details.model_dump(mode="json")
        elif hasattr(completion_details, "keys"):
            details = dict(completion_details)
        else:
            details = {k: getattr(completion_details, k, None) for k in ("reasoning_tokens", "text_tokens", "image_tokens", "audio_tokens") if getattr(completion_details, k, None) is not None}
        if details:
            out["completion_tokens_details"] = {k: v for k, v in details.items() if v is not None}
            # Alias for OpenInference / observability schema (llm.token_count.completion_details.reasoning)
            if reasoning_tokens is not None and "reasoning" not in out["completion_tokens_details"]:
                out["completion_tokens_details"]["reasoning"] = int(reasoning_tokens)
    elif getattr(usage, "reasoning_tokens", None) is not None:
        out["reasoning_tokens"] = int(usage.reasoning_tokens)
    return out


def _set_usage_attrs_on_span(span: Any, usage: dict[str, Any] | None) -> None:
    """Attach token usage to span in both OpenInference and GenAI key formats."""
    if not usage:
        return

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")

    if prompt_tokens is not None:
        prompt_tokens = int(prompt_tokens)
        span.set_attribute("llm.token_count.prompt", prompt_tokens)
        span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
    if completion_tokens is not None:
        completion_tokens = int(completion_tokens)
        span.set_attribute("llm.token_count.completion", completion_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
    if total_tokens is not None:
        total_tokens = int(total_tokens)
        span.set_attribute("llm.token_count.total", total_tokens)
        span.set_attribute("gen_ai.usage.total_tokens", total_tokens)

    reasoning_tokens = usage.get("reasoning_tokens")
    completion_details = usage.get("completion_tokens_details") or {}
    reasoning_from_details = completion_details.get("reasoning")
    reasoning_from_details_alt = completion_details.get("reasoning_tokens")
    if reasoning_tokens is None:
        reasoning_tokens = (
            reasoning_from_details
            if reasoning_from_details is not None
            else reasoning_from_details_alt
        )
    if reasoning_tokens is not None:
        reasoning_tokens = int(reasoning_tokens)
        # OpenInference style
        span.set_attribute(
            "llm.token_count.completion_details.reasoning", reasoning_tokens
        )
        span.set_attribute(
            "llm.token_count.completion_details.reasoning_tokens", reasoning_tokens
        )
        # GenAI style (used by some UIs)
        span.set_attribute(
            "gen_ai.usage.output_tokens_details.reasoning", reasoning_tokens
        )


def to_tau2_messages(
    messages: list[dict], ignore_roles: set[str] = set()
) -> list[Message]:
    """
    Convert a list of messages from a dictionary to a list of Tau2 messages.
    """
    tau2_messages = []
    for message in messages:
        role = message["role"]
        if role in ignore_roles:
            continue
        if role == "user":
            tau2_messages.append(UserMessage(**message))
        elif role == "assistant":
            tau2_messages.append(AssistantMessage(**message))
        elif role == "tool":
            tau2_messages.append(ToolMessage(**message))
        elif role == "system":
            tau2_messages.append(SystemMessage(**message))
        else:
            raise ValueError(f"Unknown message type: {role}")
    return tau2_messages


def to_litellm_messages(messages: list[Message]) -> list[dict]:
    """
    Convert a list of Tau2 messages to a list of litellm messages.
    """
    litellm_messages = []
    for message in messages:
        if isinstance(message, UserMessage):
            litellm_messages.append({"role": "user", "content": message.content})
        elif isinstance(message, AssistantMessage):
            tool_calls = None
            if message.is_tool_call():
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                        "type": "function",
                    }
                    for tc in message.tool_calls
                ]
            litellm_messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": tool_calls,
                }
            )
        elif isinstance(message, ToolMessage):
            litellm_messages.append(
                {
                    "role": "tool",
                    "content": message.content,
                    "tool_call_id": message.id,
                }
            )
        elif isinstance(message, SystemMessage):
            litellm_messages.append({"role": "system", "content": message.content})
    return litellm_messages


def generate(
    model: str,
    messages: list[Message],
    tools: Optional[list[Tool]] = None,
    tool_choice: Optional[str] = None,
    *,
    caller: Optional[Literal["agent", "user", "evaluator"]] = None,
    **kwargs: Any,
) -> UserMessage | AssistantMessage:
    """
    Generate a response from the model.

    Args:
        model: The model to use.
        messages: The messages to send to the model.
        tools: The tools to use.
        tool_choice: The tool choice to use.
        caller: Optional label for tracing (e.g. "agent", "user"). Creates a parent
            span in Logfire so completion spans appear under "agent" or "user".
        **kwargs: Additional arguments to pass to the model.

    Returns: A tuple containing the message and the cost.
    """
    if kwargs.get("num_retries") is None:
        kwargs["num_retries"] = DEFAULT_MAX_RETRIES
    timeout = kwargs.get("timeout")
    if timeout is None or not isinstance(timeout, (int, float)) or timeout <= 0:
        kwargs["timeout"] = DEFAULT_LLM_REQUEST_TIMEOUT

    if model.startswith("claude") and not ALLOW_SONNET_THINKING:
        kwargs["thinking"] = {"type": "disabled"}
    litellm_messages = to_litellm_messages(messages)
    tools = [tool.openai_schema for tool in tools] if tools else None
    if tools and tool_choice is None:
        tool_choice = "auto"

    provider = _provider_for_model(model)
    key_pool = OPENAI_KEY_POOL if provider == "openai" else GEMINI_KEY_POOL if provider == "gemini" else None

    def _do_completion(api_key: str | None = None):
        call_kwargs = dict(kwargs)
        if api_key:
            # Pass key per call so we can rotate keys without mutating global env.
            call_kwargs["api_key"] = api_key
        return litellm.completion(
            model=model,
            messages=litellm_messages,
            tools=tools,
            tool_choice=tool_choice,
            **call_kwargs,
        )

    for attempt in range(TRANSIENT_ERROR_MAX_RETRIES + 1):
        api_key = key_pool.choose() if key_pool is not None else None
        if caller:
            with logfire.span(caller) as caller_span:
                caller_span.set_attribute("llm.provider", provider)
                caller_span.set_attribute("llm.retry_attempt", attempt + 1)
                caller_span.set_attribute("llm.key_masked", _mask_key(api_key))
                logfire.info(
                    "llm.key_attempt",
                    caller=caller,
                    provider=provider or "unknown",
                    model=model,
                    attempt=attempt + 1,
                    max_attempts=TRANSIENT_ERROR_MAX_RETRIES + 1,
                    key_masked=_mask_key(api_key),
                )
                try:
                    response = _do_completion(api_key=api_key)
                    logfire.info(
                        "llm.key_success",
                        caller=caller,
                        provider=provider or "unknown",
                        model=model,
                        attempt=attempt + 1,
                        max_attempts=TRANSIENT_ERROR_MAX_RETRIES + 1,
                        key_masked=_mask_key(api_key),
                    )
                    usage = get_response_usage(response)
                    _set_usage_attrs_on_span(caller_span, usage)
                    if response.choices:
                        msg = response.choices[0].message
                        reasoning = getattr(msg, "reasoning_content", None)
                        if reasoning:
                            caller_span.set_attribute("reasoning_content", reasoning)
                            caller_span.set_attribute(
                                "reasoning_content_length", len(reasoning)
                            )
                    break
                except Exception as e:
                    transient = is_transient_error(e)
                    if transient and key_pool is not None and api_key:
                        key_pool.mark_unhealthy(api_key)
                    if transient and attempt < TRANSIENT_ERROR_MAX_RETRIES:
                        delay = TRANSIENT_ERROR_BASE_DELAY * (2**attempt)
                        log_payload = {
                            "caller": caller or "unknown",
                            "provider": provider or "unknown",
                            "model": model,
                            "attempt": attempt + 1,
                            "max_attempts": TRANSIENT_ERROR_MAX_RETRIES + 1,
                            "delay_seconds": delay,
                            "key_masked": _mask_key(api_key),
                            "error_type": type(e).__name__,
                            "error": str(e),
                        }
                        logger.warning(
                            "Transient API error (%s), retrying in %.0fs (attempt %d/%d): %s",
                            type(e).__name__,
                            delay,
                            attempt + 1,
                            TRANSIENT_ERROR_MAX_RETRIES,
                            e,
                        )
                        # Emitted within this caller span, so traces stay correctly nested.
                        logfire.info("llm.key_failover_retry", **log_payload)
                        time.sleep(delay)
                        continue
                    logger.error(e)
                    raise
        else:
            try:
                logfire.info(
                    "llm.key_attempt",
                    caller="unknown",
                    provider=provider or "unknown",
                    model=model,
                    attempt=attempt + 1,
                    max_attempts=TRANSIENT_ERROR_MAX_RETRIES + 1,
                    key_masked=_mask_key(api_key),
                )
                response = _do_completion(api_key=api_key)
                logfire.info(
                    "llm.key_success",
                    caller="unknown",
                    provider=provider or "unknown",
                    model=model,
                    attempt=attempt + 1,
                    max_attempts=TRANSIENT_ERROR_MAX_RETRIES + 1,
                    key_masked=_mask_key(api_key),
                )
                break
            except Exception as e:
                transient = is_transient_error(e)
                if transient and key_pool is not None and api_key:
                    key_pool.mark_unhealthy(api_key)
                if transient and attempt < TRANSIENT_ERROR_MAX_RETRIES:
                    delay = TRANSIENT_ERROR_BASE_DELAY * (2**attempt)
                    log_payload = {
                        "caller": "unknown",
                        "provider": provider or "unknown",
                        "model": model,
                        "attempt": attempt + 1,
                        "max_attempts": TRANSIENT_ERROR_MAX_RETRIES + 1,
                        "delay_seconds": delay,
                        "key_masked": _mask_key(api_key),
                        "error_type": type(e).__name__,
                        "error": str(e),
                    }
                    logger.warning(
                        "Transient API error (%s), retrying in %.0fs (attempt %d/%d): %s",
                        type(e).__name__,
                        delay,
                        attempt + 1,
                        TRANSIENT_ERROR_MAX_RETRIES,
                        e,
                    )
                    logfire.info("llm.key_failover_retry", **log_payload)
                    time.sleep(delay)
                    continue
                logger.error(e)
                raise
    cost = get_response_cost(response)
    usage = get_response_usage(response)
    response = response.choices[0]
    try:
        finish_reason = response.finish_reason
        if finish_reason == "length":
            logger.warning("Output might be incomplete due to token limit!")
    except Exception as e:
        logger.error(e)
        raise e
    assert response.message.role == "assistant", (
        "The response should be an assistant message"
    )
    content = response.message.content
    raw_tool_calls = response.message.tool_calls or []
    tool_calls: list[ToolCall] = []
    for idx, tool_call in enumerate(raw_tool_calls):
        raw_id = getattr(tool_call, "id", None)
        sanitized_id = _sanitize_tool_call_id(raw_id, fallback=f"call_{idx}")
        if sanitized_id != (raw_id or ""):
            # IDs can include injected reasoning blobs; keep logs short.
            logfire.info(
                "llm.tool_call_id_truncated",
                provider=provider or "unknown",
                model=model,
                raw_id_short=_short_id(str(raw_id or "")),
                sanitized_id=sanitized_id,
            )
        tool_calls.append(
            ToolCall(
                id=sanitized_id,
                name=tool_call.function.name,
                arguments=json.loads(tool_call.function.arguments),
            )
        )
    tool_calls = tool_calls or None

    # AssistantMessage must have either content or tool_calls; normalize empty model responses
    has_text = content is not None and (
        not isinstance(content, str) or content.strip() != ""
    )
    if not has_text and not tool_calls:
        logger.warning(
            "Model returned empty response (no content, no tool calls); using placeholder"
        )
        content = "(No response from model)"

    message = AssistantMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        cost=cost,
        usage=usage,
        raw_data=response.to_dict(),
    )
    return message


def get_cost(messages: list[Message]) -> tuple[float, float] | None:
    """
    Get the cost of the interaction between the agent and the user.
    Returns None if any message has no cost.
    """
    agent_cost = 0
    user_cost = 0
    for message in messages:
        if isinstance(message, ToolMessage):
            continue
        if message.cost is not None:
            if isinstance(message, AssistantMessage):
                agent_cost += message.cost
            elif isinstance(message, UserMessage):
                user_cost += message.cost
        else:
            logger.warning(f"Message {message.role}: {message.content} has no cost")
            return None
    return agent_cost, user_cost


def get_token_usage(messages: list[Message]) -> dict:
    """
    Get the token usage of the interaction between the agent and the user.
    Includes cache_read_tokens, cache_creation_input_tokens, and reasoning_tokens when present in message usage.
    """
    usage: dict[str, Any] = {"completion_tokens": 0, "prompt_tokens": 0}
    cache_read = 0
    cache_creation = 0
    reasoning_tokens = 0
    for message in messages:
        if isinstance(message, ToolMessage):
            continue
        if message.usage is None:
            logger.warning(f"Message {message.role}: {message.content} has no usage")
            continue
        usage["completion_tokens"] += message.usage.get("completion_tokens", 0)
        usage["prompt_tokens"] += message.usage.get("prompt_tokens", 0)
        cache_read += message.usage.get("cache_read_tokens", 0)
        cache_creation += message.usage.get("cache_creation_input_tokens", 0)
        reasoning_tokens += message.usage.get("reasoning_tokens", 0)
    if cache_read:
        usage["cache_read_tokens"] = cache_read
    if cache_creation:
        usage["cache_creation_input_tokens"] = cache_creation
    if reasoning_tokens:
        usage["reasoning_tokens"] = reasoning_tokens
    return usage



def _mcp_tools_to_openai_format(tools_response: Any) -> list[dict[str, Any]]:
    """Convert MCP ListToolsResult to OpenAI-style tool list; strip hidden params."""
    _HIDDEN_PARAMS = {"session_id", "ctx"}
    out = []
    for tool in getattr(tools_response, "tools", []) or []:
        name = getattr(tool, "name", "") or ""
        description = getattr(tool, "description", None) or ""
        input_schema = getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
        if isinstance(input_schema, dict):
            props = input_schema.get("properties") or {}
            required = input_schema.get("required") or []
            input_schema = {
                **input_schema,
                "properties": {k: v for k, v in props.items() if k not in _HIDDEN_PARAMS},
                "required": [r for r in required if r not in _HIDDEN_PARAMS],
            }
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": input_schema,
            },
        })
    return out


class _MCPToolSchema:
    """Minimal tool-like object for MCP tools; only openai_schema is used by generate()."""

    def __init__(self, schema: dict):
        self.name = schema["function"]["name"]
        self.openai_schema = schema


def _format_mcp_call_tool_result(result: Any) -> str:
    """Format MCP CallToolResult as string (content text or JSON)."""
    if getattr(result, "isError", False):
        content = getattr(result, "content", []) or []
        parts = [c.text for c in content if hasattr(c, "text")]
        return json.dumps({"error": " ".join(parts) or "Unknown error"})
    out = []
    for c in getattr(result, "content", []) or []:
        if hasattr(c, "text"):
            out.append(c.text)
    if hasattr(result, "structuredContent") and result.structuredContent:
        return json.dumps(result.structuredContent)
    return "\n".join(out) if out else "{}"