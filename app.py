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
    economic_profile_agent,
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

st.markdown(f"""
<style>
  .stApp, [data-testid="stAppViewContainer"] {{ background:#fff; color:#1a1a1a; }}
  [data-testid="stHeader"] {{ background:#fff; border-bottom:2px solid {RED}; }}
  section[data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display:none !important; }}
  h1,h2,h3,h4 {{ color:#1a1a1a !important; }}
  label, p {{ color:#333 !important; }}
  .stTextInput input, .stNumberInput input {{
    background:#f9f9f9 !important; color:#1a1a1a !important;
    border:1px solid #d8d8d8 !important; border-radius:3px !important; }}
  .stTextArea textarea {{
    background:#f9f9f9 !important; color:#1a1a1a !important;
    border:1px solid #d8d8d8 !important; border-radius:3px !important;
    font-size:0.83rem !important; }}
  .stSelectbox > div > div {{
    background:#f9f9f9 !important; color:#1a1a1a !important; border:1px solid #d8d8d8 !important; }}
  .stButton > button {{
    background:#1a1a1a !important; color:#fff !important;
    border:none !important; border-radius:3px !important;
    font-weight:600 !important; letter-spacing:0.4px !important; }}
  .stButton > button:hover {{ background:#333 !important; }}
  .stProgress > div > div > div {{ background:{RED} !important; }}
  details summary {{ color:#444 !important; }}
  details {{ background:#f9f9f9 !important; border:1px solid #e0e0e0 !important; }}
  hr {{ border-color:#eee !important; margin:0.5rem 0 !important; }}
  ::-webkit-scrollbar {{ width:4px; height:4px; }}
  ::-webkit-scrollbar-track {{ background:#f5f5f5; }}
  ::-webkit-scrollbar-thumb {{ background:#ccc; border-radius:3px; }}
  [data-testid="stFileUploader"] {{
    background:#f9f9f9 !important; border:1px dashed #ccc !important; border-radius:4px; }}
  .stRadio label {{ color:#333 !important; }}
  div[data-testid="stVerticalBlock"] > div:has(> .nav-btn) {{ padding:0 2px !important; }}
</style>
""", unsafe_allow_html=True)

# ── Definitions ───────────────────────────────────────────────────
MAIN_SECTIONS = [
    {"key": "registry",         "number": "01", "icon": "🏛",
     "label": "Registry",
     "full_label": "Registry & Corporate Structure",
     "desc": "Analisi della struttura societaria, catena proprietaria e governance. "
             "Verifica forma giuridica, oggetto sociale, capitale, organi amministrativi "
             "e identificazione di eventuali anomalie nella struttura."},
    {"key": "ubo_pep",          "number": "02", "icon": "👤",
     "label": "UBO / PEP",
     "full_label": "UBO / PEP Screening",
     "desc": "Identificazione del titolare effettivo (UBO) e screening delle persone "
             "politicamente esposte (PEP). Ricostruzione della catena di controllo, "
             "verifica soglie D.Lgs. 231/2007, status PEP di soci e amministratori."},
    {"key": "reputational",     "number": "03", "icon": "📰",
     "label": "Reputazionale",
     "full_label": "Reputational Analysis",
     "desc": "Adverse media screening e analisi dei precedenti giudiziari. "
             "Identificazione di procedimenti penali, reati presupposto AML, misure cautelari, "
             "interdizioni e notizie negative recenti da fonti attendibili."},
    {"key": "economic_profile", "number": "04", "icon": "📊",
     "label": "Profilo Eco.",
     "full_label": "Economic Profile",
     "desc": "Analisi del profilo economico-finanziario e verifica di coerenza AML. "
             "Esame di bilancio, ricavi, marginalità, struttura patrimoniale e rilevazione "
             "di incongruenze rispetto al settore e al profilo atteso (rif. UIF 2023)."},
    {"key": "transaction",      "number": "05", "icon": "💳",
     "label": "Transazioni",
     "full_label": "Transaction & Geographic Risk Analysis",
     "desc": "Analisi AML dei movimenti bancari e rischio geografico delle controparti. "
             "Rilevazione pattern sospetti (strutturazione, layering, pass-through), "
             "classificazione FATF/sanzioni dei paesi coinvolti nei flussi."},
]

FINAL_SECTION = {
    "key": "final_valuation", "number": "06", "icon": "⚡",
    "label": "Final Valuation",
    "full_label": "Final Valuation — Customer Risk Rating",
    "desc": "Sintesi di tutte le sezioni analizzate. Produce il Customer Risk Rating finale "
            "(BASSO / MEDIO / MEDIO-ALTO / ALTO / CRITICO), la matrice di rischio per dimensione, "
            "la raccomandazione operativa e la narrativa completa per il fascicolo cliente."
}

ALL_SECTIONS = MAIN_SECTIONS + [FINAL_SECTION]

