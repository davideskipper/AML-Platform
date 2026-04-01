"""
AML IntelliGent Platform — Streamlit Web Interface
Bain & Company Style — KYC / CDD Module
"""

import os
import tempfile
from datetime import datetime
import streamlit as st
import anthropic

from kyc_platform.models import SessionState, CaseContext
from kyc_platform.super_agent import TOOLS, SYSTEM_PROMPT
from kyc_platform import (
    registry_agent, ubo_pep_agent, reputational_agent,
    economic_profile_agent, risk_countries_agent,
    transaction_agent, final_valuation_agent,
)

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="AML IntelliGent | Bain & Company",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

RED = "#CC0000"

st.markdown(f"""
<style>
  /* ── Base ── */
  .stApp, [data-testid="stAppViewContainer"] {{ background-color: #141414; color: #e0e0e0; }}
  [data-testid="stHeader"] {{ background-color: #0a0a0a; border-bottom: 2px solid {RED}; }}
  section[data-testid="stSidebar"] {{ display: none !important; }}
  [data-testid="collapsedControl"] {{ display: none !important; }}

  /* ── Typography ── */
  h1, h2, h3, h4 {{ color: #ffffff !important; }}
  label, p {{ color: #cccccc !important; }}

  /* ── Inputs ── */
  .stTextInput input, .stNumberInput input {{
    background-color: #1e1e1e !important; color: #e0e0e0 !important;
    border: 1px solid #3a3a3a !important; border-radius: 3px !important;
  }}
  .stTextArea textarea {{
    background-color: #1e1e1e !important; color: #e0e0e0 !important;
    border: 1px solid #3a3a3a !important; border-radius: 3px !important;
    font-size: 0.83rem !important;
  }}
  .stSelectbox > div > div {{
    background-color: #1e1e1e !important; color: #e0e0e0 !important;
    border: 1px solid #3a3a3a !important;
  }}

  /* ── Buttons → Bain red ── */
  .stButton > button {{
    background-color: {RED} !important; color: #fff !important;
    border: none !important; border-radius: 3px !important;
    font-weight: 600 !important; letter-spacing: 0.4px !important;
  }}
  .stButton > button:hover {{ background-color: #aa0000 !important; }}

  /* ── Progress ── */
  .stProgress > div > div > div {{ background-color: {RED} !important; }}

  /* ── Metric ── */
  [data-testid="metric-container"] {{
    background-color: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 4px; padding: 10px 14px;
  }}

  /* ── Chat ── */
  [data-testid="stChatMessage"] {{ background-color: #1e1e1e !important; }}
  [data-testid="stChatInput"] textarea {{
    background-color: #1e1e1e !important; color: #e0e0e0 !important;
    border: 1px solid #3a3a3a !important;
  }}

  /* ── Expander ── */
  details summary {{ color: #aaa !important; }}
  details {{ background-color: #1a1a1a !important; border: 1px solid #2a2a2a !important; }}

  /* ── Divider ── */
  hr {{ border-color: #2a2a2a !important; margin: 0.6rem 0 !important; }}

  /* ── Scrollbar ── */
  ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
  ::-webkit-scrollbar-track {{ background: #141414; }}
  ::-webkit-scrollbar-thumb {{ background: #3a3a3a; border-radius: 3px; }}

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {{
    background-color: #1e1e1e !important; border: 1px dashed #3a3a3a !important; border-radius: 4px;
  }}
</style>
""", unsafe_allow_html=True)

