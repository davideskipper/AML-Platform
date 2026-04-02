"""
AML IntelliGent Platform — Streamlit Web Interface
Bain & Company Style — KYC / CDD Module
"""

import base64
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
     "label": "Corp. Structure", "full_label": "Corporate Structure Analysis",
     "desc": "Struttura societaria, catena proprietaria, governance, organi amministrativi, anomalie."},
    {"key": "ubo_pep",          "number": "02", "icon": "👤",
     "label": "UBO / PEP",      "full_label": "UBO / PEP Screening",
     "desc": "Titolari effettivi, screening PEP, catena di controllo, D.Lgs. 231/2007."},
    {"key": "reputational",     "number": "03", "icon": "📰",
     "label": "Negative News",  "full_label": "Negative News Screening",
     "desc": "Adverse media, precedenti giudiziari, reati presupposto AML, misure cautelari."},
    {"key": "economic_profile", "number": "04", "icon": "📊",
     "label": "Economic Profile","full_label": "Economic Profile Analysis",
     "desc": "Bilancio, coerenza economica, indicatori UIF 2023, incongruenze patrimoniali."},
    {"key": "transaction",      "number": "05", "icon": "💳",
     "label": "Transactional",  "full_label": "Transactional Analysis",
     "desc": "Movimenti bancari, pattern sospetti (strutturazione, layering), rischio geografico FATF."},
]
FINAL_SECTION = {
    "key": "final_valuation", "number": "06", "icon": "⚡",
    "label": "Final Valuation", "full_label": "Final Valuation & Proposal",
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

def run_section(key, client, on_token=None, on_thinking=None):
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
                                        show_output=False, on_token=on_token,
                                        on_thinking=on_thinking, use_web_search=use_web)
        elif key == "ubo_pep":
            result = ubo_pep_agent.run(client, company, country, manual_ctx,
                                       show_output=False, on_token=on_token,
                                       on_thinking=on_thinking, use_web_search=use_web)
        elif key == "reputational":
            result = reputational_agent.run(client, company, country, "", manual_ctx,
                                            show_output=False, on_token=on_token,
                                            on_thinking=on_thinking, use_web_search=use_web)
        elif key == "economic_profile":
            result = economic_profile_agent.run(client, company, country, manual_ctx,
                                                show_output=False, on_token=on_token,
                                                on_thinking=on_thinking, use_web_search=use_web)
        elif key == "transaction":
            path = st.session_state.excel_path or ""
            if not path: raise ValueError("Nessun file Excel/CSV caricato.")
            result = transaction_agent.run(client, path, company, manual_ctx,
                                           show_output=False, on_token=on_token,
                                           on_thinking=on_thinking)
        elif key == "final_valuation":
            result = final_valuation_agent.run(client, company, state.results, manual_ctx,
                                               show_output=False, on_token=on_token,
                                               on_thinking=on_thinking)
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