REQUIRED_DOCS = {
    "registry":         ["Visura camerale", "Atto costitutivo / Statuto",
                         "Organigramma societario", "Modifiche societarie recenti"],
    "ubo_pep":          ["Dichiarazione UBO", "Doc. identità soci/amministratori",
                         "Estratto Registro UBO"],
    "reputational":     ["Sentenze e atti giudiziari", "Comunicati stampa ufficiali",
                         "Lista persone chiave + nazionalità"],
    "economic_profile": ["Bilancio (ultimi 3 anni)", "Conto economico",
                         "Nota integrativa", "Dichiarazioni fiscali / rating"],
    "transaction":      ["File Excel/CSV movimenti bancari",
                         "Colonne: data, controparte, IBAN, importo, causale"],
    "final_valuation":  [],
}

RISK_COLORS = {
    "LOW": "#22aa55", "MEDIUM": "#f59e0b", "HIGH": "#ef4444", "CRITICAL": "#7c3aed",
    "BASSO": "#22aa55", "MEDIO": "#f59e0b", "MEDIO-ALTO": "#f97316",
    "ALTO": "#ef4444", "CRITICO": "#7c3aed",
}

# ── Session state ─────────────────────────────────────────────────
DEFAULTS = {
    "step":           "setup",
    "kyc_state":      None,
    "active_section": "registry",
    "edited_content": {},
    "agent_log":      [],
    "section_modes":  {},
    "section_docs":   {},
    "section_doc_names": {},
    "section_notes":  {},
    "excel_path":     None,
    "excel_name":     None,
    "running_agent":  None,
    "knowledge_base": "",
    "kb_doc_names":   [],
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
        try:
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key

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

def log_event(agent, msg, level="running"):
    st.session_state.agent_log.append(
        {"ts": datetime.now().strftime("%H:%M:%S"),
         "agent": agent, "msg": msg, "level": level})

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

def parse_json_result(text: str):
    if not text: return None
    try:
        s = text.find("{"); e = text.rfind("}") + 1
        if s >= 0 and e > s:
            return json.loads(text[s:e])
    except (json.JSONDecodeError, ValueError):
        pass
    return None

def get_risk_color(level: str) -> str:
    return RISK_COLORS.get((level or "").upper(), "#888")

def run_section(key, client, on_token=None):
    state   = st.session_state.kyc_state
    company = state.case.company_name
    country = state.case.country

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

    use_web = not bool(docs_text)

    sec = next(s for s in ALL_SECTIONS if s["key"] == key)
    st.session_state.running_agent = key
    mode_str = "documenti" if docs_text else ("web search" if use_web else "dati forniti")
    log_event(sec["label"], f"Avvio analisi ({mode_str})...")

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
            if not path:
                raise ValueError("Nessun file Excel/CSV caricato.")
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
                '<div style="padding:8px 0 10px;border-bottom:2px solid ' + RED + ';margin-bottom:12px;">'
                '<span style="font-size:0.95rem;font-weight:900;letter-spacing:3px;color:#1a1a1a;">BAIN &amp; COMPANY</span>'
                '<span style="color:#ccc;margin:0 10px;">|</span>'
                '<span style="font-size:0.8rem;color:#666;">AML IntelliGent Platform · KYC / CDD Module</span>'
                '<span style="color:#ddd;margin:0 10px;">|</span>'
                '<span style="color:#1a1a1a;font-size:0.88rem;font-weight:600;">' + state.case.company_name + '</span>'
                '<span style="color:#aaa;font-size:0.75rem;margin-left:8px;">' + (state.case.case_id or "") + '</span>'
                '<span style="background:' + rc + ';color:#fff;font-size:0.65rem;padding:2px 8px;'
                'border-radius:10px;margin-left:10px;">' + str(done) + '/' + str(total) + ' sezioni</span>'
                '</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="padding:8px 0 10px;border-bottom:2px solid ' + RED + ';margin-bottom:12px;">'
                '<span style="font-size:0.95rem;font-weight:900;letter-spacing:3px;color:#1a1a1a;">BAIN &amp; COMPANY</span>'
                '<span style="color:#ccc;margin:0 10px;">|</span>'
                '<span style="font-size:0.8rem;color:#666;">AML IntelliGent Platform · KYC / CDD Module</span>'
                '</div>',
                unsafe_allow_html=True)
    with h_right:
        st.markdown('<div style="text-align:right;padding-top:6px;font-size:0.68rem;color:#aaa;">claude-opus-4-6</div>',
                    unsafe_allow_html=True)

