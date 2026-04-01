"""
AML IntelliGent Platform — Streamlit Web Interface
===================================================
Run with:
    streamlit run app.py
"""

import os
import tempfile
import streamlit as st
import anthropic

from kyc_platform.models import SessionState
from kyc_platform.super_agent import TOOLS, SYSTEM_PROMPT
from kyc_platform import (
    registry_agent,
    ubo_pep_agent,
    reputational_agent,
    economic_profile_agent,
    risk_countries_agent,
    transaction_agent,
    final_valuation_agent,
)

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="AML IntelliGent Platform",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state init ─────────────────────────────────────────────
for key, default in {
    "messages": [],
    "kyc_state": None,
    "initialized": False,
    "excel_path": None,
    "excel_name": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.kyc_state is None:
    st.session_state.kyc_state = SessionState()

# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 AML IntelliGent")
    st.caption("KYC/CDD Analysis System · Claude Opus 4.6")
    st.divider()

    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        placeholder="sk-ant-...",
    )

    st.divider()
    st.markdown("#### 📁 File Transazioni")
    uploaded = st.file_uploader(
        "Carica Excel o CSV",
        type=["xlsx", "xls", "csv"],
        label_visibility="collapsed",
    )
    if uploaded:
        if uploaded.name != st.session_state.excel_name:
            suffix = os.path.splitext(uploaded.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(uploaded.read())
                st.session_state.excel_path = f.name
                st.session_state.excel_name = uploaded.name
        st.success(f"✓ {st.session_state.excel_name}")

    st.divider()
    st.markdown("#### 📊 Stato analisi")
    state: SessionState = st.session_state.kyc_state

    if state.case.company_name:
        st.caption(f"**Azienda:** {state.case.company_name}")
    if state.case.country:
        st.caption(f"**Paese:** {state.case.country}")

    agent_labels = {
        "registry":        "Registry",
        "ubo_pep":         "UBO / PEP",
        "reputational":    "Reputational",
        "economic_profile":"Economic Profile",
        "risk_countries":  "Risk Countries",
        "transaction":     "Transaction",
        "final_valuation": "Final Valuation",
    }
    for key, label in agent_labels.items():
        if state.has_result(key):
            st.markdown(f"✅ {label}")
        else:
            st.caption(f"○ {label}")

    st.divider()
    if st.button("🔄 Nuova sessione", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ── Main header ────────────────────────────────────────────────────
st.markdown("# 🔍 AML IntelliGent Platform")
st.caption("KYC/CDD Analysis System powered by Claude Opus 4.6")

if not api_key:
    st.info("👈 Inserisci la tua **Anthropic API Key** nella barra laterale per iniziare.")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)


# ── Tool executor ──────────────────────────────────────────────────
def execute_tool(tool_name: str, tool_input: dict, state: SessionState) -> str:
    """Execute a sub-agent tool and store the result in session state."""
    if tool_input.get("company_name") and not state.case.company_name:
        state.case.company_name = tool_input["company_name"]
    if tool_input.get("country") and not state.case.country:
        state.case.country = tool_input["country"]

    company = tool_input.get("company_name", state.case.company_name)
    country  = tool_input.get("country",       state.case.country)
    manual   = tool_input.get("manual_context", "")

    try:
        if tool_name == "run_registry_agent":
            result = registry_agent.run(client, company, country, manual, show_output=False)
            state.add_result("registry", result)

        elif tool_name == "run_ubo_pep_agent":
            result = ubo_pep_agent.run(client, company, country, manual, show_output=False)
            state.add_result("ubo_pep", result)

        elif tool_name == "run_reputational_agent":
            key_persons = tool_input.get("key_persons", "")
            result = reputational_agent.run(client, company, country, key_persons, manual, show_output=False)
            state.add_result("reputational", result)

        elif tool_name == "run_economic_profile_agent":
            result = economic_profile_agent.run(client, company, country, manual, show_output=False)
            state.add_result("economic_profile", result)

        elif tool_name == "run_risk_countries_agent":
            exposure = tool_input.get("country_exposure", "")
            result = risk_countries_agent.run(client, company, country, exposure, manual, show_output=False)
            state.add_result("risk_countries", result)

        elif tool_name == "run_transaction_agent":
            excel_path = (
                tool_input.get("excel_path")
                or st.session_state.excel_path
                or ""
            )
            if not excel_path:
                return "Nessun file Excel caricato. Carica un file dalla barra laterale prima di eseguire l'analisi transazionale."
            result = transaction_agent.run(client, excel_path, company, manual, show_output=False)
            state.add_result("transaction", result)

        elif tool_name == "run_final_valuation":
            notes = tool_input.get("notes", "")
            result = final_valuation_agent.run(
                client, state.case.company_name, state.results, notes, show_output=False
            )
            state.add_result("final_valuation", result)

        else:
            return f"Tool sconosciuto: {tool_name}"

    except Exception as exc:
        return f"Errore in {tool_name}: {exc}"

    return result[:1500] + "\n\n[... output completo salvato in sessione ...]" if len(result) > 1500 else result


# ── Helper: extract text from content blocks ───────────────────────
def get_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if hasattr(b, "type") and b.type == "text":
                parts.append(b.text)
            elif isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        return "\n".join(parts)
    return ""


def is_tool_result_message(content) -> bool:
    """True if this is a user message containing tool results (not user text)."""
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "tool_result":
            return True
        if hasattr(first, "type") and getattr(first, "type", None) == "tool_result":
            return True
    return False


# ── Initialize chat ────────────────────────────────────────────────
if not st.session_state.initialized:
    bootstrap = {
        "role": "user",
        "content": (
            "Inizia la sessione. Presentati brevemente e chiedi all'utente "
            "il nome dell'azienda da analizzare e il paese di registrazione."
        ),
    }
    with st.spinner("Avvio Super Agent..."):
        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[bootstrap],
        )
    st.session_state.messages = [
        bootstrap,
        {"role": "assistant", "content": resp.content},
    ]
    st.session_state.initialized = True
    st.rerun()