# ── Section definitions ────────────────────────────────────────────
SECTIONS = [
    {"key": "registry",         "number": "01", "icon": "🏛",
     "label": "Registry & Corporate Structure",
     "type": "agent",
     "desc": "Struttura societaria, catena proprietaria, modifiche recenti"},
    {"key": "ubo_pep",          "number": "02", "icon": "👤",
     "label": "UBO / PEP Screening",
     "type": "agent",
     "desc": "Beneficial owners, PEP, sanzioni OFAC / EU / UN"},
    {"key": "reputational",     "number": "03", "icon": "📰",
     "label": "Reputational Analysis",
     "type": "agent",
     "desc": "Adverse media, CONSOB, Banca d'Italia, watchlist"},
    {"key": "economic_profile", "number": "04", "icon": "📊",
     "label": "Economic Profile",
     "type": "agent",
     "desc": "Bilancio, EBITDA, coerenza profilo economico"},
    {"key": "risk_countries",   "number": "05", "icon": "🌍",
     "label": "Risk Countries",
     "type": "agent",
     "desc": "Esposizione FATF, sanzioni, Corruption Perception Index"},
    {"key": "transaction",      "number": "06", "icon": "💳",
     "label": "Transaction Analysis",
     "type": "manual",
     "desc": "Analisi AML transazioni — richiede file Excel / CSV"},
    {"key": "final_valuation",  "number": "07", "icon": "⚡",
     "label": "Final Valuation",
     "type": "super",
     "desc": "Parere finale — risk score, raccomandazione, piano d'azione"},
]

TOOL_TO_SECTION = {
    "run_registry_agent":        "registry",
    "run_ubo_pep_agent":         "ubo_pep",
    "run_reputational_agent":    "reputational",
    "run_economic_profile_agent":"economic_profile",
    "run_risk_countries_agent":  "risk_countries",
    "run_transaction_agent":     "transaction",
    "run_final_valuation":       "final_valuation",
}