# ── SETUP ────────────────────────────────────────────────────────
def render_setup():
    render_header()
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            '<div style="text-align:center;padding:20px 0 16px;">'
            '<div style="font-size:1.7rem;font-weight:700;color:#1a1a1a;">Nuovo Caso KYC / CDD</div>'
            '<div style="color:#888;margin-top:5px;font-size:0.88rem;">'
            'Inserisci i dati del cliente e carica la knowledge base normativa</div></div>',
            unsafe_allow_html=True)

        if not get_api_key():
            st.error("⚠️  API Key Anthropic non trovata. Aggiungila nei Secrets: ANTHROPIC_API_KEY")

        st.markdown("#### Informazioni Cliente")
        company = st.text_input("Ragione Sociale *", placeholder="es. Meridian Capital S.r.l.")
        c1, c2 = st.columns(2)
        with c1: country = st.text_input("Paese *", placeholder="es. Italia")
        with c2: sector  = st.text_input("Settore", placeholder="es. Wealth Management")
        c3, c4 = st.columns(2)
        with c3: case_id = st.text_input("Case ID", placeholder="es. AML-2026-0341")
        with c4: analyst = st.text_input("Analista", placeholder="es. M. Rossi")

        st.markdown("---")
        st.markdown("#### 📚 Knowledge Base Normativa")
        st.markdown(
            '<div style="font-size:0.78rem;color:#888;margin-bottom:8px;">'
            'Carica i documenti normativi di riferimento (FATF guidelines, circolari UIF, '
            'D.Lgs. 231/2007, liste sanzioni, policy AML interne). Saranno disponibili '
            'per tutti gli agenti come base di conoscenza.</div>',
            unsafe_allow_html=True)
        kb_files = st.file_uploader(
            "KB", type=["pdf","docx","txt","md","csv"],
            accept_multiple_files=True, key="kb_upload",
            label_visibility="collapsed")
        if kb_files:
            texts, names = [], []
            for f in kb_files:
                texts.append(f"=== {f.name} ===\n{extract_text_from_file(f)}")
                names.append(f.name)
            st.session_state.knowledge_base = "\n\n".join(texts)
            st.session_state.kb_doc_names   = names
            st.success(f"✓ {len(texts)} file caricati · {len(st.session_state.knowledge_base):,} caratteri estratti")
        elif st.session_state.kb_doc_names:
            st.info("📚 " + " · ".join(st.session_state.kb_doc_names))

        st.markdown("---")
        if st.button("▶  Apri Nota Parere", use_container_width=True):
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
                log_event("Sistema", f"Caso aperto: {company} ({country})", "super")
                st.session_state.active_section = "registry"
                st.session_state.step = "analysis"
                st.rerun()


# ── SECTION NAVIGATOR (top horizontal) ───────────────────────────
def render_section_nav():
    active    = st.session_state.active_section
    done_main, _ = main_progress()

    # Full-width pill bar
    n_cols = len(MAIN_SECTIONS) + 1
    cols   = st.columns(n_cols)

    for i, sec in enumerate(MAIN_SECTIONS):
        key       = sec["key"]
        status    = sec_status(key)
        is_active = active == key

        parsed = parse_json_result(get_content(key)) if status == "completed" else None
        risk   = parsed.get("rischioComplessivo", "") if parsed else ""
        rc     = get_risk_color(risk)

        if status == "completed" and risk:
            status_html = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{rc};margin-right:5px;vertical-align:middle;"></span>'
            label_color = "#1a1a1a"
        elif status == "completed":
            status_html = '<span style="color:#22aa55;font-size:0.8rem;margin-right:4px;">✓</span>'
            label_color = "#1a1a1a"
        else:
            status_html = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#e0e0e0;margin-right:5px;vertical-align:middle;"></span>'
            label_color = "#999"

        if is_active:
            card_style = (f"background:#fff;border:1.5px solid {RED};"
                          f"border-radius:8px;padding:8px 4px 6px;box-shadow:0 2px 8px rgba(204,0,0,0.12);")
            num_color  = RED
            fw         = "700"
        else:
            card_style = "background:#f7f7f7;border:1.5px solid #ebebeb;border-radius:8px;padding:8px 4px 6px;"
            num_color  = "#bbb"
            fw         = "500"

        with cols[i]:
            st.markdown(
                f'<div style="{card_style}text-align:center;margin:0 2px;">'
                f'<div style="font-size:0.58rem;font-weight:700;color:{num_color};'
                f'letter-spacing:1px;margin-bottom:3px;">{sec["number"]}</div>'
                f'<div style="font-size:0.78rem;font-weight:{fw};color:{label_color};'
                f'line-height:1.25;margin-bottom:4px;">{sec["icon"]}&nbsp;{sec["label"]}</div>'
                f'<div>{status_html}'
                + (f'<span style="font-size:0.6rem;font-weight:700;color:{rc};">{risk}</span>' if risk and status == "completed" else
                   '<span style="font-size:0.6rem;color:#ccc;">—</span>')
                + '</div></div>',
                unsafe_allow_html=True)
            if st.button("‎", key=f"nav_{key}", use_container_width=True, help=sec["full_label"]):
                st.session_state.active_section = key
                st.rerun()

    # Final Valuation pill
    fv_key    = "final_valuation"
    fv_status = sec_status(fv_key)
    is_active = active == fv_key
    all_done  = done_main == len(MAIN_SECTIONS)

    parsed = parse_json_result(get_content(fv_key)) if fv_status == "completed" else None
    crr    = parsed.get("customerRiskRating", "") if parsed else ""
    rc_fv  = get_risk_color(crr)

    if fv_status == "completed" and crr:
        status_html = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{rc_fv};margin-right:5px;vertical-align:middle;"></span>'
        sub_label   = f'<span style="font-size:0.6rem;font-weight:700;color:{rc_fv};">{crr}</span>'
    elif all_done:
        status_html = f'<span style="color:{RED};font-size:0.75rem;margin-right:4px;">⚡</span>'
        sub_label   = f'<span style="font-size:0.6rem;color:{RED};">Pronta</span>'
    else:
        status_html = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#e0e0e0;margin-right:5px;vertical-align:middle;"></span>'
        sub_label   = '<span style="font-size:0.6rem;color:#ccc;">Locked</span>'

    if is_active:
        card_style = (f"background:#fff;border:1.5px solid {RED};"
                      f"border-radius:8px;padding:8px 4px 6px;box-shadow:0 2px 8px rgba(204,0,0,0.12);")
        num_color  = RED; fw = "700"; label_color = "#1a1a1a"
    elif all_done or fv_status == "completed":
        card_style = f"background:#fffaf5;border:1.5px solid #ffd0a0;border-radius:8px;padding:8px 4px 6px;"
        num_color  = "#f97316"; fw = "600"; label_color = "#1a1a1a"
    else:
        card_style = "background:#f7f7f7;border:1.5px solid #ebebeb;border-radius:8px;padding:8px 4px 6px;opacity:0.5;"
        num_color  = "#ccc"; fw = "400"; label_color = "#ccc"

    with cols[-1]:
        st.markdown(
            f'<div style="{card_style}text-align:center;margin:0 2px;">'
            f'<div style="font-size:0.58rem;font-weight:700;color:{num_color};letter-spacing:1px;margin-bottom:3px;">'
            + FINAL_SECTION["number"] +
            f'</div><div style="font-size:0.78rem;font-weight:{fw};color:{label_color};line-height:1.25;margin-bottom:4px;">'
            f'⚡&nbsp;Final Val.</div>'
            f'<div>{status_html}{sub_label}</div></div>',
            unsafe_allow_html=True)
        if st.button("‎", key="nav_final_valuation", use_container_width=True,
                     help="Final Valuation — Customer Risk Rating",
                     disabled=not (all_done or fv_status == "completed")):
            st.session_state.active_section = fv_key
            st.rerun()

    st.markdown('<hr style="margin:0 0 10px 0;border-color:#eee;">', unsafe_allow_html=True)