# ── Display chat history ───────────────────────────────────────────
BOOTSTRAP_MARKER = "Inizia la sessione"

for msg in st.session_state.messages:
    role    = msg["role"]
    content = msg["content"]

    if role == "user":
        # Skip bootstrap message and tool result messages
        if isinstance(content, str) and BOOTSTRAP_MARKER in content:
            continue
        if is_tool_result_message(content):
            continue
        text = get_text(content)
        if text.strip():
            with st.chat_message("user"):
                st.markdown(text)

    elif role == "assistant":
        text = get_text(content)
        if text.strip():
            with st.chat_message("assistant", avatar="🔍"):
                st.markdown(text)


# ── Chat input & agentic loop ──────────────────────────────────────
if user_input := st.chat_input("Scrivi un messaggio al Super Agent..."):
    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})

    # Agentic loop
    while True:
        with st.spinner("Super Agent sta elaborando..."):
            resp = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4000,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=st.session_state.messages,
            )

        st.session_state.messages.append({"role": "assistant", "content": resp.content})
        assistant_text = get_text(resp.content)

        if resp.stop_reason == "tool_use":
            # Show any text the Super Agent produced alongside the tool call
            if assistant_text.strip():
                with st.chat_message("assistant", avatar="🔍"):
                    st.markdown(assistant_text)

            # Execute each tool
            tool_results = []
            for block in resp.content:
                if not (hasattr(block, "type") and block.type == "tool_use"):
                    continue
                label = block.name.replace("run_", "").replace("_", " ").title()
                with st.status(f"⚙️ {label} in esecuzione...", expanded=False) as status:
                    result_text = execute_tool(
                        block.name, block.input, st.session_state.kyc_state
                    )
                    status.update(label=f"✅ {label} completato", state="complete")
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result_text,
                })

            st.session_state.messages.append({"role": "user", "content": tool_results})
            continue  # let Super Agent process results

        elif resp.stop_reason == "end_turn":
            if assistant_text.strip():
                with st.chat_message("assistant", avatar="🔍"):
                    st.markdown(assistant_text)
            break

        else:
            break

    st.rerun()
