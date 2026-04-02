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
    import re
    decoder = json.JSONDecoder()

    def _try(s: str):
        s = s.strip()
        # Try direct parse
        try: return json.loads(s)
        except Exception: pass
        # Find first '{' and use raw_decode (handles preamble/postamble correctly)
        idx = s.find("{")
        while idx != -1:
            try:
                obj, _ = decoder.raw_decode(s, idx)
                if isinstance(obj, dict): return obj
            except Exception: pass
            idx = s.find("{", idx + 1)
        return None

    # Pass 1: raw text
    result = _try(text)
    if result: return result
    # Pass 2: strip markdown code fences
    stripped = re.sub(r"```(?:json)?\s*", "", text)
    return _try(stripped)

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
                st.session_state.step = "analysis"
                st.rerun()

# ── FILE ROUTING ─────────────────────────────────────────────────

def _route_uploaded_files(uploaded_files):
    """Route files to sections based on filename prefix: 01_, 1_, 01-, 1-, etc."""
    import re
    routing = {sec["key"]: [] for sec in MAIN_SECTIONS}
    unmatched = []
    for f in uploaded_files:
        name = f.name.lower()
        matched = False
        for i, sec in enumerate(MAIN_SECTIONS, 1):
            if re.match(r'^0?' + str(i) + r'[\s_\-\.]', name):
                routing[sec["key"]].append(f)
                matched = True
                break
        if not matched:
            unmatched.append(f)
    return routing, unmatched


# ── SECTION RESULT CARD ───────────────────────────────────────────