# ── LEFT: DOCUMENT TRACKER ────────────────────────────────────────
def render_left():
    key   = st.session_state.active_section
    sec   = next(s for s in ALL_SECTIONS if s["key"] == key)
    req   = REQUIRED_DOCS.get(key, [])
    loaded_names = st.session_state.section_doc_names.get(key, [])
    if key == "transaction" and st.session_state.excel_name:
        loaded_names = [st.session_state.excel_name]

    # Section docs
    st.markdown(
        '<div style="font-size:0.62rem;font-weight:700;letter-spacing:2px;'
        'color:' + RED + ';margin-bottom:8px;">DOCUMENTI RICHIESTI</div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:600;color:#1a1a1a;margin-bottom:6px;">'
        + sec["label"] + '</div>',
        unsafe_allow_html=True)

    if req:
        for r in req:
            # Check if any loaded doc name vaguely matches
            is_loaded = any(
                r.lower().split()[0] in n.lower() or n.lower().split(".")[0][:6] in r.lower()
                for n in loaded_names
            ) if loaded_names else False
            color  = "#22aa55" if is_loaded else "#ccc"
            icon   = "✅" if is_loaded else "○"
            weight = "600" if is_loaded else "400"
            st.markdown(
                f'<div style="font-size:0.72rem;color:{color};font-weight:{weight};'
                f'padding:3px 0;display:flex;align-items:flex-start;gap:6px;">'
                f'<span>{icon}</span><span style="color:{"#333" if is_loaded else "#aaa"};">{r}</span></div>',
                unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.72rem;color:#aaa;">Nessun documento richiesto</div>',
                    unsafe_allow_html=True)

    # Uploaded docs
    if loaded_names:
        st.markdown('<div style="margin-top:10px;font-size:0.65rem;color:#666;font-weight:600;">CARICATI</div>',
                    unsafe_allow_html=True)
        for n in loaded_names:
            st.markdown(
                '<div style="font-size:0.68rem;color:#22aa55;padding:2px 0;'
                'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                '📄 ' + n + '</div>',
                unsafe_allow_html=True)

    st.markdown('<hr style="margin:12px 0;">', unsafe_allow_html=True)

    # Overall progress
    st.markdown(
        '<div style="font-size:0.62rem;font-weight:700;letter-spacing:2px;'
        'color:' + RED + ';margin-bottom:8px;">AVANZAMENTO</div>',
        unsafe_allow_html=True)
    for s in MAIN_SECTIONS:
        st_s  = sec_status(s["key"])
        run   = st.session_state.running_agent == s["key"]
        active_s = st.session_state.active_section == s["key"]
        if run:
            icon, tc = "⏳", "#f59e0b"
        elif st_s == "completed":
            parsed = parse_json_result(get_content(s["key"]))
            risk   = parsed.get("rischioComplessivo", "") if parsed else ""
            icon   = "●" if risk else "✓"
            tc     = get_risk_color(risk) if risk else "#22aa55"
        else:
            icon, tc = "○", "#ccc"
        fw = "700" if active_s else "400"
        st.markdown(
            f'<div style="font-size:0.72rem;color:{tc};font-weight:{fw};padding:2px 0;">'
            f'{icon} <span style="color:{"#1a1a1a" if active_s else "#666"};">'
            f'{s["number"]} {s["label"]}</span></div>',
            unsafe_allow_html=True)

    st.markdown('<hr style="margin:12px 0;">', unsafe_allow_html=True)

    # KB summary
    if st.session_state.kb_doc_names:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:2px;'
            'color:#0369a1;margin-bottom:6px;">📚 KNOWLEDGE BASE</div>',
            unsafe_allow_html=True)
        for n in st.session_state.kb_doc_names:
            st.markdown(
                '<div style="font-size:0.68rem;color:#0369a1;padding:2px 0;">✓ ' + n + '</div>',
                unsafe_allow_html=True)

    if st.button("← Nuovo Caso", key="new_case", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ── CENTER: SECTION DETAIL ────────────────────────────────────────
def render_json_result(parsed: dict):
    risk      = parsed.get("rischioComplessivo", "") or parsed.get("customerRiskRating", "")
    narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                 or parsed.get("sintesiEsecutiva", ""))
    flags     = parsed.get("flags", [])
    evidenze  = parsed.get("principaliEvidenze", [])

    # ── Risk badge ────────────────────────────────────────────────
    if risk:
        rc = get_risk_color(risk)
        raccomandazione = parsed.get("raccomandazione", "")
        racc_str = ""
        if isinstance(raccomandazione, dict):
            acc = raccomandazione.get("accettazione", "")
            adv = raccomandazione.get("livelloAdeguataVerifica", "")
            if acc:
                racc_str = f" &nbsp;·&nbsp; Accettazione: <b>{acc}</b>"
            if adv:
                racc_str += f" &nbsp;·&nbsp; Verifica: <b>{adv}</b>"
        elif isinstance(raccomandazione, str) and raccomandazione:
            racc_str = f" &nbsp;·&nbsp; {raccomandazione}"
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
            '<span style="background:' + rc + ';color:#fff;font-size:0.8rem;font-weight:700;'
            'padding:5px 16px;border-radius:20px;letter-spacing:0.5px;">⬤ ' + risk + '</span>'
            + (f'<span style="font-size:0.78rem;color:#666;">{racc_str}</span>' if racc_str else '')
            + '</div>', unsafe_allow_html=True)

    # ── Final valuation: risk matrix ──────────────────────────────
    mx = parsed.get("matriceRischio")
    if mx:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;'
            'color:#666;margin-bottom:8px;">MATRICE DI RISCHIO</div>',
            unsafe_allow_html=True)
        labels = [
            ("identitaStruttura", "Identità / Struttura"),
            ("reputazionale",     "Reputazionale"),
            ("economico",         "Economico"),
            ("transazionale",     "Transazionale"),
            ("geografico",        "Geografico"),
        ]
        cols = st.columns(5)
        for i, (dim, lbl) in enumerate(labels):
            val   = mx.get(dim, {})
            score = val.get("score", 0) if isinstance(val, dict) else 0
            sc    = int(score) if str(score).isdigit() else 0
            bar_c = RED if sc >= 4 else "#f59e0b" if sc == 3 else "#22aa55"
            motiv = val.get("motivazione", "") if isinstance(val, dict) else ""
            with cols[i]:
                st.markdown(
                    '<div style="text-align:center;background:#f8f8f8;border-radius:6px;'
                    'padding:10px 4px;border:1px solid #eee;" title="' + motiv + '">'
                    '<div style="font-size:0.6rem;color:#888;margin-bottom:4px;">' + lbl + '</div>'
                    '<div style="font-size:1.6rem;font-weight:900;color:' + bar_c + ';line-height:1;">'
                    + str(sc) + '</div>'
                    '<div style="font-size:0.55rem;color:#ccc;">/5</div>'
                    # mini bar
                    '<div style="margin:5px 8px 0;height:3px;border-radius:2px;background:#eee;">'
                    '<div style="width:' + str(sc * 20) + '%;height:100%;background:' + bar_c + ';border-radius:2px;"></div>'
                    '</div></div>', unsafe_allow_html=True)
        st.markdown("")

    # ── Narrativa / sintesi discorsiva ────────────────────────────
    if narrativa:
        st.markdown(
            '<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.5px;'
            'color:#444;margin:10px 0 6px;">SINTESI</div>',
            unsafe_allow_html=True)
        st.markdown(
            '<div style="background:#f8f8f8;border-left:3px solid ' + RED + ';'
            'padding:14px 18px;border-radius:0 6px 6px 0;font-size:0.86rem;'
            'line-height:1.7;color:#1a1a1a;margin-bottom:14px;">'
            + narrativa.replace("\n", "<br>") + '</div>',
            unsafe_allow_html=True)

    # ── Principali evidenze con normativa ─────────────────────────
    if evidenze:
        st.markdown(
            '<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.5px;'
            'color:#444;margin:8px 0 6px;">PRINCIPALI EVIDENZE DI ATTENZIONE</div>',
            unsafe_allow_html=True)
        level_styles = {
            "CRITICO":    ("background:#fef2f2;border-left:3px solid #ef4444;", "#ef4444", "●"),
            "ANOMALIA":   ("background:#fffbeb;border-left:3px solid #f59e0b;", "#f59e0b", "▲"),
            "ATTENZIONE": ("background:#f0f9ff;border-left:3px solid #0ea5e9;", "#0ea5e9", "◆"),
        }
        for ev in evidenze:
            livello  = (ev.get("livello") or "ATTENZIONE").upper()
            evid_txt = ev.get("evidenza", "")
            norm_txt = ev.get("normativa", "")
            sty, col, ico = level_styles.get(livello, level_styles["ATTENZIONE"])
            st.markdown(
                '<div style="' + sty + 'border-radius:0 6px 6px 0;padding:8px 12px;'
                'margin-bottom:5px;">'
                '<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                '<span style="font-size:0.78rem;color:#1a1a1a;">'
                '<span style="color:' + col + ';margin-right:5px;">' + ico + '</span>'
                + evid_txt + '</span>'
                '<span style="font-size:0.65rem;font-weight:600;color:' + col + ';'
                'white-space:nowrap;margin-left:10px;padding:1px 7px;border-radius:10px;'
                'border:1px solid ' + col + ';">' + livello + '</span>'
                '</div>'
                + (f'<div style="font-size:0.68rem;color:#888;margin-top:3px;margin-left:16px;">'
                   f'📎 {norm_txt}</div>' if norm_txt else '')
                + '</div>', unsafe_allow_html=True)
        st.markdown("")

    # ── Flag AML ──────────────────────────────────────────────────
    if flags:
        st.markdown(
            '<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.5px;'
            'color:#444;margin:8px 0 6px;">FLAG AML</div>',
            unsafe_allow_html=True)
        for f in flags:
            frc  = get_risk_color(f.get("rischio", ""))
            tipo = f.get("tipo", "")
            desc = f.get("descrizione", "")
            norm = f.get("riferimentoNormativo", "") or f.get("indicatoreUIF", "")
            st.markdown(
                '<div style="background:#fff;border:1px solid #f0f0f0;border-left:3px solid '
                + frc + ';border-radius:0 4px 4px 0;padding:6px 10px;margin-bottom:4px;">'
                '<span style="font-size:0.78rem;font-weight:600;color:#1a1a1a;">' + tipo + '</span>'
                + (f'<span style="font-size:0.76rem;color:#555;"> — {desc}</span>' if desc else '')
                + (f'<span style="font-size:0.68rem;color:#bbb;margin-left:8px;">📎 {norm}</span>' if norm else '')
                + '</div>', unsafe_allow_html=True)
        st.markdown("")

    with st.expander("📋 Dati strutturati completi (JSON)", expanded=False):
        st.json(parsed)


