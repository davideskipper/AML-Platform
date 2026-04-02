"""Shared utilities: agent runner, formatting helpers."""

import anthropic


_WIDTH = 65


def print_section(header: str) -> None:
    print(f"\n{'━' * _WIDTH}")
    print(f"  {header}")
    print(f"{'━' * _WIDTH}")


def print_divider() -> None:
    print(f"{'─' * _WIDTH}")


def run_agent(
    client: anthropic.Anthropic,
    system_prompt: str,
    user_message: str,
    header: str = "",
    max_tokens: int = 8000,
    use_web_search: bool = True,
    show_output: bool = True,
    on_token=None,
    on_thinking=None,
    max_search_uses: int = None,
) -> str:
    """
    Run a single agent call with optional web search, streaming output.

    on_token(text)    — called for each output text chunk
    on_thinking(text) — called for each thinking chunk (optional)

    Returns the final assistant text.
    """
    if header and show_output:
        print_section(header)

    tools = []
    if use_web_search:
        web_search_tool = {"type": "web_search_20260209", "name": "web_search"}
        if max_search_uses is not None:
            web_search_tool["max_uses"] = max_search_uses
        tools = [
            web_search_tool,
            {"type": "web_fetch_20260209", "name": "web_fetch"},
        ]

    messages = [{"role": "user", "content": user_message}]
    final_text = ""

    while True:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            thinking={"type": "enabled", "budget_tokens": 2048},
            system=system_prompt,
            tools=tools,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        if show_output:
                            print(event.delta.text, end="", flush=True)
                        if on_token:
                            on_token(event.delta.text)
                    elif event.delta.type == "thinking_delta":
                        if on_thinking:
                            on_thinking(event.delta.thinking)

            msg = stream.get_final_message()

        # Collect text blocks
        final_text = "\n".join(
            b.text for b in msg.content
            if hasattr(b, "text") and b.type == "text"
        )

        if msg.stop_reason in ("end_turn", "max_tokens"):
            break
        elif msg.stop_reason == "pause_turn":
            # Server-side search loop hit limit — append and re-send
            messages.append({"role": "assistant", "content": msg.content})
            continue
        else:
            break

    if show_output:
        print()  # trailing newline after streaming

    return final_text
