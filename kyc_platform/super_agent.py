"""
Super Agent
===========
Conversational orchestrator that:
- Interacts with the compliance officer via CLI
- Decides which sub-agents to invoke and when
- Collects manual context from the user before each agent run
- Manages session state (accumulated findings)
- Engages the Final Valuation Agent on user request

The Super Agent is itself a Claude claude-opus-4-6 conversation; sub-agents are
exposed as user-defined tools in its tool list.
"""

import json
import anthropic

from .models import SessionState
from . import (
    registry_agent,
    ubo_pep_agent,
    reputational_agent,
    economic_profile_agent,
    transaction_agent,
    final_valuation_agent,
)

# ── Tool definitions exposed to the Super Agent ──────────────────────────────

TOOLS = [
    {
        "name": "run_registry_agent",
        "description": (
            "Registry Agent: analyze corporate structure, shareholdings, "
            "ownership chain, subsidiaries, and recent corporate changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name":   {"type": "string"},
                "country":        {"type": "string"},
                "manual_context": {
                    "type": "string",
                    "description": "Additional documents or data provided by the analyst (optional)",
                },
            },
            "required": ["company_name", "country"],
        },
    },
    {
        "name": "run_ubo_pep_agent",
        "description": (
            "UBO/PEP Agent: identify Ultimate Beneficial Owners, screen for "
            "Politically Exposed Persons, check sanctions lists (OFAC, EU, UN)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name":   {"type": "string"},
                "country":        {"type": "string"},
                "manual_context": {
                    "type": "string",
                    "description": "Shareholder list, org chart, or other UBO data (optional)",
                },
            },
            "required": ["company_name", "country"],
        },
    },
    {
        "name": "run_reputational_agent",
        "description": (
            "Reputational Agent: search for negative news, adverse media, and "
            "regulatory actions (CONSOB, Banca d'Italia, FCA, SEC, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name":   {"type": "string"},
                "country":        {"type": "string"},
                "key_persons":    {
                    "type": "string",
                    "description": "Names of key persons (shareholders, directors) to screen individually",
                },
                "manual_context": {"type": "string"},
            },
            "required": ["company_name", "country"],
        },
    },
    {
        "name": "run_economic_profile_agent",
        "description": (
            "Economic Profile Agent: analyze balance sheet, profitability, "
            "revenue trends, and consistency with declared business activity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name":   {"type": "string"},
                "country":        {"type": "string"},
                "manual_context": {
                    "type": "string",
                    "description": "Financial statements, annual report, or balance sheet data (optional)",
                },
            },
            "required": ["company_name", "country"],
        },
    },
    {
        "name": "run_transaction_agent",
        "description": (
            "Transaction Agent: analyze an Excel or CSV file of transactions "
            "for AML patterns (structuring, round-tripping, layering, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "excel_path":     {
                    "type": "string",
                    "description": "Absolute or relative path to the Excel/CSV file",
                },
                "company_name":   {"type": "string"},
                "manual_context": {"type": "string"},
            },
            "required": ["excel_path"],
        },
    },
    {
        "name": "run_final_valuation",
        "description": (
            "Final Valuation Agent: synthesize all collected findings into a "
            "comprehensive KYC/CDD Opinion Report with risk score and recommendation. "
            "Call this only when the user explicitly asks for the final report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "notes": {
                    "type": "string",
                    "description": "Any final analyst notes to include in the report (optional)",
                },
            },
            "required": [],
        },
    },
]

# ── Super Agent system prompt ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the **Super Agent** of the AML IntelliGent Platform,
an AI-powered KYC/CDD orchestrator for compliance officers.

Your responsibilities:
1. Guide the compliance officer through the KYC analysis process
2. Collect necessary information about the client company
3. Decide which specialized agents to run and in what order
4. Before running each agent, ask the user if they have additional documents or data to provide
5. Summarize findings progressively as agents complete
6. Run the Final Valuation Agent only when the user explicitly requests it

Recommended analysis sequence:
  Registry Agent → UBO/PEP Agent → Reputational Agent →
  Economic Profile Agent → Transaction Agent (includes geographic risk) →
  Final Valuation Agent