def render_center_section():
    client  = get_client()
    state   = st.session_state.kyc_state
    key     = st.session_state.active_section
    sec     = next(s for s in ALL_SECTIONS if s["key"] == key)
    mode    = st.session_state.section_modes.get(key, "agent")
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content)

    # ── A) Section header + description ──────────────────────────
    risk_badge = ""
    if status == "completed" and parsed:
        risk = parsed.get("rischioComplessivo") or parsed.get("customerRiskRating", "")
        if risk:
            rc = get_risk_color(risk)
            risk_badge = (f'<span style="background:{rc};color:#fff;font-size:0.72rem;'
                          f'font-weight:700;padding:3px 12px;border-radius:10px;margin-left:10px;">'
                          f'{risk}</span>')

    st.markdown(
        '<div style="margin-bottom:14px;">'
        '<span style="color:' + RED + ';font-size:0.68rem;font-weight:700;letter-spacing:1px;">'
        + sec["number"] + '</span>'
        '<span style="font-size:1.1rem;font-weight:700;color:#1a1a1a;margin-left:10px;">'
        + sec["icon"] + " " + sec["full_label"] + '</span>'
        + risk_badge +
        '<div style="font-size:0.8rem;color:#888;line-height:1.6;margin-top:6px;'
        'background:#f8f8f8;padding:10px 14px;border-radius:4px;">'
        + sec["desc"] + '</div>'
        '</div>',
        unsafe_allow_html=True)

    # ── B) Document upload ────────────────────────────────────────
    if key != "final_valuation":
        st.markdown(
            '<div style="font-size:0.65rem;font-weight:700;letter-spacing:1px;'
            'color:' + RED + ';margin-bottom:6px;">B  —  DOCUMENTI</div>',
            unsafe_allow_html=True)

        loaded_names = st.session_state.section_doc_names.get(key, [])

        if key == "transaction":
            # Transaction needs Excel - special uploader
            if st.session_state.excel_name:
                st.markdown(
                    '<div style="background:#f0fff4;border:1px solid #bbf7d0;border-radius:3px;'
                    'padding:8px 12px;font-size:0.78rem;color:#166534;margin-bottom:6px;">'
                    '📄 <b>File caricato:</b> ' + st.session_state.excel_name + '</div>',
                    unsafe_allow_html=True)
            uploaded = st.file_uploader(
                "Carica file transazioni (Excel / CSV)",
                type=["xlsx","xls","csv"], key=f"upload_{key}",
                label_visibility="collapsed")
            if uploaded:
                suffix = os.path.splitext(uploaded.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                    f.write(uploaded.read())
                    st.session_state.excel_path = f.name
                    st.session_state.excel_name = uploaded.name
                st.session_state.section_doc_names[key] = [uploaded.name]
                st.success(f"✓ {uploaded.name}")
                st.rerun()
        else:
            # Show already loaded docs
            if loaded_names:
                st.markdown(
                    '<div style="background:#f0fff4;border:1px solid #bbf7d0;border-radius:3px;'
                    'padding:8px 12px;font-size:0.78rem;color:#166534;margin-bottom:6px;">'
                    '📎 <b>Documenti caricati:</b> ' + " &nbsp;·&nbsp; ".join(loaded_names) + '</div>',
                    unsafe_allow_html=True)

            uploaded_files = st.file_uploader(
                "Carica documenti",
                type=["pdf","docx","xlsx","xls","csv","txt","md"],
                accept_multiple_files=True,
                key=f"upload_{key}",
                label_visibility="collapsed")
            if uploaded_files:
                texts, names = [], []
                for f in uploaded_files:
                    texts.append(f"=== {f.name} ===\n{extract_text_from_file(f)}")
                    names.append(f.name)
                st.session_state.section_docs[key]      = "\n\n".join(texts)
                st.session_state.section_doc_names[key] = names
                total_chars = len(st.session_state.section_docs[key])
                st.success(f"✓ {len(texts)} file · {total_chars:,} caratteri estratti")
                st.rerun()

        hint = REQUIRED_DOCS.get(key, [])
        if hint:
            st.markdown(
                '<div style="font-size:0.7rem;color:#aaa;margin-top:4px;">'
                '💡 Suggeriti: ' + " · ".join(hint) + '</div>',
                unsafe_allow_html=True)

        st.markdown('<hr style="margin:12px 0;">', unsafe_allow_html=True)

    # ── C) Mode selector (skip for final_valuation) ───────────────
    if key != "final_valuation":
        st.markdown(
            '<div style="font-size:0.65rem;font-weight:700;letter-spacing:1px;'
            'color:' + RED + ';margin-bottom:8px;">C  —  MODALITÀ DI ANALISI</div>',
            unsafe_allow_html=True)

        mode_radio = st.radio(
            "Modalità",
            ["🤖  Agente", "✍️  Manuale"],
            index=0 if mode == "agent" else 1,
            key=f"mode_{key}", horizontal=True,
            label_visibility="collapsed")
        new_mode = "agent" if "Agente" in mode_radio else "manual"
        if new_mode != st.session_state.section_modes.get(key):
            st.session_state.section_modes[key] = new_mode
            st.rerun()

        st.markdown('<hr style="margin:10px 0;">', unsafe_allow_html=True)

    # ── Actions ───────────────────────────────────────────────────
    current_mode = st.session_state.section_modes.get(key, "agent")

    if key == "final_valuation":
        # Final valuation — always agent
        done_main, total_main = main_progress()
        if done_main < total_main:
            st.warning(f"⚠️  Completa prima le {total_main} sezioni principali ({done_main}/{total_main} completate).")
        else:
            web_warn = ""
            if not st.session_state.section_docs.get(key):
                st.markdown(
                    '<div style="font-size:0.75rem;color:#f59e0b;margin-bottom:8px;">'
                    '— Sintesi automatica basata sui risultati degli agenti precedenti.</div>',
                    unsafe_allow_html=True)
            run_btn = st.button("⚡  Genera Customer Risk Rating", use_container_width=True,
                                key="run_final_valuation")
            if status == "completed":
                rerun_btn = st.button("🔄 Ri-genera", key="rerun_fv", use_container_width=True)
            else:
                rerun_btn = False

            if (run_btn or rerun_btn) and client:
                _run_agent_with_stream(key, client)

    elif current_mode == "agent":
        # Show web search / doc status
        has_docs = bool(st.session_state.section_docs.get(key) or
                        (key == "transaction" and st.session_state.excel_path))
        if has_docs:
            st.markdown(
                '<div style="font-size:0.72rem;color:#22aa55;margin-bottom:8px;">'
                '✓ L\'agente analizzerà i documenti caricati (web search disabilitata)</div>',
                unsafe_allow_html=True)
        else:
            note = " (max 3 ricerche)" if key == "reputational" else ""
            st.markdown(
                '<div style="font-size:0.72rem;color:#f59e0b;margin-bottom:8px;">'
                '⚠️ Nessun documento caricato — l\'agente userà web search' + note + '</div>',
                unsafe_allow_html=True)

        b1, b2 = st.columns([2, 1])
        with b1:
            run_btn = st.button("▶  Avvia Analisi", key=f"run_{key}", use_container_width=True)
        with b2:
            rerun_btn = (st.button("🔄 Ri-esegui", key=f"rerun_{key}", use_container_width=True)
                         if status == "completed" else False)

        if (run_btn or rerun_btn) and client:
            _run_agent_with_stream(key, client)
        elif (run_btn or rerun_btn) and not client:
            st.error("API Key non configurata nei Secrets.")

    else:
        # Manual mode
        st.markdown(
            '<div style="font-size:0.75rem;color:#666;margin-bottom:6px;">'
            'Inserisci manualmente i risultati dell\'analisi:</div>',
            unsafe_allow_html=True)
        manual_text = st.text_area(
            "Risultati analisi manuale",
            value=content,
            height=300,
            key=f"manual_edit_{key}",
            label_visibility="collapsed",
            placeholder="Scrivi qui i risultati dell'analisi per questa sezione...")
        if st.button("💾  Salva", key=f"save_{key}", use_container_width=True):
            st.session_state.edited_content[key] = manual_text
            state.add_result(key, manual_text)
            log_event(sec["label"], "Salvato manualmente ✓", "done")
            st.success("Salvato ✓")
            st.rerun()
        return  # don't show result panel yet if just editing

    # ── Result display ────────────────────────────────────────────
    if status == "completed" and content:
        st.markdown('<hr style="margin:12px 0;">', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.65rem;font-weight:700;letter-spacing:1px;'
            'color:' + RED + ';margin-bottom:8px;">RISULTATO</div>',
            unsafe_allow_html=True)
        if parsed:
            render_json_result(parsed)
        else:
            edited = st.text_area("result", value=content, height=350,
                                  key=f"edit_text_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                state.add_result(key, edited)

        # Next section button
        if key != "final_valuation":
            sec_keys = [s["key"] for s in MAIN_SECTIONS]
            idx = sec_keys.index(key) if key in sec_keys else -1
            if idx >= 0 and idx < len(sec_keys) - 1:
                next_key = sec_keys[idx + 1]
                next_sec = MAIN_SECTIONS[idx + 1]
                if st.button(f"Sezione successiva → {next_sec['label']}", key=f"next_{key}"):
                    st.session_state.active_section = next_key
                    st.rerun()
            elif idx == len(sec_keys) - 1:
                done_main, total_main = main_progress()
                if done_main == total_main:
                    if st.button("⚡  Procedi alla Final Valuation", key="go_fv"):
                        st.session_state.active_section = "final_valuation"
                        st.rerun()


def _run_agent_with_stream(key: str, client):
    """Execute agent with live token streaming in the UI."""
    st.markdown(
        '<div style="font-size:0.8rem;font-weight:600;color:' + RED + ';margin:6px 0 4px;">'
        '⏳ Agente in elaborazione...</div>',
        unsafe_allow_html=True)
    stream_area = st.empty()
    buf = {"text": ""}

    def on_token(chunk):
        buf["text"] += chunk
        display = buf["text"][-3000:] if len(buf["text"]) > 3000 else buf["text"]
        stream_area.markdown(
            '<div style="font-family:monospace;font-size:0.72rem;white-space:pre-wrap;'
            'background:#f5f5f5;border:1px solid #e8e8e8;border-radius:4px;'
            'padding:10px;max-height:300px;overflow-y:auto;">'
            + display.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            + '</div>',
            unsafe_allow_html=True)

    try:
        run_section(key, client, on_token=on_token)
    except Exception as e:
        st.error(str(e))
    st.rerun()


# ── RIGHT: AGENT LOG ──────────────────────────────────────────────
def render_right():
    done, total = main_progress()
    state = st.session_state.kyc_state

    # Progress
    st.progress(done / total if total else 0, text=f"Progresso: {done}/{total} sezioni")

    # Final valuation CRR badge (if available)
    fv_content = get_content("final_valuation")
    fv_parsed  = parse_json_result(fv_content)
    if fv_parsed:
        crr   = fv_parsed.get("customerRiskRating", "")
        score = fv_parsed.get("scoreFinale", "")
        if crr:
            rc = get_risk_color(crr)
            st.markdown(
                '<div style="background:' + rc + '18;border:2px solid ' + rc + ';'
                'border-radius:4px;padding:10px;margin:8px 0;text-align:center;">'
                '<div style="font-size:0.6rem;font-weight:700;color:#666;letter-spacing:1px;">CUSTOMER RISK RATING</div>'
                '<div style="font-size:1.3rem;font-weight:900;color:' + rc + ';">' + crr + '</div>'
                + ('<div style="font-size:0.72rem;color:#888;">Score ' + str(score) + '/5</div>' if score else '')
                + '</div>',
                unsafe_allow_html=True)

    st.markdown("---")

    # Agent log
    st.markdown(
        '<div style="font-size:0.62rem;font-weight:700;letter-spacing:2px;'
        'color:' + RED + ';margin-bottom:6px;">LOG ATTIVITÀ AGENTI</div>',
        unsafe_allow_html=True)

    level_colors = {"running": "#f59e0b", "done": "#22aa55", "error": "#ef4444", "super": RED}
    log_box = st.container(height=420)
    with log_box:
        if not st.session_state.agent_log:
            st.markdown('<div style="font-size:0.72rem;color:#bbb;">Nessuna attività.</div>',
                        unsafe_allow_html=True)
        for entry in reversed(st.session_state.agent_log[-60:]):
            c = level_colors.get(entry["level"], "#999")
            st.markdown(
                '<div style="font-size:0.67rem;font-family:monospace;padding:1px 0;">'
                '<span style="color:#ccc;">' + entry["ts"] + '</span> '
                '<span style="color:' + c + ';font-weight:600;">' + entry["agent"] + '</span>'
                '<span style="color:#999;"> — ' + entry["msg"] + '</span></div>',
                unsafe_allow_html=True)


# ── ANALYSIS PAGE ─────────────────────────────────────────────────
def render_analysis():
    render_header()
    render_section_nav()

    left, center, right = st.columns([1.6, 5, 2.4])
    with left:
        render_left()
    with center:
        render_center_section()
    with right:
        render_right()


# ── ROUTER ────────────────────────────────────────────────────────
if st.session_state.step == "setup":
    render_setup()
else:
    render_analysis()