def _render_section_result(sec: dict, client):
    """Section card: header + assigned docs + run button + result."""
    key     = sec["key"]
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    risk    = (parsed.get("rischioComplessivo","") or parsed.get("customerRiskRating","")) if parsed else ""
    rc      = get_risk_color(risk)
    running = st.session_state.running_agent == key

    # ── Header ────────────────────────────────────────────────────
    dot   = "⏳" if running else ("●" if status == "completed" else "○")
    dot_c = "#f59e0b" if running else (rc if status == "completed" else "#d0d0d0")
    bl_c  = "#f59e0b" if running else (rc if status == "completed" else "#eee")
    st.markdown(
        f'<div style="border-left:4px solid {bl_c};padding:6px 0 4px 14px;margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
        f'<span style="color:{dot_c};font-size:0.75rem;">{dot}</span>'
        f'<span style="font-size:0.6rem;color:#bbb;font-weight:700;">{sec["number"]}</span>'
        f'<span style="font-size:1.0rem;font-weight:700;color:#1a1a1a;">{sec["icon"]} {sec["full_label"]}</span>'
        + (f'<span style="background:{rc};color:#fff;font-size:0.62rem;font-weight:700;'
           f'padding:2px 10px;border-radius:10px;">{risk}</span>' if risk else '')
        + f'</div>'
        f'<div style="font-size:0.73rem;color:#aaa;padding-left:22px;margin-top:2px;">{sec["desc"]}</div>'
        f'</div>',
        unsafe_allow_html=True)

    # ── Assigned docs ─────────────────────────────────────────────
    loaded = st.session_state.section_doc_names.get(key, [])
    if key == "transaction" and st.session_state.excel_name:
        loaded = [st.session_state.excel_name]
    if loaded:
        tags = "".join(
            f'<span style="display:inline-block;background:#f0fff4;border:1px solid #bbf7d0;'
            f'border-radius:10px;padding:2px 8px;font-size:0.68rem;color:#166534;margin:2px;">📄 {n}</span>'
            for n in loaded)
        st.markdown(f'<div style="margin-bottom:8px;">{tags}</div>', unsafe_allow_html=True)

    # ── Run button ────────────────────────────────────────────────
    c1, _ = st.columns([1, 5])
    with c1:
        lbl = "▶  Avvia" if status == "empty" else "↺  Ri-esegui"
        if st.button(lbl, key=f"run_{key}", use_container_width=True):
            _run_with_stream(key, client)
            return

    # ── Result ────────────────────────────────────────────────────
    if status == "completed" and content:
        if parsed:
            render_prose_result(key, parsed)
        else:
            edited = st.text_area("", value=content, height=300,
                                  key=f"edit_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                st.session_state.kyc_state.add_result(key, edited)
    elif status == "empty" and not running:
        st.markdown(
            f'<div style="text-align:center;padding:20px 0;">'
            f'<div style="font-size:2.5rem;">{sec["icon"]}</div>'
            f'<div style="font-size:0.8rem;color:#ccc;margin-top:6px;">'
            f'In attesa dei documenti</div></div>',
            unsafe_allow_html=True)

    st.markdown('<hr style="margin:20px 0;border-color:#f0f0f0;">', unsafe_allow_html=True)


def _render_final_valuation_card(client):
    key     = "final_valuation"
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    done, total = main_progress()
    fv      = FINAL_SECTION
    crr     = parsed.get("customerRiskRating","") if parsed else ""
    crr_c   = get_risk_color(crr)
    running = st.session_state.running_agent == key

    dot   = "⏳" if running else ("●" if status == "completed" else "⚡")
    dot_c = "#f59e0b" if running else (crr_c if status == "completed" else (RED if done == total else "#d0d0d0"))
    bl_c  = "#f59e0b" if running else (crr_c if status == "completed" else (RED if done == total else "#eee"))

    st.markdown(
        f'<div style="border-left:4px solid {bl_c};padding:6px 0 4px 14px;margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="color:{dot_c};font-size:0.85rem;">{dot}</span>'
        f'<span style="font-size:0.6rem;color:#bbb;font-weight:700;">{fv["number"]}</span>'
        f'<span style="font-size:1.0rem;font-weight:700;color:#1a1a1a;">{fv["icon"]} {fv["full_label"]}</span>'
        + (f'<span style="background:{crr_c};color:#fff;font-size:0.62rem;font-weight:700;'
           f'padding:2px 10px;border-radius:10px;">{crr}</span>' if crr else '')
        + f'</div>'
        f'<div style="font-size:0.73rem;color:#aaa;padding-left:22px;margin-top:2px;">{fv["desc"]}</div>'
        f'</div>',
        unsafe_allow_html=True)

    if done < total and status != "completed":
        st.markdown(
            f'<div style="font-size:0.8rem;color:#aaa;padding:8px 0 16px 22px;">'
            f'Completa le {total} sezioni ({done}/{total}) per generare la valutazione finale.</div>',
            unsafe_allow_html=True)
        return

    c1, _, _ = st.columns([2, 1, 3])
    with c1:
        lbl = "⚡  Genera Customer Risk Rating" if status == "empty" else "⚡  Ri-genera"
        if st.button(lbl, key="run_fv", use_container_width=True):
            _run_with_stream(key, client)
            return

    if status == "completed" and content and parsed:
        render_prose_result(key, parsed)


# ── STREAMING ────────────────────────────────────────────────────
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
    client  = get_client()
    state   = st.session_state.kyc_state
    done, total = main_progress()

    # ── Process run queue (one agent at a time, with streaming) ───
    queue = st.session_state.get("run_queue", [])
    if queue:
        next_key = queue[0]
        st.session_state["run_queue"] = queue[1:]
        sec = next(s for s in ALL_SECTIONS if s["key"] == next_key)
        remaining = len(queue) - 1
        st.markdown(
            f'<div style="background:#fff8f0;border:1px solid #fed7aa;border-radius:6px;'
            f'padding:10px 16px;margin-bottom:16px;font-size:0.82rem;color:#92400e;">'
            f'⚙️ Esecuzione: <b>{sec["icon"]} {sec["full_label"]}</b>'
            + (f' &nbsp;·&nbsp; <span style="color:#aaa">{remaining} in coda</span>' if remaining else '')
            + '</div>',
            unsafe_allow_html=True)
        _run_with_stream(next_key, client)
        return

    # ── Top bar ───────────────────────────────────────────────────
    fv_parsed = parse_json_result(get_content("final_valuation"))
    crr       = fv_parsed.get("customerRiskRating","") if fv_parsed else ""
    crr_c     = get_risk_color(crr)
    segs = ""
    for i in range(total):
        c = RED if i < done else "#eee"
        segs += f'<div style="flex:1;height:5px;background:{c};border-radius:3px;margin:0 1px;"></div>'

    tb_l, tb_r = st.columns([4, 1])
    with tb_l:
        st.markdown(
            f'<div style="padding:4px 0 12px;">'
            f'<span style="font-size:1.05rem;font-weight:700;color:#1a1a1a;">{state.case.company_name}</span>'
            f'<span style="color:#ddd;margin:0 8px;">|</span>'
            f'<span style="font-size:0.8rem;color:#aaa;">{state.case.country}</span>'
            + (f'<span style="color:#ddd;margin:0 8px;">|</span>'
               f'<span style="font-size:0.75rem;color:#aaa;">{state.case.case_id}</span>'
               if state.case.case_id else '')
            + (f' <span style="background:{crr_c};color:#fff;font-size:0.7rem;font-weight:700;'
               f'padding:3px 14px;border-radius:12px;margin-left:8px;">{crr}</span>'
               if crr else '')
            + f'<div style="display:flex;align-items:center;gap:6px;margin-top:6px;">'
            f'<div style="display:flex;gap:2px;width:120px;">{segs}</div>'
            f'<span style="font-size:0.65rem;color:#999;">{done}/{total} sezioni</span></div>'
            f'</div>',
            unsafe_allow_html=True)
    with tb_r:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✕", key="new_case", use_container_width=True, help="Nuovo caso"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.rerun()
        with c2:
            if st.button("⚙", key="go_setup", use_container_width=True, help="Setup"):
                st.session_state.step = "setup"; st.rerun()

    # ── Single upload area ────────────────────────────────────────
    st.markdown(
        '<div style="background:#f9f9f9;border:1px dashed #ddd;border-radius:8px;'
        'padding:16px 20px;margin-bottom:20px;">'
        '<div style="font-size:0.82rem;font-weight:700;color:#1a1a1a;margin-bottom:4px;">'
        '📎 Carica i documenti della controparte</div>'
        '<div style="font-size:0.73rem;color:#999;margin-bottom:10px;">'
        'Nomina i file con il prefisso della sezione: <b>01_</b> Struttura · <b>02_</b> UBO/PEP · '
        '<b>03_</b> Reputational · <b>04_</b> Economic · <b>05_</b> Transactional</div>',
        unsafe_allow_html=True)

    upls = st.file_uploader(
        "Documenti",
        type=["pdf", "docx", "txt", "md", "csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key="main_upload",
        label_visibility="collapsed")

    if upls:
        fid = "_".join(f"{f.name}_{f.size}" for f in upls)
        if fid != st.session_state.get("main_upload_id"):
            st.session_state["main_upload_id"] = fid
            routing, unmatched = _route_uploaded_files(upls)

            # Store files per section
            queue = []
            for sec in MAIN_SECTIONS:
                key = sec["key"]
                files = routing[key]
                if not files:
                    continue
                if key == "transaction":
                    f = files[0]
                    f.seek(0)
                    ext = os.path.splitext(f.name)[1].lower()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(f.read())
                        st.session_state.excel_path = tmp.name
                        st.session_state.excel_name = f.name
                    st.session_state.section_doc_names[key] = [f.name]
                else:
                    texts, names = [], []
                    for f in files:
                        texts.append(f"=== {f.name} ===\n{extract_text_from_file(f)}")
                        names.append(f.name)
                    st.session_state.section_docs[key] = "\n\n".join(texts)
                    st.session_state.section_doc_names[key] = names
                queue.append(key)

            if queue:
                st.session_state["run_queue"] = queue

            st.rerun()

        # Show routing summary
        routing_done, _ = _route_uploaded_files(upls)
        rows = ""
        for f in upls:
            import re
            assigned = None
            for i, sec in enumerate(MAIN_SECTIONS, 1):
                if re.match(r'^0?' + str(i) + r'[\s_\-\.]', f.name.lower()):
                    assigned = sec
                    break
            if assigned:
                rows += (f'<div style="font-size:0.72rem;padding:2px 0;">'
                         f'<span style="color:#166534;">✅</span> '
                         f'<span style="color:#555;">{f.name}</span>'
                         f' <span style="color:#aaa;">→</span> '
                         f'<span style="color:#1a1a1a;font-weight:600;">'
                         f'{assigned["number"]} {assigned["label"]}</span></div>')
            else:
                rows += (f'<div style="font-size:0.72rem;padding:2px 0;">'
                         f'<span style="color:#d97706;">⚠️</span> '
                         f'<span style="color:#999;">{f.name}</span>'
                         f' <span style="color:#d97706;font-size:0.68rem;">— prefisso non riconosciuto</span>'
                         f'</div>')
        if rows:
            st.markdown(f'<div style="margin-top:10px;">{rows}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr style="margin:0 0 20px;border-color:#f0f0f0;">', unsafe_allow_html=True)

    # ── All 5 sections ────────────────────────────────────────────
    for sec in MAIN_SECTIONS:
        _render_section_result(sec, client)

    # ── Final Valuation ───────────────────────────────────────────
    _render_final_valuation_card(client)

    st.markdown('<hr style="margin:24px 0 8px;border-color:#f0f0f0;">', unsafe_allow_html=True)


# ── ROUTER ───────────────────────────────────────────────────────
if st.session_state.step == "setup":
    render_setup()
else:
    render_analysis()