Guidelines:
- Be professional and concise
- After each agent completes, briefly summarize the key findings
- If an agent reveals a PEP, high-risk country, or major red flag, flag it prominently
- Ask the user before running the Final Valuation: "Tutti gli agenti sono stati eseguiti. Vuoi che generi la valutazione finale?"
- Respond in the same language as the user (Italian if they write Italian, English if English)
- Do NOT hallucinate findings — rely on what the agents return
"""

# ── Tool dispatcher ───────────────────────────────────────────────────────────

def _execute_tool(
    client: anthropic.Anthropic,
    tool_name: str,
    tool_input: dict,
    state: SessionState,
) -> str:
    """Execute a sub-agent tool and store the result in session state."""

    # Update session state with case info if available
    if tool_input.get("company_name") and not state.case.company_name:
        state.case.company_name = tool_input["company_name"]
    if tool_input.get("country") and not state.case.country:
        state.case.country = tool_input["country"]

    company = tool_input.get("company_name", state.case.company_name)
    country  = tool_input.get("country",       state.case.country)
    manual   = tool_input.get("manual_context", "")

    try:
        if tool_name == "run_registry_agent":
            result = registry_agent.run(client, company, country, manual)
            state.add_result("registry", result)

        elif tool_name == "run_ubo_pep_agent":
            result = ubo_pep_agent.run(client, company, country, manual)
            state.add_result("ubo_pep", result)

        elif tool_name == "run_reputational_agent":
            key_persons = tool_input.get("key_persons", "")
            result = reputational_agent.run(client, company, country, key_persons, manual)
            state.add_result("reputational", result)

        elif tool_name == "run_economic_profile_agent":
            result = economic_profile_agent.run(client, company, country, manual)
            state.add_result("economic_profile", result)

        elif tool_name == "run_transaction_agent":
            excel_path = tool_input.get("excel_path", "")
            if not excel_path:
                return "Error: no Excel file path provided."
            result = transaction_agent.run(client, excel_path, company, manual)
            state.add_result("transaction", result)

        elif tool_name == "run_final_valuation":
            notes = tool_input.get("notes", "")
            result = final_valuation_agent.run(
                client, state.case.company_name, state.results, notes
            )
            state.add_result("final_valuation", result)

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as exc:
        return f"Error running {tool_name}: {exc}"

    # Return a brief summary to the Super Agent (not the full text, to save tokens)
    summary = result[:1500] + " [... truncated ...]" if len(result) > 1500 else result
    return summary


# ── Main interactive loop ─────────────────────────────────────────────────────

def _print_welcome() -> None:
    width = 65
    print("\n" + "═" * width)
    print("  AML IntelliGent Platform — KYC Analysis System")
    print("  Powered by Claude claude-opus-4-6 (Opus 4.6)")
    print("═" * width)
    print("  Type 'exit' or 'quit' to end the session.")
    print("═" * width + "\n")


def run(client: anthropic.Anthropic) -> None:
    """Start the interactive Super Agent session."""
    _print_welcome()

    state    = SessionState()
    messages = []

    # Bootstrap: ask Super Agent to introduce itself
    messages.append({
        "role": "user",
        "content": (
            "Inizia la sessione. Presentati brevemente e chiedi all'utente "
            "il nome dell'azienda da analizzare e il paese di registrazione."
        ),
    })

    while True:
        # ── Stream Super Agent response ──────────────────────────────────────
        print("\n\033[1;34mSuper Agent:\033[0m ", end="", flush=True)

        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4000,
            thinking={"type": "enabled", "budget_tokens": 8000},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                if (event.type == "content_block_delta"
                        and event.delta.type == "text_delta"):
                    print(event.delta.text, end="", flush=True)

            msg = stream.get_final_message()

        messages.append({"role": "assistant", "content": msg.content})

        # ── Handle tool calls ────────────────────────────────────────────────
        if msg.stop_reason == "tool_use":
            tool_use_blocks = [b for b in msg.content if b.type == "tool_use"]
            tool_results = []

            for block in tool_use_blocks:
                print(f"\n\n\033[33m[{block.name}]\033[0m Avvio...", flush=True)
                result_text = _execute_tool(client, block.name, block.input, state)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result_text,
                })

            messages.append({"role": "user", "content": tool_results})
            continue  # let Super Agent process the results

        # ── Wait for user input ──────────────────────────────────────────────
        print("\n")
        try:
            user_input = input("\033[1;32m>>> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSessione terminata.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "esci", "q"):
            print("\nGoodbye! / Arrivederci!\n")
            break

        messages.append({"role": "user", "content": user_input})