# ── Session state ──────────────────────────────────────────────────
DEFAULTS = {
    "step": "setup",
    "kyc_state": None,
    "active_section": "registry",
    "edited_content": {},
    "agent_log": [],
    "manual_inputs": {},
    "excel_path": None,
    "excel_name": None,
    "running_agent": None,
    "sa_messages": [],
    "sa_initialized": False,
    "api_key": "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
if st.session_state.kyc_state is None:
    st.session_state.kyc_state = SessionState()

# ── Helpers ───────────────────────────────────────────────────────
def api_key():
    return st.session_state.api_key or os.environ.get("ANTHROPIC_API_KEY", "")

def get_client():
    k = api_key()
    return anthropic.Anthropic(api_key=k) if k else None

def sec_status(key):
    if st.session_state.edited_content.get(key):
        return "completed"
    return "completed" if st.session_state.kyc_state.has_result(key) else "empty"

def get_content(key):
    return (st.session_state.edited_content.get(key)
            or st.session_state.kyc_state.results.get(key, ""))

def log(agent, msg, level="running"):
    st.session_state.agent_log.append(
        {"ts": datetime.now().strftime("%H:%M:%S"), "agent": agent, "msg": msg, "level": level}
    )

def progress():
    done = sum(1 for s in SECTIONS if sec_status(s["key"]) == "completed")
    return done, len(SECTIONS)

def text_from(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            (b.text if hasattr(b, "text") else b.get("text", ""))
            for b in content
            if (hasattr(b, "type") and b.type == "text")
            or (isinstance(b, dict) and b.get("type") == "text")
        )
    return ""

def run_section(key, client):
    """Execute one section's agent."""
    state = st.session_state.kyc_state
    company = state.case.company_name
    country = state.case.country
    manual = st.session_state.manual_inputs.get(key, "")
    sec = next(s for s in SECTIONS if s["key"] == key)
    st.session_state.running_agent = key
    log(sec["label"], "Avvio...")
    try:
        if key == "registry":
            result = registry_agent.run(client, company, country, manual, show_output=False)
        elif key == "ubo_pep":
            result = ubo_pep_agent.run(client, company, country, manual, show_output=False)
        elif key == "reputational":
            result = reputational_agent.run(client, company, country, "", manual, show_output=False)
        elif key == "economic_profile":
            result = economic_profile_agent.run(client, company, country, manual, show_output=False)
        elif key == "risk_countries":
            result = risk_countries_agent.run(client, company, country, "", manual, show_output=False)
        elif key == "transaction":
            path = st.session_state.excel_path or ""
            if not path:
                raise ValueError("Nessun file Excel caricato — usa il pulsante Upload.")
            result = transaction_agent.run(client, path, company, manual, show_output=False)
        elif key == "final_valuation":
            result = final_valuation_agent.run(
                client, company, state.results, manual, show_output=False)
        else:
            raise ValueError(f"Sezione sconosciuta: {key}")
        state.add_result(key, result)
        st.session_state.edited_content[key] = result
        log(sec["label"], "Completato ✓", "done")
    except Exception as e:
        log(sec["label"], f"Errore: {e}", "error")
        raise
    finally:
        st.session_state.running_agent = None

# ── Header ────────────────────────────────────────────────────────
def render_header():
    state = st.session_state.kyc_state
    # Build header using columns to avoid nested f-string HTML issues
    h_left, h_right = st.columns([5, 1])
    with h_left:
        brand = "**BAIN &amp; COMPANY** &nbsp;|&nbsp; AML IntelliGent Platform · KYC / CDD Module"
        if st.session_state.step == "analysis" and state.case.company_name:
            done, total = progress()
            badge = f'<span style="background:{RED};color:white;font-size:0.7rem;padding:2px 8px;border-radius:10px;margin-left:10px;">{done}/{total}</span>'
            st.markdown(
                f'<div style="padding:8px 0 12px;border-bottom:2px solid {RED};margin-bottom:16px;">'
                f'<span style="font-size:1rem;font-weight:900;letter-spacing:3px;color:#fff;">BAIN &amp; COMPANY</span>'
                f'<span style="color:#444;margin:0 12px;">|</span>'
                f'<span style="font-size:0.82rem;color:#888;">AML IntelliGent Platform · KYC / CDD Module</span>'
                f'<span style="color:#555;margin:0 10px;">|</span>'
                f'<span style="color:#aaa;font-size:0.85rem;">{state.case.company_name}</span>'
                f'<span style="color:#555;font-size:0.78rem;margin-left:8px;">{state.case.case_id}</span>'
                f'{badge}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="padding:8px 0 12px;border-bottom:2px solid {RED};margin-bottom:16px;">'
                f'<span style="font-size:1rem;font-weight:900;letter-spacing:3px;color:#fff;">BAIN &amp; COMPANY</span>'
                f'<span style="color:#444;margin:0 12px;">|</span>'
                f'<span style="font-size:0.82rem;color:#888;">AML IntelliGent Platform · KYC / CDD Module</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with h_right:
        st.markdown('<div style="text-align:right;padding-top:8px;font-size:0.7rem;color:#444;">Claude Opus 4.6</div>',
                    unsafe_allow_html=True)

# ── SETUP SCREEN ──────────────────────────────────────────────────
def render_setup():
    render_header()
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center; padding:24px 0 20px;">
          <div style="font-size:1.8rem; font-weight:700; color:#fff;">New KYC / CDD Case</div>
          <div style="color:#666; margin-top:6px; font-size:0.9rem;">
            Inserisci i dati del cliente per avviare l'analisi
          </div>
        </div>
        """, unsafe_allow_html=True)

        key_val = st.text_input("Anthropic API Key", type="password",
                                value=api_key(), placeholder="sk-ant-...")
        if key_val:
            st.session_state.api_key = key_val

        st.markdown("---")
        st.markdown("#### Informazioni Cliente")

        company = st.text_input("Ragione Sociale *", placeholder="es. Meridian Capital S.r.l.")
        c1, c2 = st.columns(2)
        with c1:
            country = st.text_input("Paese *", placeholder="es. Italia")
        with c2:
            sector = st.text_input("Settore", placeholder="es. Wealth Management")
        c3, c4 = st.columns(2)
        with c3:
            case_id = st.text_input("Case ID", placeholder="es. AV-2026-0341")
        with c4:
            review = st.selectbox("Tipo di Review", [
                "Customer Due Diligence (CDD)",
                "Enhanced Due Diligence (EDD)",
                "Know Your Customer (KYC)",
                "Periodic Review",
            ])

        st.markdown("---")
        if st.button("▶  Avvia Analisi", use_container_width=True):
            if not company.strip() or not country.strip():
                st.error("Ragione Sociale e Paese sono obbligatori.")
            elif not api_key():
                st.error("Inserisci la Anthropic API Key.")
            else:
                s = st.session_state.kyc_state
                s.case.company_name = company.strip()
                s.case.country = country.strip()
                s.case.sector = sector.strip()
                s.case.case_id = case_id.strip() or f"KYC-{datetime.now().strftime('%Y%m%d-%H%M')}"
                log("Sistema", f"Caso aperto: {company} ({country})", "super")
                st.session_state.step = "analysis"
                st.rerun()

# ── LEFT PANEL ────────────────────────────────────────────────────
def render_left():
    st.markdown(f"""
    <div style="font-size:0.65rem; letter-spacing:2px; color:{RED};
                font-weight:700; margin-bottom:10px;">SEZIONI ANALISI</div>
    """, unsafe_allow_html=True)

    for sec in SECTIONS:
        key   = sec["key"]
        status = sec_status(key)
        active = st.session_state.active_section == key
        running = st.session_state.running_agent == key

        if running:
            icon, color = "⏳", "#ffaa44"
        elif status == "completed":
            icon, color = "✅", "#00cc55"
        elif sec["type"] == "manual":
            icon, color = "📋", "#4499ff"
        elif sec["type"] == "super":
            icon, color = "⚡", RED
        else:
            icon, color = "○", "#555"

        border = RED if active else ("#00cc55" if status == "completed" else "#2a2a2a")
        bg     = "#222" if active else "#1a1a1a"
        lbl_c  = "#fff" if active else "#bbb"

        st.markdown(f"""
        <div style="padding:8px 10px; margin:3px 0; border-radius:3px;
                    border-left:3px solid {border}; background:{bg};">
          <span style="color:{color}; margin-right:6px;">{icon}</span>
          <span style="color:#555; font-size:0.68rem; margin-right:6px;">{sec['number']}</span>
          <span style="font-size:0.78rem; color:{lbl_c};">{sec['label']}</span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("→", key=f"nav_{key}", help=sec["desc"],
                     use_container_width=True):
            st.session_state.active_section = key
            st.rerun()

    done, total = progress()
    st.markdown("---")
    st.progress(done / total, text=f"{done} / {total} completate")

# ── CENTER PANEL ──────────────────────────────────────────────────
def render_center():
    client = get_client()
    state  = st.session_state.kyc_state
    key    = st.session_state.active_section
    sec    = next(s for s in SECTIONS if s["key"] == key)
    status = sec_status(key)
    content = get_content(key)

    # Header
    c_title, c_badge = st.columns([3, 1])
    with c_title:
        st.markdown(f"""
        <div>
          <span style="color:{RED}; font-size:0.72rem; font-weight:700;
                       letter-spacing:1px;">{sec['number']}</span>
          <span style="font-size:1.2rem; font-weight:700; color:#fff;
                       margin-left:10px;">{sec['icon']} {sec['label']}</span>
        </div>
        <div style="color:#666; font-size:0.8rem; margin-top:3px;">{sec['desc']}</div>
        """, unsafe_allow_html=True)
    with c_badge:
        if status == "completed":
            st.success("✓ Completata")
        elif sec["type"] == "manual":
            st.info("📋 Input manuale")
        elif sec["type"] == "super":
            st.warning("⚡ Super Agent")
        else:
            st.caption("○ Da eseguire")

    st.markdown("---")

    # Manual context
    if key != "final_valuation":
        with st.expander("📝 Contesto manuale (opzionale)"):
            manual = st.text_area(
                "note",
                value=st.session_state.manual_inputs.get(key, ""),
                height=90,
                key=f"manual_{key}",
                label_visibility="collapsed",
                placeholder="Inserisci dati aggiuntivi, documenti o note per l'agente...",
            )
            st.session_state.manual_inputs[key] = manual

    # File upload for transaction
    if key == "transaction":
        st.markdown("#### 📁 File Transazioni")
        uploaded = st.file_uploader("Excel / CSV", type=["xlsx", "xls", "csv"],
                                    key="tx_upload", label_visibility="collapsed")
        if uploaded:
            suffix = os.path.splitext(uploaded.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(uploaded.read())
                st.session_state.excel_path = f.name
                st.session_state.excel_name = uploaded.name
            st.success(f"✓ {uploaded.name}")
        elif st.session_state.excel_name:
            st.info(f"📄 {st.session_state.excel_name}")

    # Action buttons
    b1, b2, _ = st.columns([1, 1, 3])
    label_map = {
        "agent":  "▶ Esegui Agente",
        "manual": "▶ Analizza File",
        "super":  "⚡ Genera Valutazione Finale",
    }
    with b1:
        if st.button(label_map[sec["type"]], key=f"run_{key}",
                     use_container_width=True):
            if not client:
                st.error("API Key non configurata.")
            else:
                try:
                    with st.spinner(f"{sec['label']} in esecuzione..."):
                        run_section(key, client)
                except Exception as e:
                    st.error(str(e))
                st.rerun()
    with b2:
        if status == "completed":
            if st.button("🔄 Ri-esegui", key=f"rerun_{key}", use_container_width=True):
                if client:
                    try:
                        with st.spinner("Ri-esecuzione..."):
                            run_section(key, client)
                    except Exception as e:
                        st.error(str(e))
                    st.rerun()

    st.markdown("---")

    # Content area
    if content:
        st.markdown(f"""
        <div style="font-size:0.65rem; letter-spacing:1px; color:{RED};
                    font-weight:700; margin-bottom:6px;">RISULTATO — MODIFICABILE</div>
        """, unsafe_allow_html=True)
        edited = st.text_area("result", value=content, height=460,
                              key=f"edit_{key}", label_visibility="collapsed")
        if edited != content:
            st.session_state.edited_content[key] = edited
            state.add_result(key, edited)
    else:
        type_desc = {"agent": "automatica via web search",
                     "manual": "richiede upload file Excel/CSV",
                     "super": "sintesi di tutte le sezioni"}
        st.markdown(f"""
        <div style="text-align:center; padding:70px 0; color:#333;">
          <div style="font-size:3rem;">{sec['icon']}</div>
          <div style="color:#555; margin-top:12px;">Sezione non eseguita</div>
          <div style="color:#3a3a3a; font-size:0.78rem; margin-top:6px;">
            Analisi {type_desc.get(sec['type'], '')}
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── RIGHT PANEL ───────────────────────────────────────────────────
def render_right():
    client = get_client()
    state  = st.session_state.kyc_state
    done, total = progress()

    # Case card
    st.markdown(f"""
    <div style="background:#1a1a1a; border-left:3px solid {RED}; border-radius:3px;
                padding:10px 12px; margin-bottom:12px;">
      <div style="font-size:0.65rem; color:{RED}; font-weight:700; letter-spacing:1px;">CLIENTE</div>
      <div style="font-weight:700; color:#fff; font-size:0.95rem;">{state.case.company_name}</div>
      <div style="color:#888; font-size:0.8rem;">{state.case.country}
        {f'&nbsp;·&nbsp;<span style="color:#555;">{state.case.case_id}</span>'
         if state.case.case_id else ''}
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.progress(done / total, text=f"Progresso: {done}/{total}")

    # Run all button
    if st.button("▶▶  Esegui Tutti gli Agenti", use_container_width=True, key="run_all"):
        if not client:
            st.error("API Key non configurata.")
        else:
            auto = [s for s in SECTIONS if s["type"] == "agent"]
            bar  = st.progress(0, text="Avvio...")
            for i, sec in enumerate(auto):
                bar.progress((i) / len(auto), text=f"{sec['label']}...")
                try:
                    run_section(sec["key"], client)
                except Exception as e:
                    st.error(f"{sec['label']}: {e}")
            bar.progress(1.0, text="Completato ✓")
            st.rerun()

    st.markdown("---")

    # Agent log
    st.markdown(f"""
    <div style="font-size:0.65rem; letter-spacing:2px; color:{RED};
                font-weight:700; margin-bottom:6px;">ATTIVITÀ AGENTI</div>
    """, unsafe_allow_html=True)

    level_colors = {"running": "#66cc66", "done": "#4488ff",
                    "error": "#ff5555", "super": "#ffaa44"}
    log_box = st.container(height=200)
    with log_box:
        if not st.session_state.agent_log:
            st.caption("Nessuna attività.")
        for entry in reversed(st.session_state.agent_log[-40:]):
            c = level_colors.get(entry["level"], "#888")
            st.markdown(
                f'<div style="font-size:0.7rem; font-family:monospace; color:{c}; '
                f'padding:1px 0;">'
                f'<span style="color:#444;">{entry["ts"]}</span> '
                f'<b>{entry["agent"]}</b> — {entry["msg"]}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Super Agent
    st.markdown(f"""
    <div style="font-size:0.65rem; letter-spacing:2px; color:{RED};
                font-weight:700; margin-bottom:6px;">⚡ SUPER AGENT</div>
    """, unsafe_allow_html=True)

    # Init Super Agent intro
    if not st.session_state.sa_initialized and client:
        try:
            bootstrap = {
                "role": "user",
                "content": (
                    f"Il caso è aperto per {state.case.company_name} ({state.case.country}). "
                    "Presentati in 2 righe come Super Agent e indica che sei pronto."
                ),
            }
            resp = client.messages.create(
                model="claude-opus-4-6", max_tokens=200, system=SYSTEM_PROMPT,
                messages=[bootstrap],
            )
            intro = text_from(resp.content)
            st.session_state.sa_messages = [
                bootstrap, {"role": "assistant", "content": intro}
            ]
            st.session_state.sa_initialized = True
            log("Super Agent", "Online", "super")
        except Exception as e:
            st.caption(f"Super Agent offline: {e}")

    # Chat display
    chat_box = st.container(height=180)
    with chat_box:
        for msg in st.session_state.sa_messages[-8:]:
            role    = msg["role"]
            content = msg["content"]
            if role == "user" and isinstance(content, str) and "Presentati" in content:
                continue
            txt = text_from(content) if isinstance(content, list) else (content or "")
            if txt.strip():
                with st.chat_message(role, avatar="⚡" if role == "assistant" else "👤"):
                    st.caption(txt[:280] + ("…" if len(txt) > 280 else ""))

    # Chat input
    if user_msg := st.chat_input("Chiedi al Super Agent...", key="sa_input"):
        if not client:
            st.error("API Key non configurata.")
        else:
            st.session_state.sa_messages.append({"role": "user", "content": user_msg})
            log("Super Agent", f"← {user_msg[:50]}", "super")

            # Agentic loop
            while True:
                try:
                    resp = client.messages.create(
                        model="claude-opus-4-6", max_tokens=2000,
                        thinking={"type": "adaptive"}, system=SYSTEM_PROMPT,
                        tools=TOOLS, messages=st.session_state.sa_messages,
                    )
                except Exception as e:
                    st.error(f"Super Agent: {e}")
                    break

                st.session_state.sa_messages.append(
                    {"role": "assistant", "content": resp.content}
                )

                if resp.stop_reason == "tool_use":
                    tool_results = []
                    for block in resp.content:
                        if not (hasattr(block, "type") and block.type == "tool_use"):
                            continue
                        sec_key = TOOL_TO_SECTION.get(block.name)
                        log(block.name, "Esecuzione...", "running")
                        if sec_key:
                            try:
                                run_section(sec_key, client)
                                result_txt = get_content(sec_key)[:1500]
                            except Exception as e:
                                result_txt = f"Errore: {e}"
                        else:
                            result_txt = f"Tool {block.name} non trovato"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_txt,
                        })
                    st.session_state.sa_messages.append(
                        {"role": "user", "content": tool_results}
                    )
                    continue
                else:
                    log("Super Agent", "→ risposta inviata", "super")
                    break

            st.rerun()

# ── ANALYSIS DASHBOARD ────────────────────────────────────────────
def render_analysis():
    render_header()
    left, center, right = st.columns([1.2, 3, 2])
    with left:
        render_left()
    with center:
        render_center()
    with right:
        render_right()

    st.markdown("---")
    if st.button("← Nuovo Caso", key="new_case"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ── ROUTER ────────────────────────────────────────────────────────
if st.session_state.step == "setup":
    render_setup()
else:
    render_analysis()
