"""
AML IntelliGent Platform — Streamlit Web Interface
Bain & Company Style — KYC / CDD Module
White Theme | Document Upload | Live Streaming | JSON Display
"""

import io
import json
import os
import tempfile
from datetime import datetime
import streamlit as st
import anthropic

from kyc_platform.models import SessionState
from kyc_platform.super_agent import TOOLS, SYSTEM_PROMPT as SA_PROMPT
from kyc_platform import (
    registry_agent, ubo_pep_agent, reputational_agent,
    economic_profile_agent, risk_countries_agent,
    transaction_agent, final_valuation_agent,
)

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="AML IntelliGent | Bain & Company",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

RED = "#CC0000"

# ── CSS — White Bain Theme ────────────────────────────────────────
st.markdown(f"""
<style>
  .stApp, [data-testid="stAppViewContainer"] {{
    background-color: #ffffff; color: #1a1a1a;
  }}
  [data-testid="stHeader"] {{
    background-color: #ffffff; border-bottom: 2px solid {RED};
  }}
  section[data-testid="stSidebar"] {{ display: none !important; }}
  [data-testid="collapsedControl"] {{ display: none !important; }}
  h1, h2, h3, h4 {{ color: #1a1a1a !important; }}
  label, p {{ color: #333333 !important; }}
  .stTextInput input, .stNumberInput input {{
    background-color: #f9f9f9 !important; color: #1a1a1a !important;
    border: 1px solid #d8d8d8 !important; border-radius: 3px !important;
  }}
  .stTextArea textarea {{
    background-color: #f9f9f9 !important; color: #1a1a1a !important;
    border: 1px solid #d8d8d8 !important; border-radius: 3px !important;
    font-size: 0.83rem !important;
  }}
  .stSelectbox > div > div {{
    background-color: #f9f9f9 !important; color: #1a1a1a !important;
    border: 1px solid #d8d8d8 !important;
  }}
  .stButton > button {{
    background-color: {RED} !important; color: #ffffff !important;
    border: none !important; border-radius: 3px !important;
    font-weight: 600 !important; letter-spacing: 0.4px !important;
  }}
  .stButton > button:hover {{ background-color: #aa0000 !important; }}
  .stProgress > div > div > div {{ background-color: {RED} !important; }}
  [data-testid="metric-container"] {{
    background-color: #f5f5f5; border: 1px solid #e0e0e0;
    border-radius: 4px; padding: 10px 14px;
  }}
  [data-testid="stChatMessage"] {{ background-color: #f5f5f5 !important; }}
  [data-testid="stChatInput"] textarea {{
    background-color: #f9f9f9 !important; color: #1a1a1a !important;
    border: 1px solid #d8d8d8 !important;
  }}
  details summary {{ color: #444 !important; }}
  details {{ background-color: #f9f9f9 !important; border: 1px solid #e0e0e0 !important; }}
  hr {{ border-color: #eeeeee !important; margin: 0.6rem 0 !important; }}
  ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
  ::-webkit-scrollbar-track {{ background: #f5f5f5; }}
  ::-webkit-scrollbar-thumb {{ background: #cccccc; border-radius: 3px; }}
  [data-testid="stFileUploader"] {{
    background-color: #f9f9f9 !important;
    border: 1px dashed #cccccc !important; border-radius: 4px;
  }}
  .stRadio label {{ color: #333 !important; }}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────
SECTIONS = [
    {"key": "registry",         "number": "01", "icon": "🏛",
     "label": "Registry & Corporate Structure",
     "desc": "Struttura societaria, catena proprietaria, modifiche recenti"},
    {"key": "ubo_pep",          "number": "02", "icon": "👤",
     "label": "UBO / PEP Screening",
     "desc": "Titolari effettivi, PEP, sanzioni OFAC / EU / UN"},
    {"key": "reputational",     "number": "03", "icon": "📰",
     "label": "Reputational Analysis",
     "desc": "Adverse media, precedenti giudiziari, watchlist — web search limitata (max 3)"},
    {"key": "economic_profile", "number": "04", "icon": "📊",
     "label": "Economic Profile",
     "desc": "Bilancio, EBITDA, coerenza profilo economico"},
    {"key": "risk_countries",   "number": "05", "icon": "🌍",
     "label": "Risk Countries",
     "desc": "Esposizione FATF, sanzioni, Corruption Perception Index"},
    {"key": "transaction",      "number": "06", "icon": "💳",
     "label": "Transaction Analysis",
     "desc": "Analisi AML movimenti bancari — richiede file Excel / CSV"},
    {"key": "final_valuation",  "number": "07", "icon": "⚡",
     "label": "Final Valuation",
     "desc": "Customer Risk Rating finale — sintetizza tutti gli agenti"},
]

SECTION_DOC_HINTS = {
    "registry":         "Visura camerale, atto costitutivo, statuto, organigramma societario",
    "ubo_pep":          "Dichiarazione UBO, documenti d'identità soci/amministratori, estratto Registro UBO",
    "reputational":     "Sentenze, atti giudiziari, comunicati stampa, lista persone chiave con ruolo e nazionalità",
    "economic_profile": "Bilancio, conto economico, nota integrativa (ultimi 3 anni), dichiarazioni fiscali, rating",
    "risk_countries":   "Organigramma internazionale, contratti esteri, lista paesi di operatività e controparti",
    "transaction":      "File Excel/CSV: data, controparte, IBAN, importo, valuta, causale (movimenti bancari)",
    "final_valuation":  None,
}

TOOL_TO_SECTION = {
    "run_registry_agent":         "registry",
    "run_ubo_pep_agent":          "ubo_pep",
    "run_reputational_agent":     "reputational",
    "run_economic_profile_agent": "economic_profile",
    "run_risk_countries_agent":   "risk_countries",
    "run_transaction_agent":      "transaction",
    "run_final_valuation":        "final_valuation",
}

RISK_COLORS = {
    "LOW":      "#22aa55",
    "MEDIUM":   "#f59e0b",
    "HIGH":     "#ef4444",
    "CRITICAL": "#7c3aed",
    "BASSO":    "#22aa55",
    "MEDIO":    "#f59e0b",
    "MEDIO-ALTO": "#f97316",
    "ALTO":     "#ef4444",
    "CRITICO":  "#7c3aed",
}

# ── Session state ─────────────────────────────────────────────────
DEFAULTS = {
    "step":          "setup",
    "kyc_state":     None,
    "active_section":"registry",
    "edited_content":{},
    "agent_log":     [],
    "section_modes": {},
    "section_docs":  {},
    "section_doc_names": {},
    "section_notes": {},
    "excel_path":    None,
    "excel_name":    None,
    "running_agent": None,
    "knowledge_base":     "",
    "kb_doc_names":       [],
    "sa_messages":   [],
    "sa_initialized":False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
if st.session_state.kyc_state is None:
    st.session_state.kyc_state = SessionState()

# Init section modes defaults
for sec in SECTIONS:
    if sec["key"] not in st.session_state.section_modes:
        if sec["key"] == "final_valuation":
            st.session_state.section_modes[sec["key"]] = "super"
        else:
            st.session_state.section_modes[sec["key"]] = "agent"


# ── Helpers ───────────────────────────────────────────────────────
def get_api_key():
    return (
        os.environ.get("ANTHROPIC_API_KEY", "")
        or st.secrets.get("ANTHROPIC_API_KEY", "")
    )

def get_client():
    k = get_api_key()
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
        {"ts": datetime.now().strftime("%H:%M:%S"),
         "agent": agent, "msg": msg, "level": level}
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

def extract_text_from_file(uploaded_file) -> str:
    """Extract text from PDF, DOCX, XLSX, CSV, TXT files."""
    name = uploaded_file.name
    ext = os.path.splitext(name)[1].lower()
    data = uploaded_file.read()
    try:
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            ).strip()
        elif ext == ".docx":
            import docx as docxlib
            doc = docxlib.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext in (".xlsx", ".xls"):
            import pandas as pd
            dfs = pd.read_excel(io.BytesIO(data), sheet_name=None)
            lines = []
            for sheet, df in dfs.items():
                lines.append(f"[Foglio: {sheet}]")
                lines.append(df.head(300).to_string(index=False))
            return "\n\n".join(lines)
        elif ext == ".csv":
            import pandas as pd
            df = pd.read_csv(io.BytesIO(data))
            return df.head(300).to_string(index=False)
        elif ext in (".txt", ".md"):
            return data.decode("utf-8", errors="replace")
        else:
            return f"[Formato non supportato: {ext}]"
    except Exception as e:
        return f"[Errore lettura {name}: {e}]"

def parse_json_result(text: str) -> dict | None:
    """Try to extract and parse JSON from agent output."""
    if not text:
        return None
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return None

def get_risk_color(level: str) -> str:
    return RISK_COLORS.get(level.upper() if level else "", "#888888")

def run_section(key, client, on_token=None):
    """Execute one section's agent with document context."""
    state   = st.session_state.kyc_state
    company = state.case.company_name
    country = state.case.country

    # Build context from uploaded docs + manual notes
    docs_text  = st.session_state.section_docs.get(key, "")
    notes_text = st.session_state.section_notes.get(key, "")
    kb_text    = st.session_state.knowledge_base

    parts = []
    if kb_text:
        parts.append(f"BASE DOCUMENTALE DI RIFERIMENTO (NORMATIVA):\n\n{kb_text}")
    if docs_text:
        parts.append(f"DOCUMENTI DEL CLIENTE:\n\n{docs_text}")
    if notes_text:
        parts.append(f"NOTE ANALISTA:\n{notes_text}")
    manual_ctx = "\n\n---\n\n".join(parts)

    # Disable web search when client documents are provided
    use_web = not bool(docs_text)

    sec = next(s for s in SECTIONS if s["key"] == key)
    st.session_state.running_agent = key
    mode = "documenti" if docs_text else "web search" if use_web else "dati forniti"
    log(sec["label"], f"Avvio analisi ({mode})...")

    try:
        if key == "registry":
            result = registry_agent.run(
                client, company, country, manual_ctx,
                show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "ubo_pep":
            result = ubo_pep_agent.run(
                client, company, country, manual_ctx,
                show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "reputational":
            result = reputational_agent.run(
                client, company, country, "", manual_ctx,
                show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "economic_profile":
            result = economic_profile_agent.run(
                client, company, country, manual_ctx,
                show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "risk_countries":
            result = risk_countries_agent.run(
                client, company, country, "", manual_ctx,
                show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "transaction":
            path = st.session_state.excel_path or ""
            if not path:
                raise ValueError("Nessun file Excel/CSV caricato — carica il file nella sezione configurazione.")
            result = transaction_agent.run(
                client, path, company, manual_ctx,
                show_output=False, on_token=on_token)
        elif key == "final_valuation":
            result = final_valuation_agent.run(
                client, company, state.results, manual_ctx,
                show_output=False, on_token=on_token)
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
    h_left, h_right = st.columns([5, 1])
    with h_left:
        if st.session_state.step == "analysis" and state.case.company_name:
            done, total = progress()
            badge_color = "#22aa55" if done == total else RED
            st.markdown(
                '<div style="padding:8px 0 12px;border-bottom:2px solid ' + RED + ';margin-bottom:16px;">'
                '<span style="font-size:1rem;font-weight:900;letter-spacing:3px;color:#1a1a1a;">BAIN &amp; COMPANY</span>'
                '<span style="color:#bbb;margin:0 12px;">|</span>'
                '<span style="font-size:0.82rem;color:#666;">AML IntelliGent Platform · KYC / CDD Module</span>'
                '<span style="color:#ddd;margin:0 10px;">|</span>'
                '<span style="color:#1a1a1a;font-size:0.9rem;font-weight:600;">' + state.case.company_name + '</span>'
                '<span style="color:#aaa;font-size:0.78rem;margin-left:8px;">' + state.case.case_id + '</span>'
                '<span style="background:' + badge_color + ';color:white;font-size:0.68rem;'
                'padding:2px 8px;border-radius:10px;margin-left:10px;">' + str(done) + '/' + str(total) + '</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="padding:8px 0 12px;border-bottom:2px solid ' + RED + ';margin-bottom:16px;">'
                '<span style="font-size:1rem;font-weight:900;letter-spacing:3px;color:#1a1a1a;">BAIN &amp; COMPANY</span>'
                '<span style="color:#bbb;margin:0 12px;">|</span>'
                '<span style="font-size:0.82rem;color:#666;">AML IntelliGent Platform · KYC / CDD Module</span>'
                '</div>',
                unsafe_allow_html=True,
            )
    with h_right:
        st.markdown(
            '<div style="text-align:right;padding-top:8px;font-size:0.7rem;color:#aaa;">claude-opus-4-6</div>',
            unsafe_allow_html=True,
        )

# ── STEP 1: SETUP ─────────────────────────────────────────────────
def render_setup():
    render_header()
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            '<div style="text-align:center;padding:24px 0 20px;">'
            '<div style="font-size:1.8rem;font-weight:700;color:#1a1a1a;">Nuovo Caso KYC / CDD</div>'
            '<div style="color:#888;margin-top:6px;font-size:0.9rem;">'
            'Inserisci i dati del cliente per avviare l\'analisi</div></div>',
            unsafe_allow_html=True,
        )

        if not get_api_key():
            st.error("API Key Anthropic non trovata. Aggiungila nei Secrets di Streamlit Cloud: ANTHROPIC_API_KEY")

        st.markdown("#### Informazioni Cliente")
        company = st.text_input("Ragione Sociale *", placeholder="es. Meridian Capital S.r.l.")
        c1, c2 = st.columns(2)
        with c1:
            country = st.text_input("Paese *", placeholder="es. Italia")
        with c2:
            sector = st.text_input("Settore", placeholder="es. Wealth Management")
        c3, c4 = st.columns(2)
        with c3:
            case_id = st.text_input("Case ID", placeholder="es. AML-2026-0341")
        with c4:
            analyst = st.text_input("Analista", placeholder="es. M. Rossi")

        st.markdown("---")
        st.markdown("#### 📚 Knowledge Base Normativa (opzionale)")
        st.markdown(
            '<div style="font-size:0.8rem;color:#888;margin-bottom:8px;">'
            'Carica i documenti normativi di riferimento che tutti gli agenti useranno come base '
            'di conoscenza: FATF guidelines, circolari UIF, D.Lgs. 231/2007, liste sanzioni, '
            'policy AML interne, indicatori di anomalia, ecc.'
            '</div>',
            unsafe_allow_html=True,
        )
        kb_files = st.file_uploader(
            "Documenti Knowledge Base",
            type=["pdf", "docx", "txt", "md", "csv"],
            accept_multiple_files=True,
            key="kb_upload",
            label_visibility="collapsed",
        )
        if kb_files:
            texts, names = [], []
            for f in kb_files:
                extracted = extract_text_from_file(f)
                texts.append(f"=== {f.name} ===\n{extracted}")
                names.append(f.name)
            st.session_state.knowledge_base  = "\n\n".join(texts)
            st.session_state.kb_doc_names    = names
            total_chars = len(st.session_state.knowledge_base)
            st.success(
                f"✓ {len(texts)} documento/i caricato/i · "
                f"{total_chars:,} caratteri · "
                "disponibili per tutti gli agenti"
            )
        elif st.session_state.kb_doc_names:
            st.info("📚 KB caricata: " + ", ".join(st.session_state.kb_doc_names))

        st.markdown("---")
        if st.button("Continua →  Configura Sezioni", use_container_width=True):
            if not company.strip() or not country.strip():
                st.error("Ragione Sociale e Paese sono obbligatori.")
            elif not get_api_key():
                st.error("Configura ANTHROPIC_API_KEY nei Secrets prima di procedere.")
            else:
                s = st.session_state.kyc_state
                s.case.company_name = company.strip()
                s.case.country      = country.strip()
                s.case.sector       = sector.strip()
                s.case.case_id      = case_id.strip() or f"AML-{datetime.now().strftime('%Y%m%d-%H%M')}"
                log("Sistema", f"Caso aperto: {company} ({country})", "super")
                st.session_state.step = "section_config"
                st.rerun()


# ── STEP 2: SECTION CONFIG ────────────────────────────────────────
def render_section_config():
    render_header()
    state = st.session_state.kyc_state

    _, col, _ = st.columns([0.3, 3, 0.3])
    with col:
        st.markdown(
            '<div style="padding:8px 0 4px;">'
            '<div style="font-size:1.3rem;font-weight:700;color:#1a1a1a;">Configura Sezioni di Analisi</div>'
            '<div style="color:#888;font-size:0.85rem;margin-top:4px;">'
            'Per ogni sezione: scegli la modalità, carica i documenti e aggiungi note. '
            'Caricare documenti disabilita la ricerca web (risparmio token).</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        for sec in SECTIONS:
            key  = sec["key"]
            hint = SECTION_DOC_HINTS.get(key)

            # Card container
            st.markdown(
                '<div style="background:#f8f8f8;border:1px solid #e8e8e8;'
                'border-left:3px solid ' + RED + ';border-radius:4px;'
                'padding:14px 18px;margin-bottom:12px;">'
                '<span style="font-size:1.1rem;">' + sec["icon"] + '</span>'
                '<span style="color:' + RED + ';font-size:0.7rem;font-weight:700;'
                'margin-left:8px;">' + sec["number"] + '</span>'
                '<span style="font-size:0.95rem;font-weight:600;color:#1a1a1a;'
                'margin-left:8px;">' + sec["label"] + '</span>'
                '<div style="color:#888;font-size:0.78rem;margin-top:3px;margin-left:28px;">'
                + sec["desc"] + '</div></div>',
                unsafe_allow_html=True,
            )

            if key == "final_valuation":
                st.markdown(
                    '<div style="margin-left:28px;margin-bottom:12px;'
                    'font-size:0.82rem;color:#888;">'
                    '⚡ Modalità fissa: sintetizza automaticamente i risultati degli altri agenti.</div>',
                    unsafe_allow_html=True,
                )
                # Optional notes for final valuation
                notes = st.text_area(
                    "Note aggiuntive (opzionale)",
                    value=st.session_state.section_notes.get(key, ""),
                    height=60,
                    key=f"cfg_notes_{key}",
                    placeholder="Istruzioni particolari per la valutazione finale...",
                )
                st.session_state.section_notes[key] = notes
                st.markdown("---")
                continue

            # Mode toggle
            col_mode, col_info = st.columns([2, 3])
            with col_mode:
                current_mode = st.session_state.section_modes.get(key, "agent")
                mode_idx = 0 if current_mode == "agent" else 1
                mode = st.radio(
                    "Modalità",
                    ["🤖  Agente", "✍️  Manuale"],
                    index=mode_idx,
                    key=f"cfg_mode_{key}",
                    horizontal=True,
                )
                st.session_state.section_modes[key] = "agent" if "Agente" in mode else "manual"

            with col_info:
                if st.session_state.section_modes[key] == "agent":
                    already_loaded = st.session_state.section_doc_names.get(key, [])
                    if already_loaded:
                        st.success("✓ " + ", ".join(already_loaded))
                    else:
                        st.caption("Carica documenti o l'agente userà web search (solo Reputational)")
                else:
                    st.info("✍️ Inserisci i risultati manualmente nella pagina di analisi")

            # Document upload (only for agent mode, or always show for convenience)
            if hint and st.session_state.section_modes[key] == "agent":
                st.markdown(
                    '<div style="font-size:0.75rem;color:#666;margin:6px 0 4px;">'
                    '📎 <b>Documenti suggeriti:</b> ' + hint + '</div>',
                    unsafe_allow_html=True,
                )

                # Special handling for transaction: need Excel
                if key == "transaction":
                    uploaded = st.file_uploader(
                        f"Carica file transazioni (Excel / CSV) *",
                        type=["xlsx", "xls", "csv"],
                        key=f"cfg_upload_{key}",
                        label_visibility="collapsed",
                    )
                    if uploaded:
                        suffix = os.path.splitext(uploaded.name)[1]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                            f.write(uploaded.read())
                            st.session_state.excel_path = f.name
                            st.session_state.excel_name = uploaded.name
                        st.session_state.section_doc_names[key] = [uploaded.name]
                        st.success(f"✓ {uploaded.name}")
                    elif st.session_state.excel_name:
                        st.caption(f"📄 File caricato: {st.session_state.excel_name}")
                else:
                    uploaded_files = st.file_uploader(
                        f"Carica documenti per {sec['label']}",
                        type=["pdf", "docx", "xlsx", "xls", "csv", "txt", "md"],
                        accept_multiple_files=True,
                        key=f"cfg_upload_{key}",
                        label_visibility="collapsed",
                    )
                    if uploaded_files:
                        texts = []
                        names = []
                        for f in uploaded_files:
                            extracted = extract_text_from_file(f)
                            texts.append(f"=== {f.name} ===\n{extracted}")
                            names.append(f.name)
                        st.session_state.section_docs[key]      = "\n\n".join(texts)
                        st.session_state.section_doc_names[key] = names
                        total_chars = sum(len(t) for t in texts)
                        st.success(f"✓ {len(texts)} file caricati ({total_chars:,} caratteri estratti)")
                    elif st.session_state.section_doc_names.get(key):
                        st.caption("📄 " + ", ".join(st.session_state.section_doc_names[key]))

            # Manual notes
            notes = st.text_area(
                "Note aggiuntive (opzionale)",
                value=st.session_state.section_notes.get(key, ""),
                height=60,
                key=f"cfg_notes_{key}",
                placeholder="Aggiungi contesto, istruzioni o dati supplementari per questo agente...",
            )
            st.session_state.section_notes[key] = notes
            st.markdown("---")

        # Summary
        agent_count  = sum(1 for s in SECTIONS if st.session_state.section_modes.get(s["key"]) == "agent")
        manual_count = sum(1 for s in SECTIONS if st.session_state.section_modes.get(s["key"]) == "manual")
        docs_count   = sum(1 for s in SECTIONS if st.session_state.section_docs.get(s["key"]) or
                          (s["key"] == "transaction" and st.session_state.excel_path))

        st.markdown(
            '<div style="background:#fff5f5;border:1px solid #fecaca;border-radius:4px;'
            'padding:12px 16px;margin-bottom:16px;">'
            '<b>Riepilogo configurazione:</b> '
            + str(agent_count) + ' sezioni con agente · '
            + str(manual_count) + ' manuali · '
            + str(docs_count) + ' con documenti caricati'
            + '</div>',
            unsafe_allow_html=True,
        )

        col_back, col_fwd = st.columns([1, 3])
        with col_back:
            if st.button("← Indietro", use_container_width=True, key="cfg_back"):
                st.session_state.step = "setup"
                st.rerun()
        with col_fwd:
            if st.button("▶  Avvia Analisi", use_container_width=True, key="cfg_start"):
                st.session_state.step = "analysis"
                st.rerun()


# ── LEFT PANEL ────────────────────────────────────────────────────
def render_left():
    st.markdown(
        '<div style="font-size:0.65rem;letter-spacing:2px;color:' + RED + ';'
        'font-weight:700;margin-bottom:10px;">SEZIONI ANALISI</div>',
        unsafe_allow_html=True,
    )

    for sec in SECTIONS:
        key     = sec["key"]
        status  = sec_status(key)
        active  = st.session_state.active_section == key
        running = st.session_state.running_agent == key
        mode    = st.session_state.section_modes.get(key, "agent")

        # Parse JSON to get risk level
        content = get_content(key)
        parsed  = parse_json_result(content)
        risk_level = parsed.get("rischioComplessivo") if parsed else None

        if running:
            icon, color = "⏳", "#f59e0b"
        elif status == "completed":
            rc = get_risk_color(risk_level) if risk_level else "#22aa55"
            icon, color = "●", rc
        elif mode == "manual":
            icon, color = "✍", "#6b7280"
        elif mode == "super":
            icon, color = "⚡", RED
        else:
            icon, color = "○", "#cccccc"

        border = RED if active else ("#e8e8e8" if status != "completed" else get_risk_color(risk_level or ""))
        bg     = "#fff5f5" if active else ("#f8f8f8" if status == "completed" else "#ffffff")
        lbl_c  = "#1a1a1a" if active else ("#333" if status == "completed" else "#888")

        st.markdown(
            '<div style="padding:8px 10px;margin:2px 0;border-radius:3px;'
            'border-left:3px solid ' + border + ';background:' + bg + ';">'
            '<span style="color:' + color + ';margin-right:6px;font-size:0.75rem;">' + icon + '</span>'
            '<span style="color:#bbb;font-size:0.65rem;margin-right:6px;">' + sec["number"] + '</span>'
            '<span style="font-size:0.78rem;color:' + lbl_c + ';">' + sec["label"] + '</span>'
            + (('<br><span style="font-size:0.62rem;color:' + get_risk_color(risk_level) + ';margin-left:22px;">'
                + risk_level + '</span>') if risk_level and status == "completed" else "")
            + '</div>',
            unsafe_allow_html=True,
        )

        if st.button("→", key=f"nav_{key}", help=sec["desc"], use_container_width=True):
            st.session_state.active_section = key
            st.rerun()

    done, total = progress()
    st.markdown("---")
    st.progress(done / total, text=f"{done} / {total} sezioni completate")

    if st.button("⚙ Riconfigura", key="reconfig", use_container_width=True):
        st.session_state.step = "section_config"
        st.rerun()


# ── CENTER PANEL ──────────────────────────────────────────────────
def render_json_result(key: str, parsed: dict):
    """Display structured JSON result from an agent."""
    risk = parsed.get("rischioComplessivo", "")
    narrativa = parsed.get("narrativa") or parsed.get("narrativaCompleta") or parsed.get("sintesiEsecutiva", "")
    flags = parsed.get("flags", [])

    # Risk badge
    if risk:
        rc = get_risk_color(risk)
        st.markdown(
            '<span style="background:' + rc + ';color:white;font-size:0.75rem;'
            'font-weight:700;padding:3px 12px;border-radius:12px;">'
            'RISCHIO: ' + risk + '</span>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    # Narrative
    if narrativa:
        st.markdown(
            '<div style="background:#f8f8f8;border-left:3px solid ' + RED + ';'
            'padding:12px 16px;border-radius:3px;font-size:0.88rem;line-height:1.6;">'
            + narrativa.replace("\n", "<br>") + '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    # Flags
    if flags:
        st.markdown(
            '<div style="font-size:0.65rem;letter-spacing:1px;font-weight:700;'
            'color:' + RED + ';margin-bottom:6px;">FLAG RILEVATI</div>',
            unsafe_allow_html=True,
        )
        for f in flags:
            frc = get_risk_color(f.get("rischio", ""))
            tipo = f.get("tipo", "")
            desc = f.get("descrizione", "")
            norm = f.get("riferimentoNormativo", "") or f.get("indicatoreUIF", "")
            st.markdown(
                '<div style="background:#fff;border:1px solid #e8e8e8;'
                'border-left:3px solid ' + frc + ';border-radius:3px;'
                'padding:7px 10px;margin-bottom:5px;font-size:0.8rem;">'
                '<span style="font-weight:600;">' + tipo + '</span>'
                + (' — ' + desc if desc else '')
                + ('<span style="color:#aaa;font-size:0.72rem;margin-left:8px;">' + norm + '</span>' if norm else '')
                + '</div>',
                unsafe_allow_html=True,
            )
        st.markdown("")

    # Section-specific structured data
    with st.expander("📋 Dati strutturati (JSON completo)", expanded=False):
        st.json(parsed)


def render_center():
    client  = get_client()
    state   = st.session_state.kyc_state
    key     = st.session_state.active_section
    sec     = next(s for s in SECTIONS if s["key"] == key)
    mode    = st.session_state.section_modes.get(key, "agent")
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content)

    # Section header
    c_title, c_badge = st.columns([3, 1])
    with c_title:
        st.markdown(
            '<div><span style="color:' + RED + ';font-size:0.72rem;font-weight:700;'
            'letter-spacing:1px;">' + sec["number"] + '</span>'
            '<span style="font-size:1.1rem;font-weight:700;color:#1a1a1a;margin-left:10px;">'
            + sec["icon"] + " " + sec["label"] + '</span></div>'
            '<div style="color:#888;font-size:0.78rem;margin-top:3px;">' + sec["desc"] + '</div>',
            unsafe_allow_html=True,
        )
    with c_badge:
        if status == "completed":
            risk = (parsed.get("rischioComplessivo") if parsed else None)
            if risk:
                rc = get_risk_color(risk)
                st.markdown(
                    '<div style="text-align:right;padding-top:6px;">'
                    '<span style="background:' + rc + ';color:white;font-size:0.72rem;'
                    'font-weight:700;padding:3px 10px;border-radius:10px;">' + risk + '</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.success("✓ Completata")
        elif mode == "manual":
            st.info("✍ Manuale")
        elif mode == "super":
            st.warning("⚡ Super Agent")
        else:
            st.caption("○ Da eseguire")

    st.markdown("---")

    # ── MANUAL MODE ──────────────────────────────────────────────
    if mode == "manual":
        st.markdown(
            '<div style="font-size:0.78rem;color:#666;margin-bottom:8px;">'
            '✍️ Sezione in modalità manuale — inserisci direttamente i risultati dell\'analisi.</div>',
            unsafe_allow_html=True,
        )
        edited = st.text_area(
            "Risultati",
            value=content,
            height=450,
            key=f"manual_edit_{key}",
            label_visibility="collapsed",
            placeholder="Inserisci qui i risultati dell'analisi manuale...",
        )
        if st.button("💾 Salva risultati", key=f"save_manual_{key}"):
            st.session_state.edited_content[key] = edited
            state.add_result(key, edited)
            st.success("Salvato ✓")
            st.rerun()
        return

    # ── AGENT / SUPER MODE ────────────────────────────────────────
    # Show loaded docs info
    doc_names = st.session_state.section_doc_names.get(key, [])
    if key == "transaction" and st.session_state.excel_name:
        doc_names = [st.session_state.excel_name]

    if doc_names:
        st.markdown(
            '<div style="font-size:0.75rem;color:#22aa55;margin-bottom:8px;">'
            '📎 Documenti: ' + " · ".join(doc_names) + '</div>',
            unsafe_allow_html=True,
        )
    elif key != "final_valuation":
        web_note = " (max 3 ricerche)" if key == "reputational" else " — nessun documento caricato"
        st.markdown(
            '<div style="font-size:0.75rem;color:#f59e0b;margin-bottom:8px;">'
            '⚠️ Web search abilitata' + web_note + '</div>',
            unsafe_allow_html=True,
        )

    # Action buttons
    label_map = {
        "agent": "▶  Esegui Agente",
        "super": "⚡  Genera Valutazione Finale",
    }
    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        run_btn = st.button(label_map.get(mode, "▶ Esegui"),
                            key=f"run_{key}", use_container_width=True)
    with b2:
        rerun_btn = False
        if status == "completed":
            rerun_btn = st.button("🔄 Ri-esegui", key=f"rerun_{key}", use_container_width=True)

    # Execute agent with live streaming
    if (run_btn or rerun_btn) and client:
        st.markdown(
            '<div style="font-size:0.8rem;font-weight:600;color:' + RED + ';margin:8px 0;">'
            '⏳ Agente in elaborazione...</div>',
            unsafe_allow_html=True,
        )
        stream_area = st.empty()
        buf = {"text": ""}

        def on_token(chunk):
            buf["text"] += chunk
            display = buf["text"][-4000:] if len(buf["text"]) > 4000 else buf["text"]
            stream_area.markdown(
                '<div style="font-family:monospace;font-size:0.75rem;'
                'white-space:pre-wrap;background:#f5f5f5;border:1px solid #e8e8e8;'
                'border-radius:4px;padding:12px;max-height:400px;overflow-y:auto;">'
                + display.replace("<", "&lt;").replace(">", "&gt;")
                + '</div>',
                unsafe_allow_html=True,
            )

        try:
            run_section(key, client, on_token=on_token)
        except Exception as e:
            st.error(str(e))
        st.rerun()
    elif (run_btn or rerun_btn) and not client:
        st.error("API Key Anthropic non configurata nei Secrets.")

    st.markdown("---")

    # ── RESULT DISPLAY ────────────────────────────────────────────
    if content:
        if parsed:
            render_json_result(key, parsed)
        else:
            st.markdown(
                '<div style="font-size:0.65rem;letter-spacing:1px;color:' + RED + ';'
                'font-weight:700;margin-bottom:6px;">RISULTATO</div>',
                unsafe_allow_html=True,
            )
            # Editable text fallback
            edited = st.text_area("result", value=content, height=400,
                                  key=f"edit_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                state.add_result(key, edited)
    else:
        type_desc = {"agent": "carica documenti o usa web search",
                     "super": "sintetizza tutti gli agenti completati"}
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#ccc;">'
            '<div style="font-size:3rem;">' + sec["icon"] + '</div>'
            '<div style="color:#aaa;margin-top:12px;">Sezione non ancora eseguita</div>'
            '<div style="color:#ccc;font-size:0.78rem;margin-top:6px;">'
            + type_desc.get(mode, "") + '</div></div>',
            unsafe_allow_html=True,
        )


# ── RIGHT PANEL ───────────────────────────────────────────────────
def render_right():
    client = get_client()
    state  = st.session_state.kyc_state
    done, total = progress()

    # Case card
    st.markdown(
        '<div style="background:#f8f8f8;border-left:3px solid ' + RED + ';'
        'border-radius:3px;padding:10px 12px;margin-bottom:12px;">'
        '<div style="font-size:0.65rem;color:' + RED + ';font-weight:700;letter-spacing:1px;">CLIENTE</div>'
        '<div style="font-weight:700;color:#1a1a1a;font-size:0.95rem;">' + state.case.company_name + '</div>'
        '<div style="color:#888;font-size:0.78rem;">' + state.case.country
        + (' &nbsp;·&nbsp; <span style="color:#aaa;">' + state.case.case_id + '</span>'
           if state.case.case_id else '') + '</div></div>',
        unsafe_allow_html=True,
    )

    st.progress(done / total, text=f"Progresso: {done}/{total}")

    # Knowledge Base indicator
    if st.session_state.kb_doc_names:
        kb_count = len(st.session_state.kb_doc_names)
        kb_chars = len(st.session_state.knowledge_base)
        st.markdown(
            '<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:3px;'
            'padding:7px 10px;margin:6px 0;font-size:0.75rem;">'
            '<span style="font-weight:700;color:#0369a1;">📚 KB Normativa:</span> '
            + str(kb_count) + ' doc · ' + f'{kb_chars:,}' + ' caratteri</div>',
            unsafe_allow_html=True,
        )

    # Final Valuation score if available
    fv_content = get_content("final_valuation")
    fv_parsed  = parse_json_result(fv_content)
    if fv_parsed:
        crr = fv_parsed.get("customerRiskRating", "")
        score = fv_parsed.get("scoreFinale", "")
        if crr:
            rc = get_risk_color(crr)
            st.markdown(
                '<div style="background:' + rc + '15;border:2px solid ' + rc + ';'
                'border-radius:4px;padding:10px 14px;margin:8px 0;text-align:center;">'
                '<div style="font-size:0.65rem;font-weight:700;color:#666;letter-spacing:1px;">CUSTOMER RISK RATING</div>'
                '<div style="font-size:1.4rem;font-weight:900;color:' + rc + ';">' + crr + '</div>'
                + ('<div style="font-size:0.75rem;color:#888;">Score: ' + str(score) + '/5</div>' if score else '')
                + '</div>',
                unsafe_allow_html=True,
            )

    # Run all agent sections
    if st.button("▶▶  Esegui Tutti gli Agenti", use_container_width=True, key="run_all"):
        if not client:
            st.error("API Key non configurata.")
        else:
            auto = [s for s in SECTIONS
                    if st.session_state.section_modes.get(s["key"]) == "agent"
                    and s["key"] != "final_valuation"]
            bar = st.progress(0, text="Avvio...")
            for i, s in enumerate(auto):
                bar.progress(i / len(auto), text=f"{s['label']}...")
                try:
                    run_section(s["key"], client)
                except Exception as e:
                    st.error(f"{s['label']}: {e}")
            bar.progress(1.0, text="Completato ✓")
            st.rerun()

    st.markdown("---")

    # Agent log
    st.markdown(
        '<div style="font-size:0.65rem;letter-spacing:2px;color:' + RED + ';'
        'font-weight:700;margin-bottom:6px;">ATTIVITÀ AGENTI</div>',
        unsafe_allow_html=True,
    )
    level_colors = {"running": "#f59e0b", "done": "#22aa55", "error": "#ef4444", "super": RED}
    log_box = st.container(height=180)
    with log_box:
        if not st.session_state.agent_log:
            st.caption("Nessuna attività.")
        for entry in reversed(st.session_state.agent_log[-40:]):
            c = level_colors.get(entry["level"], "#888")
            st.markdown(
                '<div style="font-size:0.68rem;font-family:monospace;color:' + c + ';padding:1px 0;">'
                '<span style="color:#bbb;">' + entry["ts"] + '</span>'
                ' <b>' + entry["agent"] + '</b> — ' + entry["msg"] + '</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Super Agent
    st.markdown(
        '<div style="font-size:0.65rem;letter-spacing:2px;color:' + RED + ';'
        'font-weight:700;margin-bottom:6px;">⚡ SUPER AGENT</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.sa_initialized and client:
        try:
            bootstrap = {
                "role": "user",
                "content": (
                    f"Il caso è aperto per {state.case.company_name} ({state.case.country}). "
                    "Presentati brevemente come Super Agent AML e indica che sei pronto."
                ),
            }
            resp = client.messages.create(
                model="claude-opus-4-6", max_tokens=200, system=SA_PROMPT,
                messages=[bootstrap],
            )
            intro = text_from(resp.content)
            st.session_state.sa_messages   = [bootstrap, {"role": "assistant", "content": intro}]
            st.session_state.sa_initialized = True
            log("Super Agent", "Online", "super")
        except Exception as e:
            st.caption(f"Super Agent offline: {e}")

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
                    st.caption(txt[:300] + ("…" if len(txt) > 300 else ""))

    if user_msg := st.chat_input("Chiedi al Super Agent...", key="sa_input"):
        if not client:
            st.error("API Key non configurata.")
        else:
            st.session_state.sa_messages.append({"role": "user", "content": user_msg})
            log("Super Agent", f"← {user_msg[:50]}", "super")

            while True:
                try:
                    resp = client.messages.create(
                        model="claude-opus-4-6", max_tokens=2000,
                        thinking={"type": "adaptive"}, system=SA_PROMPT,
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
                    st.session_state.sa_messages.append({"role": "user", "content": tool_results})
                    continue
                else:
                    log("Super Agent", "→ risposta inviata", "super")
                    break
            st.rerun()


# ── ANALYSIS DASHBOARD ────────────────────────────────────────────
def render_analysis():
    render_header()
    left, center, right = st.columns([1.2, 3.2, 2])
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
elif st.session_state.step == "section_config":
    render_section_config()
else:
    render_analysis()
