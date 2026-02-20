"""
Gemini 3 Flash with reasoning/thinking — stream or non-stream.

Per LiteLLM Gemini 3 docs (https://docs.litellm.ai/blog/gemini_3):
- Use reasoning_effort ("low" | "medium" | "high") to control thinking level.
- Streaming: thought tokens in delta.reasoning_content.
- Non-streaming: thought text in message.reasoning_content.

Logfire: run with Logfire configured to see prompt, thinking, and response in the UI.

CLI: prompt (thinking input) is required; optional --reasoning-effort, --no-stream.
"""
import argparse
import os

import litellm
import logfire

# LiteLLM uses GOOGLE_API_KEY or GEMINI_API_KEY from the environment
if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
    raise SystemExit("Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment")

MODEL = "gemini/gemini-3-flash-preview"


def _log_thinking_to_span(
    span,
    thinking_buffer: str,
    response_buffer: str,
) -> None:
    """Set Logfire span attributes for thinking and response."""
    span.set_attribute("thinking_char_count", len(thinking_buffer))
    span.set_attribute("response_char_count", len(response_buffer))
    span.set_attribute("thinking", thinking_buffer or "(none)")
    span.set_attribute("response", response_buffer or "(none)")


def _log_raw_response_openinference(
    span,
    model_name: str,
    output_content: str,
    output_role: str = "assistant",
    usage: object | None = None,
) -> None:
    """Set Logfire span attributes in OpenInference / observability schema format."""
    span.set_attribute("llm.model_name", model_name)
    span.set_attribute("llm.output_messages.0.message.content", output_content or "")
    span.set_attribute("llm.output_messages.0.message.role", output_role)
    # Infer provider from model name (e.g. gemini/... -> google)
    provider = "google" if model_name.startswith("gemini/") else model_name.split("/")[0] if "/" in model_name else None
    if provider:
        span.set_attribute("llm.provider", provider)
    span.set_attribute("openinference.span.kind", "LLM")
    span.set_attribute("output.value", output_content or "")

    if usage is None:
        return
    # Token counts
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if prompt_tokens is not None:
        span.set_attribute("llm.token_count.prompt", int(prompt_tokens))
    if completion_tokens is not None:
        span.set_attribute("llm.token_count.completion", int(completion_tokens))
    if total_tokens is not None:
        span.set_attribute("llm.token_count.total", int(total_tokens))
    # Completion details (e.g. reasoning tokens)
    comp_details = getattr(usage, "completion_tokens_details", None)
    if comp_details is not None:
        reasoning = getattr(comp_details, "reasoning_tokens", None)
        if reasoning is not None:
            span.set_attribute("llm.token_count.completion_details.reasoning", int(reasoning))
    # Prompt details (e.g. cache)
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details is not None:
        details = (
            prompt_details.model_dump(mode="json")
            if hasattr(prompt_details, "model_dump")
            else dict(prompt_details)
            if hasattr(prompt_details, "keys")
            else {}
        )
        cache_input = details.get("cached_tokens") or details.get("cache_read") or details.get("cache_input")
        if cache_input is not None:
            span.set_attribute("llm.token_count.prompt_details.cache_input", int(cache_input))


def run_with_thinking(
    prompt: str,
    reasoning_effort: str = "high",
    stream: bool = True,
):
    """Call Gemini 3 Flash with reasoning; capture and display thought tokens.

    With stream=True, thought tokens come from delta.reasoning_content (and
    delta.thinking for other providers). With stream=False, they come from
    message.reasoning_content on the final response.
    """
    label = "Streaming" if stream else "Non-streaming"
    print(f"🤔 {label} response with reasoning/thinking tokens...\n")
    print("=" * 60)

    with logfire.span(
        "thinking_test",
        _span_name="Gemini 3 Flash thinking",
        prompt=prompt,
        reasoning_effort=reasoning_effort,
        stream=stream,
        model=MODEL,
    ) as span:
        response = litellm.completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort=reasoning_effort,
            stream=stream,
        )

        usage_for_log = None
        if stream:
            thinking_buffer = ""
            response_buffer = ""
            in_thinking = False
            last_chunk = None
            for chunk in response:
                last_chunk = chunk
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None) or getattr(
                    delta, "thinking", None
                )
                if reasoning:
                    if not in_thinking:
                        print("\n💭 [THINKING]")
                        print("-" * 40)
                        in_thinking = True
                    print(reasoning, end="", flush=True)
                    thinking_buffer += reasoning
                if delta.content:
                    if in_thinking:
                        print("\n" + "-" * 40)
                        print("\n✅ [RESPONSE]")
                        print("-" * 40)
                        in_thinking = False
                    print(delta.content, end="", flush=True)
                    response_buffer += delta.content
            if last_chunk is not None:
                usage_for_log = getattr(last_chunk, "usage", None)
        else:
            msg = response.choices[0].message
            thinking_buffer = getattr(msg, "reasoning_content", None) or ""
            if thinking_buffer is None:
                thinking_buffer = ""
            response_buffer = msg.content or ""
            usage_for_log = getattr(response, "usage", None)
            # Print in same format as streaming
            if thinking_buffer:
                print("\n💭 [THINKING]")
                print("-" * 40)
                print(thinking_buffer)
            if response_buffer:
                if thinking_buffer:
                    print("-" * 40)
                    print("\n✅ [RESPONSE]")
                    print("-" * 40)
                print(response_buffer)

        _log_thinking_to_span(span, thinking_buffer, response_buffer)
        _log_raw_response_openinference(
            span,
            model_name=MODEL,
            output_content=response_buffer,
            output_role="assistant",
            usage=usage_for_log,
        )

    print("\n" + "=" * 60)
    print(
        f"\n📊 Stats: {len(thinking_buffer)} thinking chars, {len(response_buffer)} response chars"
    )
    return thinking_buffer, response_buffer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Gemini 3 Flash with reasoning; prompt is the thinking input."
    )
    parser.add_argument(
        "prompt",
        type=str,
        nargs="*",
        help="The prompt (thinking input) to send to the model. Multiple words allowed. If omitted, read from stdin.",
    )
    parser.add_argument(
        "--reasoning-effort",
        type=str,
        choices=["low", "medium", "high", "minimal"],
        default="high",
        help="Reasoning effort / thinking level (default: high).",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Use non-streaming completion (stream=False).",
    )
    args = parser.parse_args()

    if args.prompt:
        prompt = " ".join(args.prompt).strip()
    else:
        import sys
        prompt = sys.stdin.read().strip() or None
    if not prompt:
        parser.error("Provide a prompt as argument or via stdin (e.g. echo 'Your question' | python thinking-test.py)")

    logfire.configure(scrubbing=False)
    logfire.instrument_litellm()

    run_with_thinking(
        prompt,
        reasoning_effort=args.reasoning_effort,
        stream=not args.no_stream,
    )