"""Shared utilities: agent runner, output validation, shared helpers."""

import json
import anthropic


def no_docs_json(narrativa: str, note: str, extra_fields: dict = None) -> str:
    """Return a standard NON_VALUTABILE JSON string for agents lacking required docs."""
    d = {
        "rischioComplessivo": "NON_VALUTABILE",
        "principaliEvidenze": [],
        "flags": [],
        "narrativa": narrativa,
        "note": note,
    }
    if extra_fields:
        d.update(extra_fields)
    return json.dumps(d, ensure_ascii=False)


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
            thinking={"type": "enabled", "budget_tokens": 8000},
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


def run_standard_agent(
    client: anthropic.Anthropic,
    system_prompt: str,
    task_intro: str,
    context_label: str,
    company_name: str,
    country: str,
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
    on_thinking=None,
    use_web_search: bool = False,
    max_tokens: int = 6000,
    header: str = "",
) -> str:
    """
    Generic runner for standard two-parameter agents (company + country).
    Builds the user message and delegates to run_agent().
    """
    user_msg = f"{task_intro}\n\nAzienda: {company_name}\nPaese: {country}\n"
    if manual_context:
        user_msg += f"\n{context_label}\n{manual_context}"
    return run_agent(
        client=client,
        system_prompt=system_prompt,
        user_message=user_msg,
        header=header or f"Agent — {company_name}",
        max_tokens=max_tokens,
        use_web_search=use_web_search,
        show_output=show_output,
        on_token=on_token,
        on_thinking=on_thinking,
    )


# ── Output validation ─────────────────────────────────────────────

_VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "NON_VALUTABILE"}
_HALLUCINATION_MARKERS = [
    "da compilare", "inserire qui", "TODO", "PLACEHOLDER",
    "esempio", "sample text", "<nome>", "<data>",
]


def validate_agent_output(agent_name: str, output: str) -> tuple:
    """
    Validate agent JSON output. Returns (is_valid: bool, error_msg: str).
    Checks: JSON parseable, rischioComplessivo enum, narrativa min length,
    absence of hallucination placeholder strings.
    """
    if not output or not output.strip():
        return False, f"{agent_name}: output vuoto"

    # Extract JSON
    s = output.find("{")
    e = output.rfind("}") + 1
    if s < 0 or e <= s:
        return False, f"{agent_name}: output non contiene JSON valido"

    try:
        data = json.loads(output[s:e])
    except (json.JSONDecodeError, ValueError) as exc:
        return False, f"{agent_name}: JSON non valido — {exc}"

    # Check rischioComplessivo enum
    risk = data.get("rischioComplessivo", "")
    if risk and risk not in _VALID_RISK_LEVELS:
        return False, f"{agent_name}: rischioComplessivo '{risk}' non riconosciuto"

    # Check narrativa minimum length (skip for NON_VALUTABILE outputs)
    if risk != "NON_VALUTABILE":
        narrativa = data.get("narrativa", "")
        if narrativa and len(narrativa) < 100:
            return False, f"{agent_name}: narrativa troppo breve ({len(narrativa)} caratteri)"

    # Check for hallucination placeholders
    output_lower = output.lower()
    for marker in _HALLUCINATION_MARKERS:
        if marker.lower() in output_lower:
            return False, f"{agent_name}: possibile placeholder di allucinazione: '{marker}'"

    return True, ""