# ── Logo ─────────────────────────────────────────────────────────
def _logo_html(height: int = 38) -> str:
    """Return an <img> tag with the Bain logo as base64, or fallback text."""
    for fname in ("assets/bain_logo.png", "assets/bain_logo.jpg",
                  "assets/bain_logo.svg", "assets/bain_logo.webp"):
        if os.path.exists(fname):
            ext  = fname.rsplit(".", 1)[-1]
            mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
            with open(fname, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return (f'<img src="data:{mime};base64,{b64}" '
                    f'style="height:{height}px;vertical-align:middle;">')
    # Fallback — styled text
    return ('<span style="font-size:0.95rem;font-weight:900;letter-spacing:3px;'
            f'color:{RED};">BAIN &amp; COMPANY</span>')


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
                +_logo_html(34)+
                '<span style="color:#ddd;margin:0 12px;">|</span>'
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
                +_logo_html(34)+
                '<span style="color:#ddd;margin:0 12px;">|</span>'
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
                if ext in (".xlsx", ".xls", ".csv"):
                    excel_file = (f.name, ext, f)
            st.session_state.all_docs      = "\n\n".join(texts)
            st.session_state.all_doc_names = names
            for sec in MAIN_SECTIONS:
                if sec["key"] != "transaction":
                    st.session_state.section_docs[sec["key"]]      = st.session_state.all_docs
                    st.session_state.section_doc_names[sec["key"]] = names
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

        # ── Navigation buttons — always visible ───────────────────
        st.markdown("---")
        cb, cf = st.columns([1, 3])
        with cb:
            if st.button("← Indietro", use_container_width=True, key="cfg_back"):
                st.session_state.step = "setup"; st.rerun()
        with cf:
            if st.button("▶  Avvia Analisi Controparte", use_container_width=True, key="cfg_go"):
                st.session_state.active_section = "registry"
                st.session_state.step = "analysis"; st.rerun()


# ── SIDEBAR + CONTENT (new analysis layout) ──────────────────────

def _sidebar_section_row(sec: dict, is_active: bool):
    """Render one section row in the sidebar."""
    key     = sec["key"]
    status  = sec_status(key)
    running = st.session_state.running_agent == key
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    risk    = parsed.get("rischioComplessivo", "") if parsed else ""
    rc      = get_risk_color(risk)
    mode    = st.session_state.section_modes.get(key, "agent")

    if running:
        dot_color = "#f59e0b"; dot = "⏳"; dot_size = "0.8rem"
    elif status == "completed":
        dot_color = rc; dot = "●"; dot_size = "0.7rem"
    elif mode == "manual":
        dot_color = "#aaa"; dot = "✍"; dot_size = "0.72rem"
    else:
        dot_color = "#d0d0d0"; dot = "○"; dot_size = "0.75rem"

    border   = f"3px solid {RED}" if is_active else f"3px solid {'#e8e8e8' if status != 'completed' else rc+'55'}"
    bg       = "#fff5f5" if is_active else ("#fafafa" if status == "completed" else "#fff")
    name_w   = "700" if is_active else "600"
    name_c   = "#1a1a1a"

    excerpt_html = ""
    if status == "completed" and parsed:
        narrativa = parsed.get("narrativa", "") or parsed.get("narrativaCompleta", "") or ""
        if narrativa:
            short = narrativa[:90].replace("<","&lt;").replace(">","&gt;")
            if len(narrativa) > 90: short += "…"
            excerpt_html = (f'<div style="font-size:0.65rem;color:#888;margin-top:3px;'
                            f'line-height:1.4;padding-left:18px;">{short}</div>')
    elif running:
        excerpt_html = ('<div style="font-size:0.65rem;color:#f59e0b;margin-top:3px;'
                        'padding-left:18px;">elaborazione in corso...</div>')

    risk_badge = ""
    if risk and status == "completed":
        risk_badge = (f'<span style="font-size:0.6rem;font-weight:700;color:{rc};">{risk}</span>')

    st.markdown(
        f'<div style="border-left:{border};background:{bg};border-radius:0 6px 6px 0;'
        f'padding:8px 10px 8px 10px;margin-bottom:3px;">'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<span style="color:{dot_color};font-size:{dot_size};flex-shrink:0;">{dot}</span>'
        f'<span style="font-size:0.6rem;color:#bbb;flex-shrink:0;">{sec["number"]}</span>'
        f'<span style="font-size:0.78rem;font-weight:{name_w};color:{name_c};flex:1;">{sec["label"]}</span>'
        f'{risk_badge}</div>'
        f'{excerpt_html}</div>',
        unsafe_allow_html=True)

    if st.button("‎", key=f"sb_{key}", use_container_width=True, help=sec["full_label"]):
        st.session_state.active_section = key
        st.rerun()


def render_sidebar():
    state     = st.session_state.kyc_state
    active    = st.session_state.active_section
    done, total = main_progress()

    # ── Case card ────────────────────────────────────────────────
    fv_parsed = parse_json_result(get_content("final_valuation"))
    crr       = fv_parsed.get("customerRiskRating", "") if fv_parsed else ""
    crr_color = get_risk_color(crr)

    st.markdown(
        '<div style="background:#1a1a1a;border-radius:6px;padding:12px 14px;margin-bottom:12px;">'
        '<div style="font-size:0.58rem;color:#888;letter-spacing:1.5px;font-weight:700;margin-bottom:4px;">CONTROPARTE</div>'
        '<div style="font-size:0.9rem;font-weight:700;color:#fff;line-height:1.3;">' + state.case.company_name + '</div>'
        '<div style="font-size:0.7rem;color:#666;margin-top:2px;">'
        + (state.case.country or "") + ("  ·  " + state.case.case_id if state.case.case_id else "") + '</div>'
        + (f'<div style="margin-top:8px;text-align:center;background:{crr_color};color:#fff;'
           f'font-size:0.75rem;font-weight:700;padding:3px 0;border-radius:4px;">{crr}</div>'
           if crr else '') +
        '</div>',
        unsafe_allow_html=True)

    # ── Progress bar ─────────────────────────────────────────────
    bar_segments = ""
    for i in range(total):
        seg_c = RED if i < done else "#eee"
        bar_segments += f'<div style="flex:1;height:4px;background:{seg_c};border-radius:2px;margin:0 1px;"></div>'
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:12px;">'
        f'<div style="display:flex;flex:1;gap:1px;">{bar_segments}</div>'
        f'<span style="font-size:0.65rem;color:#999;white-space:nowrap;">{done}/{total}</span></div>',
        unsafe_allow_html=True)

    # ── Sections list ─────────────────────────────────────────────
    for sec in MAIN_SECTIONS:
        _sidebar_section_row(sec, is_active=(active == sec["key"]))

    st.markdown('<hr style="margin:8px 0 6px;border-color:#f0f0f0;">', unsafe_allow_html=True)

    # ── Final Valuation row ───────────────────────────────────────
    fv_key    = "final_valuation"
    fv_status = sec_status(fv_key)
    all_done  = done == total
    is_active_fv = active == fv_key

    if fv_status == "completed":
        dot_c = crr_color; dot_s = "●"; dot_sz = "0.7rem"
    elif all_done:
        dot_c = RED; dot_s = "⚡"; dot_sz = "0.85rem"
    else:
        dot_c = "#d0d0d0"; dot_s = "⚡"; dot_sz = "0.85rem"

    border_fv = f"3px solid {RED}" if is_active_fv else ("3px solid #ffd0a0" if all_done else "3px solid #eee")
    bg_fv     = "#fff5f5" if is_active_fv else ("#fffaf5" if all_done else "#fafafa")
    opacity   = "1" if (all_done or fv_status == "completed") else "0.4"

    st.markdown(
        f'<div style="border-left:{border_fv};background:{bg_fv};border-radius:0 6px 6px 0;'
        f'padding:8px 10px;margin-bottom:6px;opacity:{opacity};">'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<span style="color:{dot_c};font-size:{dot_sz};">{dot_s}</span>'
        f'<span style="font-size:0.6rem;color:#bbb;">{FINAL_SECTION["number"]}</span>'
        f'<span style="font-size:0.78rem;font-weight:700;color:#1a1a1a;">Final Valuation</span>'
        + (f'<span style="font-size:0.6rem;font-weight:700;color:{crr_color};">{crr}</span>' if crr else '')
        + f'</div></div>',
        unsafe_allow_html=True)
    if st.button("‎", key="sb_fv", use_container_width=True,
                 help="Final Valuation & Proposal",
                 disabled=not (all_done or fv_status == "completed")):
        st.session_state.active_section = fv_key
        st.rerun()

    st.markdown('<hr style="margin:6px 0 8px;border-color:#f0f0f0;">', unsafe_allow_html=True)

    # ── Action buttons ─────────────────────────────────────────────
    if done < total:
        if st.button("▶▶  Esegui Tutti gli Agenti", use_container_width=True, key="run_all"):
            client = get_client()
            if client:
                auto = [s for s in MAIN_SECTIONS
                        if st.session_state.section_modes.get(s["key"]) == "agent"]
                for s in auto:
                    try: run_section(s["key"], client)
                    except Exception as e: st.error(f"{s['label']}: {e}")
                st.rerun()
    elif fv_status != "completed":
        if st.button("⚡  Genera Final Valuation", use_container_width=True, key="go_fv_sb"):
            st.session_state.active_section = "final_valuation"
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("⚙  Config.", key="reconfig", use_container_width=True, help="Riconfigura sezioni"):
            st.session_state.step = "section_config"; st.rerun()
    with c2:
        if st.button("✕  Nuovo", key="new_case", use_container_width=True, help="Nuovo caso"):
            for k in list(st.session_state.keys()): del st.session_state[k]
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



