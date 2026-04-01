"""
AML IntelliGent Platform — Streamlit Web Interface
Bain & Company Style — KYC / CDD Module
"""

import io, json, os, tempfile
from datetime import datetime
import streamlit as st
import anthropic

from kyc_platform.models import SessionState
from kyc_platform import (
    registry_agent, ubo_pep_agent, reputational_agent,
    economic_profile_agent, transaction_agent, final_valuation_agent,
)

st.set_page_config(
    page_title="AML IntelliGent | Bain & Company",
    page_icon="🔍", layout="wide",
    initial_sidebar_state="collapsed",
)

RED = "#CC0000"

st.markdown(f"""
<style>
  .stApp, [data-testid="stAppViewContainer"] {{ background:#fff; color:#1a1a1a; }}
  [data-testid="stHeader"] {{ background:#fff; border-bottom:2px solid {RED}; }}
  section[data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display:none !important; }}
  h1,h2,h3,h4 {{ color:#1a1a1a !important; }}
  label, p {{ color:#333 !important; }}
  .stTextInput input, .stNumberInput input {{
    background:#f9f9f9 !important; color:#1a1a1a !important;
    border:1px solid #d8d8d8 !important; border-radius:4px !important; }}
  .stTextArea textarea {{
    background:#f9f9f9 !important; color:#1a1a1a !important;
    border:1px solid #d8d8d8 !important; border-radius:4px !important;
    font-size:0.84rem !important; }}
  .stSelectbox > div > div {{
    background:#f9f9f9 !important; color:#1a1a1a !important;
    border:1px solid #d8d8d8 !important; }}
  .stButton > button {{
    background:{RED} !important; color:#fff !important;
    border:none !important; border-radius:4px !important;
    font-weight:600 !important; }}
  .stButton > button:hover {{ background:#aa0000 !important; }}
  .stProgress > div > div > div {{ background:{RED} !important; }}
  details summary {{ color:#444 !important; }}
  details {{ background:#f9f9f9 !important; border:1px solid #e0e0e0 !important; }}
  hr {{ border-color:#eee !important; margin:0.5rem 0 !important; }}
  ::-webkit-scrollbar {{ width:4px; }}
  ::-webkit-scrollbar-thumb {{ background:#ddd; border-radius:3px; }}
  [data-testid="stFileUploader"] {{
    background:#f9f9f9 !important; border:1px dashed #ccc !important; border-radius:4px; }}
  .stRadio label {{ color:#333 !important; }}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────
MAIN_SECTIONS = [
    {"key": "registry",         "number": "01", "icon": "🏛",
     "label": "Registry",       "full_label": "Registry & Corporate Structure",
     "desc": "Struttura societaria, catena proprietaria, governance, organi amministrativi, anomalie."},
    {"key": "ubo_pep",          "number": "02", "icon": "👤",
     "label": "UBO / PEP",      "full_label": "UBO / PEP Screening",
     "desc": "Titolari effettivi, screening PEP, catena di controllo, D.Lgs. 231/2007."},
    {"key": "reputational",     "number": "03", "icon": "📰",
     "label": "Reputazionale",  "full_label": "Reputational Analysis",
     "desc": "Adverse media, precedenti giudiziari, reati presupposto AML, misure cautelari."},
    {"key": "economic_profile", "number": "04", "icon": "📊",
     "label": "Profilo Eco.",   "full_label": "Economic Profile",
     "desc": "Bilancio, coerenza economica, indicatori UIF 2023, incongruenze patrimoniali."},
    {"key": "transaction",      "number": "05", "icon": "💳",
     "label": "Transazioni",    "full_label": "Transaction & Geographic Risk",
     "desc": "Movimenti bancari, pattern sospetti (strutturazione, layering), rischio geografico FATF."},
]
FINAL_SECTION = {
    "key": "final_valuation", "number": "06", "icon": "⚡",
    "label": "Final Val.",    "full_label": "Final Valuation — Customer Risk Rating",
    "desc": "Matrice di rischio, Customer Risk Rating e raccomandazione operativa.",
}
ALL_SECTIONS = MAIN_SECTIONS + [FINAL_SECTION]

REQUIRED_DOCS = {
    "registry":         ["Visura camerale", "Atto costitutivo / Statuto",
                         "Organigramma societario", "Modifiche recenti"],
    "ubo_pep":          ["Dichiarazione UBO", "Documenti identità soci",
                         "Estratto Registro UBO"],
    "reputational":     ["Sentenze / atti giudiziari", "Comunicati stampa",
                         "Lista persone chiave"],
    "economic_profile": ["Bilancio (3 anni)", "Conto economico",
                         "Dichiarazioni fiscali"],
    "transaction":      ["File Excel/CSV movimenti bancari"],
    "final_valuation":  [],
}

RISK_COLORS = {
    "LOW": "#22aa55", "MEDIUM": "#f59e0b", "HIGH": "#ef4444", "CRITICAL": "#7c3aed",
    "BASSO": "#22aa55", "MEDIO": "#f59e0b", "MEDIO-ALTO": "#f97316",
    "ALTO": "#ef4444", "CRITICO": "#7c3aed",
}

# ── Session state ─────────────────────────────────────────────────
DEFAULTS = {
    "step": "setup", "kyc_state": None,
    "active_section": "registry",
    "edited_content": {}, "agent_log": [],
    "section_modes": {}, "section_docs": {},
    "section_doc_names": {}, "section_notes": {},
    "excel_path": None, "excel_name": None,
    "running_agent": None,
    "knowledge_base": "", "kb_doc_names": [],
    "all_docs": "", "all_doc_names": [],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
if st.session_state.kyc_state is None:
    st.session_state.kyc_state = SessionState()
for sec in ALL_SECTIONS:
    if sec["key"] not in st.session_state.section_modes:
        st.session_state.section_modes[sec["key"]] = "agent"

# ── Helpers ───────────────────────────────────────────────────────
def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try: key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception: pass
    return key

def get_client():
    k = get_api_key()
    return anthropic.Anthropic(api_key=k) if k else None

def sec_status(key):
    if st.session_state.edited_content.get(key): return "completed"
    return "completed" if st.session_state.kyc_state.has_result(key) else "empty"

def get_content(key):
    return (st.session_state.edited_content.get(key)
            or st.session_state.kyc_state.results.get(key, ""))

def log_event(agent, msg, level="running"):
    st.session_state.agent_log.append(
        {"ts": datetime.now().strftime("%H:%M:%S"), "agent": agent, "msg": msg, "level": level})

def main_progress():
    done = sum(1 for s in MAIN_SECTIONS if sec_status(s["key"]) == "completed")
    return done, len(MAIN_SECTIONS)

def text_from(content):
    if isinstance(content, str): return content
    if isinstance(content, list):
        return "\n".join(
            (b.text if hasattr(b, "text") else b.get("text", ""))
            for b in content
            if (hasattr(b, "type") and b.type == "text")
               or (isinstance(b, dict) and b.get("type") == "text"))
    return ""

def extract_text_from_file(uploaded_file) -> str:
    name = uploaded_file.name
    ext  = os.path.splitext(name)[1].lower()
    data = uploaded_file.read()
    try:
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n\n".join(p.extract_text() or "" for p in reader.pages).strip()
        elif ext == ".docx":
            import docx as docxlib
            doc = docxlib.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext in (".xlsx", ".xls"):
            import pandas as pd
            dfs = pd.read_excel(io.BytesIO(data), sheet_name=None)
            return "\n\n".join(f"[{sh}]\n{df.head(300).to_string(index=False)}" for sh, df in dfs.items())
        elif ext == ".csv":
            import pandas as pd
            return pd.read_csv(io.BytesIO(data)).head(300).to_string(index=False)
        elif ext in (".txt", ".md"):
            return data.decode("utf-8", errors="replace")
        else:
            return f"[Formato non supportato: {ext}]"
    except Exception as e:
        return f"[Errore lettura {name}: {e}]"

def parse_json_result(text: str):
    if not text: return None
    try:
        s = text.find("{"); e = text.rfind("}") + 1
        if s >= 0 and e > s: return json.loads(text[s:e])
    except (json.JSONDecodeError, ValueError): pass
    return None

def get_risk_color(level: str) -> str:
    return RISK_COLORS.get((level or "").upper(), "#888")

def run_section(key, client, on_token=None):
    state   = st.session_state.kyc_state
    company = state.case.company_name
    country = state.case.country
    # Use section-specific docs if present, otherwise fall back to the shared pool
    docs_text  = (st.session_state.section_docs.get(key, "")
                  or st.session_state.get("all_docs", ""))
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
    use_web = not bool(docs_text)
    sec = next(s for s in ALL_SECTIONS if s["key"] == key)
    st.session_state.running_agent = key
    log_event(sec["label"], f"Avvio ({'documenti' if docs_text else 'web search' if use_web else 'note'})...")
    try:
        if key == "registry":
            result = registry_agent.run(client, company, country, manual_ctx,
                                        show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "ubo_pep":
            result = ubo_pep_agent.run(client, company, country, manual_ctx,
                                       show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "reputational":
            result = reputational_agent.run(client, company, country, "", manual_ctx,
                                            show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "economic_profile":
            result = economic_profile_agent.run(client, company, country, manual_ctx,
                                                show_output=False, on_token=on_token, use_web_search=use_web)
        elif key == "transaction":
            path = st.session_state.excel_path or ""
            if not path: raise ValueError("Nessun file Excel/CSV caricato.")
            result = transaction_agent.run(client, path, company, manual_ctx,
                                           show_output=False, on_token=on_token)
        elif key == "final_valuation":
            result = final_valuation_agent.run(client, company, state.results, manual_ctx,
                                               show_output=False, on_token=on_token)
        else:
            raise ValueError(f"Sezione sconosciuta: {key}")
        state.add_result(key, result)
        st.session_state.edited_content[key] = result
        log_event(sec["label"], "Completato ✓", "done")
    except Exception as e:
        log_event(sec["label"], f"Errore: {e}", "error")
        raise
    finally:
        st.session_state.running_agent = None


# ── Header ────────────────────────────────────────────────────────
def render_header():
    state = st.session_state.kyc_state
    h_left, h_right = st.columns([6, 1])
    with h_left:
        if st.session_state.step == "analysis" and state.case.company_name:
            done, total = main_progress()
            rc = "#22aa55" if done == total else RED
            st.markdown(
                '<div style="padding:6px 0 10px;border-bottom:2px solid '+RED+';margin-bottom:10px;">'
                '<span style="font-size:0.9rem;font-weight:900;letter-spacing:3px;color:#1a1a1a;">BAIN &amp; COMPANY</span>'
                '<span style="color:#ccc;margin:0 10px;">|</span>'
                '<span style="font-size:0.78rem;color:#888;">AML IntelliGent Platform · KYC/CDD</span>'
                '<span style="color:#ddd;margin:0 10px;">|</span>'
                '<span style="color:#1a1a1a;font-size:0.9rem;font-weight:600;">'+state.case.company_name+'</span>'
                '<span style="color:#aaa;font-size:0.72rem;margin-left:8px;">'+(state.case.case_id or '')+'</span>'
                '<span style="background:'+rc+';color:#fff;font-size:0.62rem;padding:2px 8px;'
                'border-radius:10px;margin-left:10px;">'+str(done)+'/'+str(total)+'</span>'
                '</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="padding:6px 0 10px;border-bottom:2px solid '+RED+';margin-bottom:10px;">'
                '<span style="font-size:0.9rem;font-weight:900;letter-spacing:3px;color:#1a1a1a;">BAIN &amp; COMPANY</span>'
                '<span style="color:#ccc;margin:0 10px;">|</span>'
                '<span style="font-size:0.78rem;color:#888;">AML IntelliGent Platform · KYC/CDD</span>'
                '</div>', unsafe_allow_html=True)
    with h_right:
        st.markdown('<div style="text-align:right;padding-top:4px;font-size:0.65rem;color:#bbb;">claude-opus-4-6</div>',
                    unsafe_allow_html=True)

# ── STEP 1: SETUP ────────────────────────────────────────────────
def render_setup():
    render_header()
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            '<div style="text-align:center;padding:20px 0 16px;">'
            '<div style="font-size:1.7rem;font-weight:700;color:#1a1a1a;">Nuova Analisi Controparte</div>'
            '<div style="color:#888;margin-top:5px;font-size:0.85rem;">'
            'Inserisci i dati della controparte e carica la knowledge base normativa</div></div>',
            unsafe_allow_html=True)
        if not get_api_key():
            st.error("⚠️  API Key Anthropic non trovata — aggiungi ANTHROPIC_API_KEY nei Secrets")
        st.markdown("#### Controparte")
        company = st.text_input("Ragione Sociale *", placeholder="es. Meridian Capital S.r.l.")
        c1, c2 = st.columns(2)
        with c1: country = st.text_input("Paese *", placeholder="es. Italia")
        with c2: sector  = st.text_input("Settore", placeholder="es. Wealth Management")
        c3, c4 = st.columns(2)
        with c3: case_id = st.text_input("Case ID", placeholder="es. AML-2026-0341")
        with c4: analyst = st.text_input("Analista", placeholder="es. M. Rossi")
        st.markdown("---")
        st.markdown("#### 📚 Knowledge Base Normativa")
        st.markdown('<div style="font-size:0.78rem;color:#888;margin-bottom:8px;">'
                    'FATF guidelines, circolari UIF, D.Lgs. 231/2007, liste sanzioni, policy AML interne.</div>',
                    unsafe_allow_html=True)
        kb_files = st.file_uploader("KB", type=["pdf","docx","txt","md","csv"],
                                    accept_multiple_files=True, key="kb_upload",
                                    label_visibility="collapsed")
        if kb_files:
            texts, names = [], []
            for f in kb_files:
                texts.append(f"=== {f.name} ===\n{extract_text_from_file(f)}")
                names.append(f.name)
            st.session_state.knowledge_base = "\n\n".join(texts)
            st.session_state.kb_doc_names   = names
            st.success(f"✓ {len(texts)} file · {len(st.session_state.knowledge_base):,} caratteri")
        elif st.session_state.kb_doc_names:
            st.info("📚 " + " · ".join(st.session_state.kb_doc_names))
        st.markdown("---")
        if st.button("Continua →  Configura Sezioni", use_container_width=True):
            if not company.strip() or not country.strip():
                st.error("Ragione Sociale e Paese sono obbligatori.")
            elif not get_api_key():
                st.error("Configura ANTHROPIC_API_KEY nei Secrets.")
            else:
                s = st.session_state.kyc_state
                s.case.company_name = company.strip()
                s.case.country      = country.strip()
                s.case.sector       = sector.strip()
                s.case.case_id      = case_id.strip() or f"AML-{datetime.now().strftime('%Y%m%d-%H%M')}"
                log_event("Sistema", f"Caso aperto: {company} ({country})", "super")
                st.session_state.step = "section_config"
                st.rerun()

# ── STEP 2: SECTION CONFIG ───────────────────────────────────────
def render_section_config():
    render_header()
    state = st.session_state.kyc_state
    _, col, _ = st.columns([0.2, 3.6, 0.2])
    with col:
        st.markdown(
            '<div style="padding:4px 0 14px;">'
            '<div style="font-size:1.25rem;font-weight:700;color:#1a1a1a;">'
            'Configura Analisi — ' + state.case.company_name + '</div>'
            '<div style="color:#888;font-size:0.82rem;margin-top:3px;">'
            'Scegli la modalità per ogni sezione, poi carica tutta la documentazione disponibile</div></div>',
            unsafe_allow_html=True)

        # ── Mode selection per section ────────────────────────────
        for sec in MAIN_SECTIONS:
            key  = sec["key"]
            mode = st.session_state.section_modes.get(key, "agent")
            left_c, right_c = st.columns([3, 1.5])
            with left_c:
                st.markdown(
                    '<div style="display:flex;align-items:center;padding:6px 0;">'
                    '<span style="color:' + RED + ';font-size:0.62rem;font-weight:700;'
                    'letter-spacing:1px;width:22px;">' + sec["number"] + '</span>'
                    '<span style="font-size:0.88rem;font-weight:600;color:#1a1a1a;margin-left:6px;">'
                    + sec["icon"] + ' ' + sec["full_label"] + '</span>'
                    '<span style="font-size:0.72rem;color:#bbb;margin-left:10px;">'
                    + sec["desc"] + '</span></div>',
                    unsafe_allow_html=True)
            with right_c:
                mode_radio = st.radio(
                    "m", ["🤖  Agente", "✍️  Manuale"],
                    index=0 if mode == "agent" else 1,
                    key=f"cfg_{key}", horizontal=True,
                    label_visibility="collapsed")
                st.session_state.section_modes[key] = "agent" if "Agente" in mode_radio else "manual"

        # ── Single document upload box ────────────────────────────
        st.markdown("---")
        st.markdown(
            '<div style="font-size:0.82rem;font-weight:600;color:#1a1a1a;margin-bottom:4px;">'
            '📎 Carica i documenti della controparte</div>'
            '<div style="font-size:0.75rem;color:#999;margin-bottom:10px;">'
            'Puoi caricare tutti i file in una volta sola (PDF, Word, Excel, CSV, TXT). '
            'I file Excel/CSV verranno usati anche per l\'analisi transazionale.</div>',
            unsafe_allow_html=True)

        # Show already loaded
        all_names = st.session_state.get("all_doc_names", [])
        if st.session_state.excel_name and st.session_state.excel_name not in all_names:
            all_names = all_names + [st.session_state.excel_name]
        if all_names:
            tags = "".join(
                f'<span style="display:inline-block;background:#f0fff4;border:1px solid #bbf7d0;'
                f'border-radius:12px;padding:2px 10px;font-size:0.7rem;color:#166534;margin:2px;">✅ {n}</span>'
                for n in all_names)
            st.markdown(
                '<div style="margin-bottom:8px;line-height:2;">' + tags + '</div>',
                unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Documenti",
            type=["pdf", "docx", "xlsx", "xls", "csv", "txt", "md"],
            accept_multiple_files=True,
            key="cfg_all_docs",
            label_visibility="collapsed")

        if uploaded:
            texts, names = [], []
            excel_file = None
            for f in uploaded:
                ext = os.path.splitext(f.name)[1].lower()
                extracted = extract_text_from_file(f)
                texts.append(f"=== {f.name} ===\n{extracted}")
                names.append(f.name)
                # Save Excel/CSV as transaction file
                if ext in (".xlsx", ".xls", ".csv"):
                    excel_file = (f.name, ext, f)
            # Store combined docs accessible to all agents
            st.session_state.all_docs      = "\n\n".join(texts)
            st.session_state.all_doc_names = names
            # Also populate per-section docs for left panel tracker
            for sec in MAIN_SECTIONS:
                if sec["key"] != "transaction":
                    st.session_state.section_docs[sec["key"]]      = st.session_state.all_docs
                    st.session_state.section_doc_names[sec["key"]] = names
            # Handle Excel for transaction
            if excel_file:
                fname, ext, fobj = excel_file
                fobj.seek(0)
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(fobj.read())
                    st.session_state.excel_path = tmp.name
                    st.session_state.excel_name = fname
                st.session_state.section_doc_names["transaction"] = [fname]
            total_chars = len(st.session_state.all_docs)
            st.success(f"✓ {len(names)} file caricati · {total_chars:,} caratteri estratti")
            st.rerun()

        st.markdown("---")
        cb, cf = st.columns([1, 3])
        with cb:
            if st.button("← Indietro", use_container_width=True, key="cfg_back"):
                st.session_state.step = "setup"; st.rerun()
        with cf:
            if st.button("▶  Avvia Analisi Controparte", use_container_width=True, key="cfg_go"):
                st.session_state.active_section = "registry"
                st.session_state.step = "analysis"; st.rerun()


# ── TOP NAVIGATOR ────────────────────────────────────────────────
def render_section_nav():
    active = st.session_state.active_section
    done_main, _ = main_progress()
    cols = st.columns(len(MAIN_SECTIONS) + 1)

    for i, sec in enumerate(MAIN_SECTIONS):
        key       = sec["key"]
        status    = sec_status(key)
        is_active = active == key
        running   = st.session_state.running_agent == key

        parsed = parse_json_result(get_content(key)) if status == "completed" else None
        risk   = parsed.get("rischioComplessivo","") if parsed else ""
        rc     = get_risk_color(risk)

        if running:
            dot = '<span style="font-size:0.7rem;animation:spin 1s linear infinite;">⏳</span>'
            sub = '<span style="font-size:0.58rem;color:#f59e0b;">elaborazione...</span>'
        elif status == "completed":
            dot = f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{rc};"></span>'
            sub = f'<span style="font-size:0.58rem;font-weight:700;color:{rc};">{risk or "✓"}</span>'
        else:
            dot = f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#e0e0e0;"></span>'
            sub = '<span style="font-size:0.58rem;color:#ccc;">—</span>'

        if is_active:
            card = (f"background:#fff;border:2px solid {RED};border-radius:8px;"
                    f"padding:8px 2px 6px;box-shadow:0 2px 10px rgba(204,0,0,0.15);")
            nc = RED; fw = "700"; lc = "#1a1a1a"
        else:
            card = "background:#f7f7f7;border:1.5px solid #e8e8e8;border-radius:8px;padding:8px 2px 6px;"
            nc = "#bbb"; fw = "500"; lc = "#777"

        with cols[i]:
            st.markdown(
                f'<div style="{card}text-align:center;margin:0 1px;">'
                f'<div style="font-size:0.55rem;font-weight:700;color:{nc};letter-spacing:1px;">{sec["number"]}</div>'
                f'<div style="font-size:0.75rem;font-weight:{fw};color:{lc};margin:2px 0;">{sec["icon"]} {sec["label"]}</div>'
                f'<div>{dot} {sub}</div></div>',
                unsafe_allow_html=True)
            if st.button("‎", key=f"nav_{key}", use_container_width=True, help=sec["full_label"]):
                st.session_state.active_section = key; st.rerun()

    # Final Valuation pill
    fv_key    = "final_valuation"
    fv_status = sec_status(fv_key)
    is_active = active == fv_key
    all_done  = done_main == len(MAIN_SECTIONS)
    parsed_fv = parse_json_result(get_content(fv_key)) if fv_status == "completed" else None
    crr = parsed_fv.get("customerRiskRating","") if parsed_fv else ""
    rc_fv = get_risk_color(crr)

    if fv_status == "completed":
        dot = f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{rc_fv};"></span>'
        sub = f'<span style="font-size:0.58rem;font-weight:700;color:{rc_fv};">{crr}</span>'
    elif all_done:
        dot = f'<span style="color:{RED};font-size:0.75rem;">⚡</span>'
        sub = f'<span style="font-size:0.58rem;color:{RED};">Pronta</span>'
    else:
        dot = '<span style="color:#e0e0e0;font-size:0.75rem;">⚡</span>'
        sub = '<span style="font-size:0.58rem;color:#ddd;">Locked</span>'

    if is_active:
        card = f"background:#fff;border:2px solid {RED};border-radius:8px;padding:8px 2px 6px;box-shadow:0 2px 10px rgba(204,0,0,0.15);"
        nc = RED; fw = "700"; lc = "#1a1a1a"
    elif all_done or fv_status == "completed":
        card = f"background:#fffaf5;border:1.5px solid #ffd0a0;border-radius:8px;padding:8px 2px 6px;"
        nc = "#f97316"; fw = "600"; lc = "#1a1a1a"
    else:
        card = "background:#f7f7f7;border:1.5px solid #e8e8e8;border-radius:8px;padding:8px 2px 6px;opacity:0.45;"
        nc = "#ccc"; fw = "400"; lc = "#ccc"

    with cols[-1]:
        st.markdown(
            f'<div style="{card}text-align:center;margin:0 1px;">'
            f'<div style="font-size:0.55rem;font-weight:700;color:{nc};letter-spacing:1px;">{FINAL_SECTION["number"]}</div>'
            f'<div style="font-size:0.75rem;font-weight:{fw};color:{lc};margin:2px 0;">⚡ Final Val.</div>'
            f'<div>{dot} {sub}</div></div>',
            unsafe_allow_html=True)
        if st.button("‎", key="nav_fv", use_container_width=True,
                     help="Final Valuation — Customer Risk Rating",
                     disabled=not (all_done or fv_status == "completed")):
            st.session_state.active_section = fv_key; st.rerun()

    st.markdown('<hr style="margin:6px 0 10px;border-color:#eee;">', unsafe_allow_html=True)

# ── LEFT: DOC TRACKER ────────────────────────────────────────────
def render_left():
    key = st.session_state.active_section

    st.markdown(
        '<div style="font-size:0.6rem;font-weight:700;letter-spacing:2px;'
        'color:'+RED+';margin-bottom:10px;">DOCUMENTAZIONE</div>',
        unsafe_allow_html=True)

    for sec in MAIN_SECTIONS:
        skey     = sec["key"]
        is_active= skey == key
        status   = sec_status(skey)
        loaded   = st.session_state.section_doc_names.get(skey, [])
        if skey == "transaction" and st.session_state.excel_name:
            loaded = [st.session_state.excel_name]
        req_docs = REQUIRED_DOCS.get(skey, [])
        mode     = st.session_state.section_modes.get(skey, "agent")

        # Section title line
        parsed = parse_json_result(get_content(skey)) if status == "completed" else None
        risk   = parsed.get("rischioComplessivo","") if parsed else ""
        rc     = get_risk_color(risk)
        running = st.session_state.running_agent == skey

        if running:
            si = "⏳"; sc = "#f59e0b"
        elif status == "completed":
            si = "●"; sc = rc
        elif mode == "manual":
            si = "✍"; sc = "#888"
        else:
            si = "○"; sc = "#ccc"

        border_l = f"2px solid {RED}" if is_active else ("2px solid "+rc if status == "completed" else "2px solid #eee")
        bg = "#fff5f5" if is_active else "#fff"

        st.markdown(
            '<div style="border-left:'+border_l+';background:'+bg+';'
            'padding:5px 8px;margin-bottom:2px;border-radius:0 4px 4px 0;">'
            '<span style="font-size:0.65rem;color:'+sc+';">'+si+'</span>'
            '<span style="font-size:0.62rem;color:#bbb;margin:0 4px;">'+sec["number"]+'</span>'
            '<span style="font-size:0.73rem;font-weight:'+("700" if is_active else "500")+';color:'+("#1a1a1a" if is_active else "#555")+';">'
            +sec["label"]+'</span>'
            +(f' <span style="font-size:0.58rem;color:{rc};font-weight:700;">{risk}</span>' if risk else '')
            +(f' <span style="font-size:0.58rem;color:#aaa;">[Manuale]</span>' if mode == "manual" else '')
            +'</div>',
            unsafe_allow_html=True)

        # Click to navigate
        if st.button("‎", key=f"left_nav_{skey}", use_container_width=True, help=sec["full_label"]):
            st.session_state.active_section = skey; st.rerun()

        # Doc list
        if req_docs:
            for r in req_docs:
                matched = any(r.lower().split()[0] in n.lower() for n in loaded) if loaded else False
                icon = "✅" if matched else "○"
                col_ = "#22aa55" if matched else "#ccc"
                st.markdown(
                    '<div style="font-size:0.68rem;padding:1px 0 1px 16px;">'
                    '<span style="color:'+col_+';">'+icon+'</span> '
                    '<span style="color:'+('#333' if matched else '#bbb')+';">'+r+'</span></div>',
                    unsafe_allow_html=True)
            if loaded:
                for n in loaded:
                    if not any(r.lower().split()[0] in n.lower() for r in req_docs):
                        st.markdown(
                            '<div style="font-size:0.65rem;padding:1px 0 1px 16px;color:#22aa55;">✅ '+n+'</div>',
                            unsafe_allow_html=True)
        st.markdown('<div style="margin-bottom:6px;"></div>', unsafe_allow_html=True)

    # KB indicator
    if st.session_state.kb_doc_names:
        st.markdown('<hr style="margin:6px 0;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.6rem;font-weight:700;letter-spacing:2px;color:#0369a1;margin-bottom:4px;">📚 KNOWLEDGE BASE</div>',
                    unsafe_allow_html=True)
        for n in st.session_state.kb_doc_names:
            st.markdown('<div style="font-size:0.68rem;color:#0369a1;">✓ '+n+'</div>', unsafe_allow_html=True)

    st.markdown('<hr style="margin:8px 0;">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⚙", key="reconfig", use_container_width=True, help="Riconfigura sezioni"):
            st.session_state.step = "section_config"; st.rerun()
    with c2:
        if st.button("✕", key="new_case", use_container_width=True, help="Nuovo caso"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()


# ── RIGHT: DYNAMIC SECTION POPULATION ───────────────────────────
def render_right():
    state = st.session_state.kyc_state
    done, total = main_progress()

    st.markdown(
        '<div style="font-size:0.6rem;font-weight:700;letter-spacing:2px;'
        'color:'+RED+';margin-bottom:8px;">NOTA PARERE — IN COMPILAZIONE</div>',
        unsafe_allow_html=True)

    for sec in MAIN_SECTIONS:
        key     = sec["key"]
        status  = sec_status(key)
        running = st.session_state.running_agent == key
        content = get_content(key)
        parsed  = parse_json_result(content) if content else None
        risk    = parsed.get("rischioComplessivo","") if parsed else ""
        rc      = get_risk_color(risk)
        mode    = st.session_state.section_modes.get(key, "agent")

        if running:
            bg = "#fffbeb"; border = "#f59e0b"
            icon_h = '<span style="font-size:0.7rem;">⏳</span>'
            body_h = '<div style="font-size:0.68rem;color:#f59e0b;margin-top:3px;">elaborazione in corso...</div>'
        elif status == "completed":
            bg = "#f8fff8"; border = rc
            icon_h = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{rc};"></span>'
            narrativa = (parsed.get("narrativa","") if parsed else content) or ""
            excerpt   = narrativa[:130].replace("<","&lt;").replace(">","&gt;")
            if len(narrativa) > 130: excerpt += "…"
            evidenze  = parsed.get("principaliEvidenze",[]) if parsed else []
            ev_count  = len(evidenze)
            body_h = (
                f'<div style="font-size:0.7rem;color:#444;margin-top:4px;line-height:1.45;">{excerpt}</div>'
                + (f'<div style="font-size:0.62rem;color:{rc};margin-top:3px;font-weight:600;">'
                   f'{ev_count} evidenz{"a" if ev_count==1 else "e"} rilevat{"a" if ev_count==1 else "e"}</div>'
                   if ev_count else '')
            )
        else:
            bg = "#fafafa"; border = "#e8e8e8"
            icon_h = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#e0e0e0;"></span>'
            mode_label = "Manuale" if mode == "manual" else "In attesa"
            body_h = f'<div style="font-size:0.68rem;color:#ccc;margin-top:3px;">{mode_label}</div>'

        st.markdown(
            '<div style="background:'+bg+';border:1px solid '+border+';border-left:3px solid '+border+';'
            'border-radius:0 5px 5px 0;padding:8px 10px;margin-bottom:5px;cursor:pointer;">'
            '<div style="display:flex;align-items:center;gap:6px;">'
            +icon_h+
            '<span style="font-size:0.62rem;color:#bbb;">'+sec["number"]+'</span>'
            '<span style="font-size:0.74rem;font-weight:600;color:#1a1a1a;">'+sec["icon"]+' '+sec["label"]+'</span>'
            +(f'<span style="margin-left:auto;font-size:0.6rem;font-weight:700;color:{rc};">{risk}</span>' if risk else '')
            +'</div>'
            +body_h+
            '</div>', unsafe_allow_html=True)

        if st.button("‎", key=f"rp_nav_{key}", use_container_width=True, help=f"Vai a {sec['label']}"):
            st.session_state.active_section = key; st.rerun()

    # Final Valuation
    fv_status = sec_status("final_valuation")
    all_done  = done == total
    fv_parsed = parse_json_result(get_content("final_valuation")) if fv_status == "completed" else None
    crr = fv_parsed.get("customerRiskRating","") if fv_parsed else ""
    rc_fv = get_risk_color(crr)

    if fv_status == "completed":
        bg = f"{rc_fv}18"; border = rc_fv
        body_h = (
            '<div style="text-align:center;margin-top:4px;">'
            f'<span style="font-size:1.1rem;font-weight:900;color:{rc_fv};">{crr}</span><br>'
            '<span style="font-size:0.58rem;color:#888;">Customer Risk Rating</span></div>'
        )
    elif all_done:
        bg = "#fff8f5"; border = "#f97316"
        body_h = f'<div style="font-size:0.68rem;color:{RED};margin-top:3px;">⚡ Pronta per la generazione</div>'
    else:
        bg = "#fafafa"; border = "#e8e8e8"
        body_h = '<div style="font-size:0.68rem;color:#ccc;margin-top:3px;">🔒 Completa le sezioni precedenti</div>'

    st.markdown(
        '<div style="background:'+bg+';border:1px solid '+border+';border-left:3px solid '+border+';'
        'border-radius:0 5px 5px 0;padding:8px 10px;margin-bottom:5px;">'
        '<div style="display:flex;align-items:center;gap:6px;">'
        '<span style="font-size:0.62rem;color:#bbb;">'+FINAL_SECTION["number"]+'</span>'
        '<span style="font-size:0.74rem;font-weight:600;color:#1a1a1a;">⚡ Final Valuation</span></div>'
        +body_h+'</div>', unsafe_allow_html=True)
    if st.button("‎", key="rp_nav_fv", use_container_width=True,
                 help="Final Valuation",
                 disabled=not (all_done or fv_status == "completed")):
        st.session_state.active_section = "final_valuation"; st.rerun()

    # Run all button
    if done < total:
        st.markdown('<hr style="margin:8px 0;">', unsafe_allow_html=True)
        if st.button("▶▶  Esegui Tutti gli Agenti", use_container_width=True, key="run_all"):
            client = get_client()
            if client:
                auto = [s for s in MAIN_SECTIONS if st.session_state.section_modes.get(s["key"]) == "agent"]
                for s in auto:
                    try: run_section(s["key"], client)
                    except Exception as e: st.error(f"{s['label']}: {e}")
                st.rerun()


# ── RESULT DISPLAY (prose-only) ──────────────────────────────────
def render_prose_result(key: str, parsed: dict):
    """Displays agent result as professional prose — no raw JSON."""
    risk      = parsed.get("rischioComplessivo","") or parsed.get("customerRiskRating","")
    narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                 or parsed.get("sintesiEsecutiva","") or "")
    evidenze  = parsed.get("principaliEvidenze", [])
    flags     = parsed.get("flags", [])

    # Risk badge + raccomandazione
    if risk:
        rc = get_risk_color(risk)
        racc = parsed.get("raccomandazione","")
        racc_str = ""
        if isinstance(racc, dict):
            acc = racc.get("accettazione","")
            adv = racc.get("livelloAdeguataVerifica","")
            freq = racc.get("frequenzaMonitoraggio","")
            parts = [x for x in [acc, adv, freq] if x]
            if parts: racc_str = " &nbsp;·&nbsp; ".join(parts)
        elif isinstance(racc, str) and racc:
            racc_str = racc
        st.markdown(
            '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:16px;">'
            '<span style="background:'+rc+';color:#fff;font-size:0.82rem;font-weight:700;'
            'padding:5px 18px;border-radius:20px;">⬤ RISCHIO: '+risk+'</span>'
            +(f'<span style="font-size:0.76rem;color:#777;">{racc_str}</span>' if racc_str else '')
            +'</div>', unsafe_allow_html=True)

    # Risk matrix (Final Valuation only)
    mx = parsed.get("matriceRischio")
    if mx:
        labels = [("identitaStruttura","Identità / Struttura"),
                  ("reputazionale","Reputazionale"),
                  ("economico","Economico"),
                  ("transazionale","Transazionale"),
                  ("geografico","Geografico")]
        cols = st.columns(5)
        for i, (dim, lbl) in enumerate(labels):
            val = mx.get(dim,{})
            sc  = int(val.get("score",0)) if isinstance(val,dict) else 0
            bc  = RED if sc >= 4 else "#f59e0b" if sc == 3 else "#22aa55"
            motiv = val.get("motivazione","") if isinstance(val,dict) else ""
            with cols[i]:
                st.markdown(
                    '<div style="text-align:center;background:#f8f8f8;border-radius:6px;'
                    'padding:10px 4px;border:1px solid #eee;" title="'+motiv+'">'
                    '<div style="font-size:0.58rem;color:#999;margin-bottom:3px;">'+lbl+'</div>'
                    '<div style="font-size:1.5rem;font-weight:900;color:'+bc+';">'+str(sc)+'<span style="font-size:0.55rem;color:#ccc;">/5</span></div>'
                    '<div style="margin:4px 8px 0;height:3px;background:#eee;border-radius:2px;">'
                    '<div style="width:'+str(sc*20)+'%;height:100%;background:'+bc+';border-radius:2px;"></div>'
                    '</div></div>', unsafe_allow_html=True)
        st.markdown("")

    # Narrativa principale — border color by risk level
    if narrativa:
        risk_upper = (risk or "").upper()
        if risk_upper in ("CRITICAL", "CRITICO", "ALTO", "HIGH"):
            border_c = "#ef4444"; bg_c = "#fff8f8"
            label_c  = "#ef4444"; label_txt = "ANALISI — CRITICITÀ RILEVATE"
        elif risk_upper in ("MEDIO-ALTO", "MEDIUM"):
            border_c = "#f59e0b"; bg_c = "#fffdf5"
            label_c  = "#f59e0b"; label_txt = "ANALISI — DA APPROFONDIRE"
        else:
            border_c = "#22aa55"; bg_c = "#f8fff8"
            label_c  = "#22aa55"; label_txt = "ANALISI — PROFILO NELLA NORMA"

        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;'
            'color:' + label_c + ';margin:12px 0 6px;">' + label_txt + '</div>',
            unsafe_allow_html=True)
        st.markdown(
            '<div style="background:' + bg_c + ';border-left:4px solid ' + border_c + ';'
            'padding:16px 20px;border-radius:0 6px 6px 0;font-size:0.87rem;'
            'line-height:1.75;color:#1a1a1a;margin-bottom:16px;">'
            + narrativa.replace("\n", "<br>") + '</div>',
            unsafe_allow_html=True)

    # Principali evidenze
    if evidenze:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;color:#555;margin:8px 0 8px;">PRINCIPALI EVIDENZE DI ATTENZIONE</div>',
            unsafe_allow_html=True)
        level_styles = {
            "CRITICO":    ("#fef2f2","#ef4444","●"),
            "ANOMALIA":   ("#fffbeb","#f59e0b","▲"),
            "ATTENZIONE": ("#f0f9ff","#0ea5e9","◆"),
        }
        for ev in evidenze:
            lvl  = (ev.get("livello") or "ATTENZIONE").upper()
            etxt = ev.get("evidenza","")
            ntxt = ev.get("normativa","")
            bg_e, col_e, ico_e = level_styles.get(lvl, level_styles["ATTENZIONE"])
            st.markdown(
                '<div style="background:'+bg_e+';border-left:3px solid '+col_e+';'
                'border-radius:0 5px 5px 0;padding:8px 12px;margin-bottom:6px;">'
                '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
                '<span style="font-size:0.8rem;color:#1a1a1a;line-height:1.5;">'
                '<span style="color:'+col_e+';margin-right:5px;">'+ico_e+'</span>'+etxt+'</span>'
                '<span style="font-size:0.6rem;font-weight:700;color:'+col_e+';white-space:nowrap;'
                'padding:1px 6px;border-radius:8px;border:1px solid '+col_e+';">'+lvl+'</span></div>'
                +(f'<div style="font-size:0.68rem;color:#888;margin-top:4px;margin-left:16px;">📎 {ntxt}</div>'
                  if ntxt else '')
                +'</div>', unsafe_allow_html=True)

    # Flags
    if flags:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;color:#555;margin:8px 0 6px;">FLAG AML</div>',
            unsafe_allow_html=True)
        for f in flags:
            frc  = get_risk_color(f.get("rischio",""))
            tipo = f.get("tipo",""); desc = f.get("descrizione","")
            norm = f.get("riferimentoNormativo","") or f.get("indicatoreUIF","")
            st.markdown(
                '<div style="border-left:3px solid '+frc+';padding:5px 10px;margin-bottom:4px;background:#fff;'
                'border-radius:0 4px 4px 0;">'
                '<span style="font-size:0.78rem;font-weight:600;">'+tipo+'</span>'
                +(f'<span style="font-size:0.76rem;color:#555;"> — {desc}</span>' if desc else '')
                +(f'<span style="font-size:0.66rem;color:#bbb;margin-left:6px;">📎 {norm}</span>' if norm else '')
                +'</div>', unsafe_allow_html=True)


# ── CENTER: SECTION DETAIL ───────────────────────────────────────
def render_center_section():
    client  = get_client()
    state   = st.session_state.kyc_state
    key     = st.session_state.active_section
    sec     = next(s for s in ALL_SECTIONS if s["key"] == key)
    mode    = st.session_state.section_modes.get(key, "agent")
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content)
    risk    = (parsed.get("rischioComplessivo","") or parsed.get("customerRiskRating","")) if parsed else ""

    # ── Section header ────────────────────────────────────────────
    risk_badge = ""
    if risk:
        rc = get_risk_color(risk)
        risk_badge = (f'<span style="background:{rc};color:#fff;font-size:0.7rem;font-weight:700;'
                      f'padding:3px 12px;border-radius:10px;margin-left:10px;">{risk}</span>')
    st.markdown(
        '<div style="margin-bottom:12px;">'
        '<span style="color:'+RED+';font-size:0.65rem;font-weight:700;letter-spacing:1px;">'+sec["number"]+'</span>'
        '<span style="font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-left:8px;">'+sec["icon"]+' '+sec["full_label"]+'</span>'
        +risk_badge+
        '<div style="font-size:0.78rem;color:#888;line-height:1.5;margin-top:6px;'
        'background:#f8f8f8;padding:8px 12px;border-radius:4px;">'+sec["desc"]+'</div>'
        '</div>', unsafe_allow_html=True)

    # ── Documents (for non-final sections) ───────────────────────
    if key != "final_valuation":
        loaded = st.session_state.section_doc_names.get(key, [])
        if key == "transaction" and st.session_state.excel_name:
            loaded = [st.session_state.excel_name]

        if loaded:
            st.markdown(
                '<div style="background:#f0fff4;border:1px solid #bbf7d0;border-radius:4px;'
                'padding:7px 12px;font-size:0.76rem;color:#166534;margin-bottom:8px;">'
                '📎 <b>Documenti:</b> ' + " &nbsp;·&nbsp; ".join(loaded) + '</div>',
                unsafe_allow_html=True)
            if st.button("+ Aggiungi documenti", key=f"add_doc_{key}"):
                st.session_state.step = "section_config"; st.rerun()
        else:
            hint = " · ".join(REQUIRED_DOCS.get(key, []))
            if hint:
                st.markdown(
                    '<div style="font-size:0.72rem;color:#f59e0b;margin-bottom:6px;">'
                    '⚠️ Nessun documento — '
                    + ("web search abilitata (max 3 ricerche)" if key == "reputational"
                       else "web search abilitata" if mode == "agent" else "inserimento manuale")
                    + f'<br><span style="color:#bbb;font-size:0.68rem;">Suggeriti: {hint}</span></div>',
                    unsafe_allow_html=True)

    # ── Manual mode ───────────────────────────────────────────────
    if mode == "manual" and key != "final_valuation":
        st.markdown('<hr style="margin:8px 0;">', unsafe_allow_html=True)
        manual_text = st.text_area("Risultati analisi", value=content, height=350,
                                   key=f"manual_{key}", label_visibility="collapsed",
                                   placeholder="Inserisci qui i risultati dell'analisi...")
        if st.button("💾  Salva", key=f"save_{key}", use_container_width=True):
            st.session_state.edited_content[key] = manual_text
            state.add_result(key, manual_text)
            log_event(sec["label"], "Salvato manualmente ✓", "done")
            st.rerun()

    # ── Agent / Final Valuation mode ─────────────────────────────
    else:
        if key == "final_valuation":
            done_m, total_m = main_progress()
            if done_m < total_m:
                st.warning(f"⚠️  Completa prima le {total_m} sezioni ({done_m}/{total_m} completate).")
            else:
                if st.button("⚡  Genera Customer Risk Rating", key="run_fv", use_container_width=True):
                    _run_with_stream(key, client)
                if status == "completed":
                    if st.button("🔄 Ri-genera", key="rerun_fv"):
                        _run_with_stream(key, client)
        else:
            b1, b2 = st.columns([2, 1])
            with b1:
                lbl = "▶  Avvia Analisi" if status == "empty" else "▶  Ri-esegui"
                if st.button(lbl, key=f"run_{key}", use_container_width=True):
                    _run_with_stream(key, client)
            with b2:
                if st.button("⚙  Cambia config.", key=f"cfg_{key}", use_container_width=True,
                             help="Cambia modalità o documenti"):
                    st.session_state.step = "section_config"; st.rerun()

    # ── Result ────────────────────────────────────────────────────
    if status == "completed" and content:
        st.markdown('<hr style="margin:10px 0;">', unsafe_allow_html=True)
        if parsed:
            render_prose_result(key, parsed)
        else:
            # Plain text fallback
            edited = st.text_area("Risultato", value=content, height=400,
                                  key=f"edit_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                state.add_result(key, edited)

    # ── Prev / Next navigation ────────────────────────────────────
    st.markdown('<hr style="margin:14px 0 8px;">', unsafe_allow_html=True)
    sec_keys = [s["key"] for s in MAIN_SECTIONS]
    if key in sec_keys:
        idx = sec_keys.index(key)
        nc1, nc2, nc3 = st.columns([1, 3, 1])
        with nc1:
            if idx > 0:
                prev = MAIN_SECTIONS[idx - 1]
                if st.button(f"← {prev['label']}", key=f"prev_{key}", use_container_width=True):
                    st.session_state.active_section = prev["key"]; st.rerun()
        with nc3:
            if idx < len(sec_keys) - 1:
                nxt = MAIN_SECTIONS[idx + 1]
                if st.button(f"{nxt['label']} →", key=f"next_{key}", use_container_width=True):
                    st.session_state.active_section = nxt["key"]; st.rerun()
            elif main_progress()[0] == len(MAIN_SECTIONS):
                if st.button("⚡ Final Val. →", key="go_fv", use_container_width=True):
                    st.session_state.active_section = "final_valuation"; st.rerun()


def _run_with_stream(key: str, client):
    if not client:
        st.error("API Key non configurata nei Secrets."); return
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:600;color:'+RED+';margin:6px 0 4px;">⏳ Elaborazione in corso...</div>',
        unsafe_allow_html=True)
    area = st.empty()
    buf  = {"text": ""}
    def on_token(chunk):
        buf["text"] += chunk
        disp = buf["text"][-3000:] if len(buf["text"]) > 3000 else buf["text"]
        area.markdown(
            '<div style="font-family:monospace;font-size:0.7rem;white-space:pre-wrap;'
            'background:#f5f5f5;border:1px solid #e8e8e8;border-radius:4px;'
            'padding:10px;max-height:260px;overflow-y:auto;">'
            + disp.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            + '</div>', unsafe_allow_html=True)
    try:
        run_section(key, client, on_token=on_token)
    except Exception as e:
        st.error(str(e))
    st.rerun()


# ── ANALYSIS PAGE ────────────────────────────────────────────────
def render_analysis():
    render_header()
    render_section_nav()
    left, center, right = st.columns([1.6, 5, 2.5])
    with left:   render_left()
    with center: render_center_section()
    with right:  render_right()


# ── ROUTER ───────────────────────────────────────────────────────
if st.session_state.step == "setup":
    render_setup()
elif st.session_state.step == "section_config":
    render_section_config()
else:
    render_analysis()