def render_section_content():
    """Main content area for the active section."""
    client  = get_client()
    state   = st.session_state.kyc_state
    key     = st.session_state.active_section
    sec     = next(s for s in ALL_SECTIONS if s["key"] == key)
    mode    = st.session_state.section_modes.get(key, "agent")
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content)
    risk    = (parsed.get("rischioComplessivo", "") or parsed.get("customerRiskRating", "")) if parsed else ""
    rc      = get_risk_color(risk)
    done, total = main_progress()

    # ── Section title ─────────────────────────────────────────────
    risk_badge_html = ""
    if risk:
        risk_badge_html = (
            f'<span style="background:{rc};color:#fff;font-size:0.72rem;font-weight:700;'
            f'padding:3px 14px;border-radius:12px;margin-left:12px;">{risk}</span>')

    st.markdown(
        f'<div style="border-bottom:2px solid #f0f0f0;padding-bottom:12px;margin-bottom:16px;">'
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;">'
        f'<span style="font-size:0.7rem;font-weight:700;color:{RED};letter-spacing:1.5px;">{sec["number"]}</span>'
        f'<span style="font-size:1.15rem;font-weight:700;color:#1a1a1a;">{sec["icon"]} {sec["full_label"]}</span>'
        f'{risk_badge_html}</div>'
        f'<div style="font-size:0.8rem;color:#999;margin-top:5px;line-height:1.5;">{sec["desc"]}</div>'
        f'</div>',
        unsafe_allow_html=True)

    # ── Documents banner ─────────────────────────────────────────
    if key != "final_valuation":
        loaded = st.session_state.section_doc_names.get(key, [])
        if key == "transaction" and st.session_state.excel_name:
            loaded = [st.session_state.excel_name]

        if loaded:
            tags = "".join(
                f'<span style="display:inline-block;background:#f0fff4;border:1px solid #bbf7d0;'
                f'border-radius:10px;padding:2px 10px;font-size:0.7rem;color:#166534;margin:2px 2px;">📄 {n}</span>'
                for n in loaded)
            st.markdown(
                f'<div style="margin-bottom:12px;">{tags}</div>',
                unsafe_allow_html=True)
        else:
            hint = " · ".join(REQUIRED_DOCS.get(key, []))
            web_note = " (max 3 ricerche)" if key == "reputational" else ""
            bg_warn = "#fffbeb"; bc_warn = "#fde68a"
            st.markdown(
                f'<div style="background:{bg_warn};border:1px solid {bc_warn};border-radius:6px;'
                f'padding:8px 14px;margin-bottom:12px;font-size:0.76rem;color:#92400e;">'
                f'⚠️ Nessun documento caricato — '
                + ("Web search abilitata" + web_note if mode == "agent" else "Modalità manuale")
                + (f'<br><span style="color:#aaa;font-size:0.7rem;">Suggeriti: {hint}</span>' if hint else '')
                + '</div>',
                unsafe_allow_html=True)

    # ── Manual mode ───────────────────────────────────────────────
    if mode == "manual" and key != "final_valuation":
        manual_text = st.text_area(
            "Risultati analisi",
            value=content, height=340,
            key=f"manual_{key}", label_visibility="collapsed",
            placeholder="Inserisci i risultati dell'analisi per questa sezione…")
        c1, c2, _ = st.columns([1, 1, 3])
        with c1:
            if st.button("💾  Salva", key=f"save_{key}", use_container_width=True):
                st.session_state.edited_content[key] = manual_text
                state.add_result(key, manual_text)
                log_event(sec["label"], "Salvato manualmente ✓", "done")
                st.rerun()
        with c2:
            if st.button("⚙  Config.", key=f"cfgm_{key}", use_container_width=True):
                st.session_state.step = "section_config"; st.rerun()

    # ── Agent mode ────────────────────────────────────────────────
    else:
        if key == "final_valuation":
            done_m, total_m = main_progress()
            if done_m < total_m:
                st.info(f"Completa le {total_m} sezioni prima di generare la Final Valuation ({done_m}/{total_m}).")
            else:
                c1, c2, _ = st.columns([2, 1, 2])
                with c1:
                    lbl = "⚡  Genera Customer Risk Rating" if status == "empty" else "⚡  Ri-genera"
                    if st.button(lbl, key="run_fv", use_container_width=True):
                        _run_with_stream(key, client)
        else:
            c1, c2, c3 = st.columns([2, 1, 2])
            with c1:
                lbl = "▶  Avvia Analisi" if status == "empty" else "▶  Ri-esegui"
                if st.button(lbl, key=f"run_{key}", use_container_width=True):
                    _run_with_stream(key, client)
            with c2:
                if st.button("⚙", key=f"cfg_{key}", use_container_width=True,
                             help="Cambia modalità o documenti"):
                    st.session_state.step = "section_config"; st.rerun()

    # ── Result display ────────────────────────────────────────────
    if status == "completed" and content:
        st.markdown('<hr style="margin:16px 0 12px;border-color:#f0f0f0;">', unsafe_allow_html=True)
        if parsed:
            render_prose_result(key, parsed)
        else:
            edited = st.text_area("result", value=content, height=400,
                                  key=f"edit_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                state.add_result(key, edited)
    elif status == "empty" and mode == "agent" and key != "final_valuation":
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#ddd;">'
            '<div style="font-size:3.5rem;margin-bottom:12px;">' + sec["icon"] + '</div>'
            '<div style="font-size:0.9rem;color:#ccc;">Clicca "Avvia Analisi" per eseguire questa sezione</div>'
            '</div>', unsafe_allow_html=True)

    # ── Prev / Next ───────────────────────────────────────────────
    sec_keys = [s["key"] for s in MAIN_SECTIONS]
    if key in sec_keys:
        idx  = sec_keys.index(key)
        st.markdown('<hr style="margin:16px 0 8px;border-color:#f0f0f0;">', unsafe_allow_html=True)
        cn1, cn2, cn3 = st.columns([1, 3, 1])
        with cn1:
            if idx > 0:
                prev = MAIN_SECTIONS[idx - 1]
                if st.button(f"← {prev['label']}", key=f"prev_{key}", use_container_width=True):
                    st.session_state.active_section = prev["key"]; st.rerun()
        with cn3:
            if idx < len(sec_keys) - 1:
                nxt = MAIN_SECTIONS[idx + 1]
                if st.button(f"{nxt['label']} →", key=f"next_{key}", use_container_width=True):
                    st.session_state.active_section = nxt["key"]; st.rerun()
            elif done == len(MAIN_SECTIONS):
                if st.button("Final Val. →", key="go_fv", use_container_width=True):
                    st.session_state.active_section = "final_valuation"; st.rerun()


def _run_with_stream(key: str, client):
    if not client:
        st.error("API Key non configurata nei Secrets."); return

    status_box = st.empty()
    stream_box = st.empty()
    buf = {"text": "", "thinking": "", "phase": "thinking"}

    def _render():
        parts = []
        if buf["thinking"] and buf["phase"] == "thinking":
            th = buf["thinking"][-800:] if len(buf["thinking"]) > 800 else buf["thinking"]
            parts.append(
                '<div style="font-size:0.68rem;color:#aaa;font-style:italic;'
                'margin-bottom:6px;border-left:2px solid #ddd;padding-left:8px;">'
                '🧠 ' + th.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                + '</div>')
        if buf["text"]:
            disp = buf["text"][-3000:] if len(buf["text"]) > 3000 else buf["text"]
            parts.append(
                '<div style="font-family:monospace;font-size:0.7rem;white-space:pre-wrap;">'
                + disp.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                + '</div>')
        if parts:
            stream_box.markdown(
                '<div style="background:#f8f8f8;border:1px solid #eee;border-radius:6px;'
                'padding:10px 14px;max-height:280px;overflow-y:auto;">'
                + "".join(parts) + '</div>',
                unsafe_allow_html=True)

    def on_thinking(chunk):
        buf["thinking"] += chunk
        buf["phase"] = "thinking"
        status_box.markdown(
            f'<div style="font-size:0.75rem;font-weight:600;color:#aaa;margin:6px 0 2px;">'
            f'🧠 Analisi in corso…</div>', unsafe_allow_html=True)
        _render()

    def on_token(chunk):
        buf["text"] += chunk
        buf["phase"] = "writing"
        status_box.markdown(
            f'<div style="font-size:0.75rem;font-weight:600;color:{RED};margin:6px 0 2px;">'
            f'✍️ Redazione…</div>', unsafe_allow_html=True)
        _render()

    try:
        run_section(key, client, on_token=on_token, on_thinking=on_thinking)
    except Exception as e:
        st.error(str(e))
    st.rerun()


# ── ANALYSIS PAGE ────────────────────────────────────────────────
def render_analysis():
    render_header()
    sidebar, content_col = st.columns([1.9, 5.8])
    with sidebar:
        render_sidebar()
    with content_col:
        render_section_content()


# ── ROUTER ───────────────────────────────────────────────────────
if st.session_state.step == "setup":
    render_setup()
elif st.session_state.step == "section_config":
    render_section_config()
else:
    render_analysis()
