"""
AML IntelliGent Platform — Streamlit Web Interface
Bain & Company Style — KYC / CDD Module
"""

import base64
import io, json, os, re, tempfile
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
  @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
  .aml-spin {{ display:inline-block; animation: spin 1s linear infinite; }}
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
    "step": "setup",
    "kyc_state": None,
    "uploaded_files_data": [],
    "file_assignments": {},
    "section_modes": {},
    "section_web": {},
    "section_docs": {},
    "section_doc_names": {},
    "section_notes": {},
    "excel_path": None,
    "excel_name": None,
    "edited_content": {},
    "agent_log": [],
    "active_section": "registry",
    "run_queue": [],
    "agent_run_now": False,
    "crit_panel_section": None,
    "crit_overrides": {},
    "knowledge_base": "",
    "kb_doc_names": [],
    "final_mode": None,
    "upload_hash": "",
    "running_agent": None,
    "all_docs": "",
    "all_doc_names": [],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.kyc_state is None:
    st.session_state.kyc_state = SessionState()

for sec in ALL_SECTIONS:
    if sec["key"] not in st.session_state.section_modes:
        st.session_state.section_modes[sec["key"]] = "agent"
    if sec["key"] not in st.session_state.section_web:
        st.session_state.section_web[sec["key"]] = False


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
    decoder = json.JSONDecoder()

    def _try(s: str):
        s = s.strip()
        try: return json.loads(s)
        except Exception: pass
        idx = s.find("{")
        while idx != -1:
            try:
                obj, _ = decoder.raw_decode(s, idx)
                if isinstance(obj, dict): return obj
            except Exception: pass
            idx = s.find("{", idx + 1)
        return None

    result = _try(text)
    if result: return result
    stripped = re.sub(r"```(?:json)?\s*", "", text)
    return _try(stripped)

def get_risk_color(level: str) -> str:
    return RISK_COLORS.get((level or "").upper(), "#888")

def run_section(key, client, on_token=None, on_thinking=None):
    state   = st.session_state.kyc_state
    company = state.case.company_name
    country = state.case.country
    docs_text  = (st.session_state.section_docs.get(key, "")
                  or st.session_state.get("all_docs", ""))
    notes_text = st.session_state.section_notes.get(key, "")
    kb_text    = st.session_state.knowledge_base
    use_web    = st.session_state.section_web.get(key, False) or not bool(docs_text)
    parts = []
    if kb_text:
        parts.append(f"BASE DOCUMENTALE DI RIFERIMENTO (NORMATIVA):\n\n{kb_text}")
    if docs_text:
        parts.append(f"DOCUMENTI DEL CLIENTE:\n\n{docs_text}")
    if notes_text:
        parts.append(f"NOTE ANALISTA:\n{notes_text}")
    manual_ctx = "\n\n---\n\n".join(parts)
    sec = next(s for s in ALL_SECTIONS if s["key"] == key)
    st.session_state.running_agent = key
    log_event(sec["label"], f"Avvio ({'web search' if use_web else 'documenti'})...")
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
    for fname in ("assets/bain_logo.png", "assets/bain_logo.jpg",
                  "assets/bain_logo.svg", "assets/bain_logo.webp"):
        if os.path.exists(fname):
            ext  = fname.rsplit(".", 1)[-1]
            mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
            with open(fname, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return (f'<img src="data:{mime};base64,{b64}" '
                    f'style="height:{height}px;vertical-align:middle;">')
    return ('<span style="font-size:0.95rem;font-weight:900;letter-spacing:3px;'
            f'color:{RED};">BAIN &amp; COMPANY</span>')


# ── Step Navigation Bar ───────────────────────────────────────────
_STEP_ORDER = ["upload", "analysis", "final"]
_STEP_LABELS = {
    "upload":   "① Documenti",
    "analysis": "② Analisi",
    "final":    "③ Valutazione",
}

def render_step_nav(current_step_id: str):
    try:
        current_idx = _STEP_ORDER.index(current_step_id)
    except ValueError:
        current_idx = -1

    parts = []
    for i, step_id in enumerate(_STEP_ORDER):
        label = _STEP_LABELS[step_id]
        if i < current_idx:
            # Past step — grey tick
            parts.append(
                f'<span style="color:#999;font-size:0.82rem;">✔ {label}</span>'
            )
        elif i == current_idx:
            # Active step — bold red
            parts.append(
                f'<span style="color:{RED};font-size:0.82rem;font-weight:700;">{label}</span>'
            )
        else:
            # Future step — light grey
            parts.append(
                f'<span style="color:#ccc;font-size:0.82rem;">{label}</span>'
            )
        if i < len(_STEP_ORDER) - 1:
            parts.append('<span style="color:#ddd;margin:0 8px;font-size:0.82rem;">→</span>')

    st.markdown(
        '<div style="display:flex;align-items:center;flex-wrap:wrap;'
        'padding:6px 0 10px;margin-bottom:4px;">'
        + "".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


# ── Header ────────────────────────────────────────────────────────
def render_header():
    state = st.session_state.kyc_state
    h_left, h_right = st.columns([6, 1])
    with h_left:
        if st.session_state.step == "analysis" and state.case.company_name:
            done, total = main_progress()
            rc = "#22aa55" if done == total else RED
            st.markdown(
                '<div style="padding:6px 0 10px;border-bottom:2px solid ' + RED + ';margin-bottom:10px;">'
                + _logo_html(34) +
                '<span style="color:#ddd;margin:0 12px;">|</span>'
                '<span style="font-size:0.78rem;color:#888;">AML IntelliGent Platform · KYC/CDD</span>'
                '<span style="color:#ddd;margin:0 10px;">|</span>'
                '<span style="color:#1a1a1a;font-size:0.9rem;font-weight:600;">' + state.case.company_name + '</span>'
                '<span style="color:#aaa;font-size:0.72rem;margin-left:8px;">' + (state.case.case_id or '') + '</span>'
                '<span style="background:' + rc + ';color:#fff;font-size:0.62rem;padding:2px 8px;'
                'border-radius:10px;margin-left:10px;">' + str(done) + '/' + str(total) + '</span>'
                '</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="padding:6px 0 10px;border-bottom:2px solid ' + RED + ';margin-bottom:10px;">'
                + _logo_html(34) +
                '<span style="color:#ddd;margin:0 12px;">|</span>'
                '<span style="font-size:0.78rem;color:#888;">AML IntelliGent Platform · KYC/CDD</span>'
                '</div>', unsafe_allow_html=True)
    with h_right:
        st.markdown('<div style="text-align:right;padding-top:4px;font-size:0.65rem;color:#bbb;">claude-sonnet-4-6</div>',
                    unsafe_allow_html=True)
    # Show step nav for all steps except setup
    if st.session_state.step not in ("setup", ""):
        render_step_nav(st.session_state.step)


# ── render_prose_result ───────────────────────────────────────────
def render_prose_result(key: str, parsed: dict):
    """Displays agent result as professional prose — no raw JSON."""
    risk      = parsed.get("rischioComplessivo","") or parsed.get("customerRiskRating","")
    narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                 or parsed.get("sintesiEsecutiva","") or "")
    evidenze  = parsed.get("principaliEvidenze", [])
    flags     = parsed.get("flags", [])

    if risk:
        rc = get_risk_color(risk)
        racc = parsed.get("raccomandazione","")
        racc_str = ""
        if isinstance(racc, dict):
            acc  = racc.get("accettazione","")
            adv  = racc.get("livelloAdeguataVerifica","")
            freq = racc.get("frequenzaMonitoraggio","")
            parts_r = [x for x in [acc, adv, freq] if x]
            if parts_r: racc_str = " &nbsp;·&nbsp; ".join(parts_r)
        elif isinstance(racc, str) and racc:
            racc_str = racc
        st.markdown(
            '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:16px;">'
            '<span style="background:' + rc + ';color:#fff;font-size:0.82rem;font-weight:700;'
            'padding:5px 18px;border-radius:20px;">⬤ RISCHIO: ' + risk + '</span>'
            + (f'<span style="font-size:0.76rem;color:#777;">{racc_str}</span>' if racc_str else '')
            + '</div>', unsafe_allow_html=True)

    # Risk matrix — only for final_valuation
    if key == "final_valuation":
        mx = parsed.get("matriceRischio")
        if mx:
            labels = [("identitaStruttura","Identità/Struttura"),("reputazionale","Reputazionale"),
                      ("economico","Economico"),("transazionale","Transazionale"),("geografico","Geografico")]
            cols = st.columns(5)
            for i, (dim, lbl) in enumerate(labels):
                val  = mx.get(dim,{})
                sc   = int(val.get("score",0)) if isinstance(val,dict) else 0
                bc   = RED if sc >= 4 else "#f59e0b" if sc == 3 else "#22aa55"
                motiv = val.get("motivazione","") if isinstance(val,dict) else ""
                with cols[i]:
                    st.markdown(
                        '<div style="text-align:center;background:#f8f8f8;border-radius:6px;'
                        'padding:10px 4px;border:1px solid #eee;" title="' + motiv + '">'
                        '<div style="font-size:0.58rem;color:#999;margin-bottom:3px;">' + lbl + '</div>'
                        '<div style="font-size:1.5rem;font-weight:900;color:' + bc + ';">' + str(sc)
                        + '<span style="font-size:0.55rem;color:#ccc;">/5</span></div>'
                        '<div style="margin:4px 8px 0;height:3px;background:#eee;border-radius:2px;">'
                        '<div style="width:' + str(sc*20) + '%;height:100%;background:' + bc + ';border-radius:2px;"></div>'
                        '</div></div>', unsafe_allow_html=True)
            st.markdown("")

    if narrativa:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;color:#777;'
            'margin:12px 0 6px;">ANALISI</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="background:#fff;border:1px solid #e8e8e8;'
            'padding:16px 20px;border-radius:6px;font-size:0.87rem;'
            'line-height:1.8;color:#1a1a1a;margin-bottom:16px;">'
            + narrativa.replace("\n", "<br>") + '</div>', unsafe_allow_html=True)

    if evidenze:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;color:#555;'
            'margin:8px 0 8px;">PRINCIPALI EVIDENZE DI ATTENZIONE</div>', unsafe_allow_html=True)
        level_styles = {
            "CRITICO":    ("#fef2f2","#dc2626","🔴"),
            "ANOMALIA":   ("#fffbeb","#d97706","🟡"),
            "ATTENZIONE": ("#f0fdf4","#16a34a","🟢"),
        }
        for ev in evidenze:
            lvl  = (ev.get("livello") or "ATTENZIONE").upper()
            etxt = ev.get("evidenza","")
            ntxt = ev.get("normativa","")
            bg_e, col_e, ico_e = level_styles.get(lvl, level_styles["ATTENZIONE"])
            st.markdown(
                '<div style="background:' + bg_e + ';border-left:3px solid ' + col_e + ';'
                'border-radius:0 5px 5px 0;padding:8px 12px;margin-bottom:6px;">'
                '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
                '<span style="font-size:0.8rem;color:#1a1a1a;line-height:1.5;">'
                '<span style="color:' + col_e + ';margin-right:5px;">' + ico_e + '</span>' + etxt + '</span>'
                '<span style="font-size:0.6rem;font-weight:700;color:' + col_e + ';white-space:nowrap;'
                'padding:1px 6px;border-radius:8px;border:1px solid ' + col_e + ';">' + lvl + '</span></div>'
                + (f'<div style="font-size:0.68rem;color:#888;margin-top:4px;margin-left:16px;">📎 {ntxt}</div>'
                   if ntxt else '')
                + '</div>', unsafe_allow_html=True)

    if flags:
        st.markdown(
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:1.5px;color:#555;'
            'margin:8px 0 6px;">FLAG AML</div>', unsafe_allow_html=True)
        for fl in flags:
            frc  = get_risk_color(fl.get("rischio",""))
            tipo = fl.get("tipo","")
            desc = fl.get("descrizione","")
            norm = fl.get("riferimentoNormativo","") or fl.get("indicatoreUIF","")
            st.markdown(
                '<div style="border-left:3px solid ' + frc + ';padding:5px 10px;margin-bottom:4px;'
                'background:#fff;border-radius:0 4px 4px 0;">'
                '<span style="font-size:0.78rem;font-weight:600;">' + tipo + '</span>'
                + (f'<span style="font-size:0.76rem;color:#555;"> — {desc}</span>' if desc else '')
                + (f'<span style="font-size:0.66rem;color:#bbb;margin-left:6px;">📎 {norm}</span>' if norm else '')
                + '</div>', unsafe_allow_html=True)


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
        if st.button("Continua →  Carica Documenti", use_container_width=True):
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
                st.session_state.step = "upload"
                st.rerun()


# ── STEP 2: UPLOAD ────────────────────────────────────────────────
def _auto_detect_section(filename: str) -> str:
    """Return section key if filename starts with 0?N[space/_/-/.] for N=1..5, else ''."""
    lower = filename.lower()
    for i, sec in enumerate(MAIN_SECTIONS, 1):
        if re.match(r'^0?' + str(i) + r'[\s_\-\.]', lower):
            return sec["key"]
    return ""

def render_upload():
    render_header()
    _, col, _ = st.columns([0.5, 5, 0.5])
    with col:
        st.markdown("### 📎 Carica i documenti della controparte")
        st.markdown(
            '<div style="font-size:0.78rem;color:#888;margin-bottom:12px;">'
            'Nomina i file con il prefisso della sezione per l\'assegnazione automatica: '
            '<b>01_</b> Struttura · <b>02_</b> UBO/PEP · <b>03_</b> Reputational · '
            '<b>04_</b> Economic · <b>05_</b> Transactional</div>',
            unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Documenti controparte",
            type=["pdf", "docx", "txt", "md", "csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="upload_step_files",
            label_visibility="collapsed")

        if uploaded:
            new_hash = "_".join(f"{f.name}_{f.size}" for f in uploaded)
            if new_hash != st.session_state.upload_hash:
                files_data = []
                assignments = {}
                for f in uploaded:
                    f.seek(0)
                    ext = os.path.splitext(f.name)[1].lower()
                    # Keep raw bytes for Excel/CSV so the agent can read the real file
                    raw_bytes = None
                    if ext in (".xlsx", ".xls", ".csv"):
                        raw_bytes = f.read()
                        f.seek(0)
                    content_text = extract_text_from_file(f)
                    files_data.append({
                        "name": f.name,
                        "content_text": content_text,
                        "ext": ext,
                        "size": f.size,
                        "raw_bytes": raw_bytes,
                    })
                    # Preserve existing assignment if present, else auto-detect
                    existing = st.session_state.file_assignments.get(f.name)
                    if existing is not None:
                        assignments[f.name] = existing
                    else:
                        assignments[f.name] = _auto_detect_section(f.name)
                st.session_state.uploaded_files_data = files_data
                st.session_state.file_assignments = assignments
                st.session_state.upload_hash = new_hash
                st.rerun()

        # Assignment table
        files_data = st.session_state.uploaded_files_data
        if files_data:
            st.markdown(
                '<div style="font-size:0.8rem;font-weight:700;color:#1a1a1a;'
                'margin:16px 0 8px;">Assegnazione sezioni</div>',
                unsafe_allow_html=True)

            section_options = [("", "— Non assegnato —")] + [
                (s["key"], f'{s["number"]} · {s["full_label"]}') for s in MAIN_SECTIONS
            ]
            option_labels = [lbl for _, lbl in section_options]
            option_keys   = [k for k, _ in section_options]

            for fd in files_data:
                fname = fd["name"]
                disp  = fname if len(fname) <= 40 else fname[:37] + "..."
                row_l, row_r = st.columns([2, 3])
                with row_l:
                    st.markdown(
                        f'<div style="font-size:0.82rem;padding:8px 0;color:#1a1a1a;">'
                        f'📄 {disp}</div>',
                        unsafe_allow_html=True)
                with row_r:
                    current_key = st.session_state.file_assignments.get(fname, "")
                    try:
                        idx = option_keys.index(current_key)
                    except ValueError:
                        idx = 0
                    chosen = st.selectbox(
                        f"assign_{fname}",
                        options=option_labels,
                        index=idx,
                        key=f"assign_{fname}",
                        label_visibility="collapsed")
                    chosen_key = option_keys[option_labels.index(chosen)]
                    if chosen_key != st.session_state.file_assignments.get(fname):
                        st.session_state.file_assignments[fname] = chosen_key

        st.markdown("---")
        nav_l, nav_r = st.columns([1, 1])
        with nav_l:
            if st.button("← Indietro", key="upload_back", use_container_width=True):
                st.session_state.step = "setup"
                st.rerun()
        with nav_r:
            disabled = len(files_data) == 0
            if st.button("▶ Avvia Analisi", key="upload_next",
                         use_container_width=True,
                         disabled=disabled):
                # Build section_docs, section_doc_names and run_queue
                _files_data  = st.session_state.uploaded_files_data
                _file_assigns = st.session_state.file_assignments
                section_docs      = {}
                section_doc_names = {}

                for sec in MAIN_SECTIONS:
                    skey     = sec["key"]
                    assigned = [fd for fd in _files_data
                                if _file_assigns.get(fd["name"]) == skey]
                    if not assigned:
                        continue
                    if skey == "transaction":
                        fd  = assigned[0]
                        ext = fd["ext"]
                        raw = fd.get("raw_bytes")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                            if raw:
                                tmp.write(raw)
                            else:
                                tmp.write(fd["content_text"].encode("utf-8", errors="replace"))
                            st.session_state.excel_path = tmp.name
                        st.session_state.excel_name = fd["name"]
                        section_doc_names[skey] = [fd["name"]]
                    else:
                        texts = [f"=== {fd['name']} ===\n{fd['content_text']}" for fd in assigned]
                        names = [fd["name"] for fd in assigned]
                        section_docs[skey]      = "\n\n".join(texts)
                        section_doc_names[skey] = names

                st.session_state.section_docs      = section_docs
                st.session_state.section_doc_names = section_doc_names

                # Default: agent mode for assigned sections, no web search
                for sec in MAIN_SECTIONS:
                    if sec["key"] not in st.session_state.section_modes:
                        st.session_state.section_modes[sec["key"]] = "agent"

                run_queue = [s["key"] for s in MAIN_SECTIONS
                             if any(_file_assigns.get(fd["name"]) == s["key"]
                                    for fd in _files_data)
                             and st.session_state.section_modes.get(s["key"]) == "agent"]

                st.session_state.run_queue     = run_queue
                st.session_state.active_section = "registry"
                st.session_state.step           = "analysis"
                st.rerun()


# ── STEP 3: MODE CONFIG ───────────────────────────────────────────
def render_mode_config():
    render_header()
    _, col, _ = st.columns([0.5, 5, 0.5])
    with col:
        st.markdown("### ⚙️ Configura le modalità di analisi")
        st.markdown(
            '<div style="font-size:0.78rem;color:#888;margin-bottom:16px;">'
            'Scegli se ogni sezione deve essere analizzata dall\'agente AI o inserita manualmente.</div>',
            unsafe_allow_html=True)

        files_data    = st.session_state.uploaded_files_data
        file_assigns  = st.session_state.file_assignments

        for sec in MAIN_SECTIONS:
            key = sec["key"]
            # Files assigned to this section
            assigned_files = [fd["name"] for fd in files_data
                              if file_assigns.get(fd["name"]) == key]

            # Card
            st.markdown(
                f'<div style="background:#f9f9f9;border:1px solid #e8e8e8;border-radius:8px;'
                f'padding:14px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                f'<span style="font-size:1.1rem;">{sec["icon"]}</span>'
                f'<span style="font-size:0.7rem;color:#bbb;font-weight:700;">{sec["number"]}</span>'
                f'<span style="font-size:0.92rem;font-weight:700;color:#1a1a1a;">{sec["full_label"]}</span>'
                f'</div>',
                unsafe_allow_html=True)

            col_mode, col_web, col_files = st.columns([2, 1.5, 2.5])

            with col_mode:
                current_mode = st.session_state.section_modes.get(key, "agent")
                mode_idx = 0 if current_mode == "agent" else 1
                chosen = st.radio(
                    "Modalità",
                    options=["🤖 Agente", "✍️ Manuale"],
                    index=mode_idx,
                    key=f"mode_{key}",
                    horizontal=True,
                    label_visibility="collapsed")
                new_mode = "agent" if chosen == "🤖 Agente" else "manual"
                st.session_state.section_modes[key] = new_mode

            with col_web:
                if st.session_state.section_modes.get(key) == "agent":
                    web_val = st.session_state.section_web.get(key, False)
                    new_web = st.checkbox("🌐 Web search", value=web_val, key=f"web_{key}")
                    st.session_state.section_web[key] = new_web

            with col_files:
                if assigned_files:
                    tags = "".join(
                        f'<span style="display:inline-block;background:#f0fff4;border:1px solid #bbf7d0;'
                        f'border-radius:10px;padding:2px 8px;font-size:0.68rem;color:#166534;margin:2px;">'
                        f'📄 {n[:28]}</span>'
                        for n in assigned_files)
                    st.markdown(f'<div style="padding-top:4px;">{tags}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<span style="font-size:0.72rem;color:#bbb;">Nessun documento assegnato</span>',
                        unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        nav_l, nav_r = st.columns([1, 1])
        with nav_l:
            if st.button("← Indietro", key="mode_back", use_container_width=True):
                st.session_state.step = "upload"
                st.rerun()
        with nav_r:
            if st.button("▶ Avvia Analisi", key="mode_next", use_container_width=True):
                # Build section_docs and section_doc_names
                files_data   = st.session_state.uploaded_files_data
                file_assigns = st.session_state.file_assignments
                section_docs     = {}
                section_doc_names = {}

                for sec in MAIN_SECTIONS:
                    skey = sec["key"]
                    assigned = [fd for fd in files_data if file_assigns.get(fd["name"]) == skey]
                    if not assigned:
                        continue
                    if skey == "transaction":
                        fd  = assigned[0]
                        ext = fd["ext"]
                        raw = fd.get("raw_bytes")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                            if raw:
                                tmp.write(raw)          # real binary Excel/CSV
                            else:
                                tmp.write(fd["content_text"].encode("utf-8", errors="replace"))
                            st.session_state.excel_path = tmp.name
                        st.session_state.excel_name = fd["name"]
                        section_doc_names[skey] = [fd["name"]]
                    else:
                        texts = [f"=== {fd['name']} ===\n{fd['content_text']}" for fd in assigned]
                        names = [fd["name"] for fd in assigned]
                        section_docs[skey]      = "\n\n".join(texts)
                        section_doc_names[skey] = names

                st.session_state.section_docs     = section_docs
                st.session_state.section_doc_names = section_doc_names

                # Build run_queue — only agent-mode sections
                run_queue = [s["key"] for s in MAIN_SECTIONS
                             if st.session_state.section_modes.get(s["key"]) == "agent"]
                st.session_state.run_queue = run_queue
                st.session_state.active_section = "registry"
                st.session_state.step = "analysis"
                st.rerun()


# ── STREAMING helper ──────────────────────────────────────────────
def _run_with_stream(key: str, client):
    if not client:
        st.error("API Key non configurata nei Secrets.")
        return

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
                '🧠 ' + th.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                + '</div>')
        if buf["text"]:
            disp = buf["text"][-3000:] if len(buf["text"]) > 3000 else buf["text"]
            parts.append(
                '<div style="font-family:monospace;font-size:0.7rem;white-space:pre-wrap;">'
                + disp.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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


# ── Analysis sidebar ──────────────────────────────────────────────
def _render_analysis_sidebar(queued_key=None):
    queue      = st.session_state.get("run_queue", [])
    active_key = st.session_state.get("active_section", "registry")

    for sec in MAIN_SECTIONS:
        k         = sec["key"]
        status    = sec_status(k)
        is_active = (k == active_key)
        is_running = (k == queued_key)

        # Colours: green = done, grey = pending/running
        if status == "completed":
            dot_c     = "#22aa55"
            label_c   = "#1a1a1a"
            dot       = "●"
        elif is_running:
            dot_c     = "#aaa"
            label_c   = "#777"
            dot       = "⚙"   # will spin via CSS
        else:
            dot_c     = "#d0d0d0"
            label_c   = "#aaa"
            dot       = "○"

        dot_class = 'class="aml-spin"' if is_running else ''
        border    = f"border-left:3px solid {RED};background:#fff9f9;" if is_active else "border-left:3px solid transparent;"

        st.markdown(
            f'<div style="{border}padding:8px 8px 8px 10px;border-radius:0 4px 4px 0;margin-bottom:2px;">'
            f'<span {dot_class} style="color:{dot_c};font-size:0.65rem;margin-right:6px;">{dot}</span>'
            f'<span style="font-size:0.82rem;font-weight:{"700" if is_active else "400"};color:{label_c};">'
            f'{sec["icon"]} {sec["label"]}</span>'
            f'</div>',
            unsafe_allow_html=True)

        if st.button("‎", key=f"sb_{k}", use_container_width=True, help=sec["full_label"]):
            st.session_state.active_section = k
            st.rerun()

    st.markdown('<hr style="margin:10px 0;border-color:#f0f0f0;">', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✕ Nuovo", key="new_case_sb", use_container_width=True):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()
    with c2:
        if st.button("⚙", key="go_setup_sb", use_container_width=True, help="Setup"):
            st.session_state.step = "setup"; st.rerun()


# ── Criticality panel ─────────────────────────────────────────────
def _render_crit_panel(key: str):
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    if not parsed:
        st.markdown('<div style="color:#aaa;font-size:0.8rem;padding:8px;">Nessun risultato disponibile.</div>',
                    unsafe_allow_html=True)
        return

    evidenze  = parsed.get("principaliEvidenze", [])
    overrides = st.session_state.crit_overrides.get(key, {})

    critics  = [(i, ev) for i, ev in enumerate(evidenze)
                if (ev.get("livello","") or "").upper().startswith("CRITICO")]
    anomalie = [(i, ev) for i, ev in enumerate(evidenze)
                if (ev.get("livello","") or "").upper().startswith("ANOMALIA")]

    def _render_group(group, header_html):
        if not group:
            return
        st.markdown(header_html, unsafe_allow_html=True)
        for idx, ev in group:
            ov = overrides.get(idx, {})
            is_closed = (ov.get("status","") or "").lower() == "chiuso"
            etxt  = ev.get("evidenza","")
            ntxt  = ev.get("normativa","")
            prop  = ev.get("proposta","") or etxt
            lvl   = (ev.get("livello","") or "").upper()
            bg_c  = "#fef2f2" if lvl.startswith("CRITICO") else "#fffbeb"
            brd_c = "#dc2626"  if lvl.startswith("CRITICO") else "#d97706"
            opacity = "opacity:0.5;" if is_closed else ""

            st.markdown(
                f'<div style="background:{bg_c};border-left:3px solid {brd_c};'
                f'border-radius:0 5px 5px 0;padding:10px 12px;margin-bottom:8px;{opacity}">'
                f'<div style="font-size:0.8rem;color:#1a1a1a;font-weight:600;margin-bottom:4px;">{etxt}</div>'
                f'<div style="font-size:0.75rem;color:#555;margin-bottom:4px;">Proposta: {prop}</div>'
                + (f'<div style="font-size:0.67rem;color:#999;">📎 {ntxt}</div>' if ntxt else '')
                + (f'<div style="font-size:0.67rem;color:{brd_c};font-weight:700;margin-top:4px;">'
                   f'Stato: {ov.get("status","—")}</div>' if ov else '')
                + f'</div>',
                unsafe_allow_html=True)

            # Edit status button
            edit_key = f"crit_edit_{key}_{idx}"
            if st.button(f"Modifica stato ▾", key=f"crit_btn_{key}_{idx}"):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                st.rerun()

            if st.session_state.get(edit_key, False):
                with st.form(key=f"crit_form_{key}_{idx}"):
                    cur_status = ov.get("status","Confermato")
                    cur_motiv  = ov.get("motivation","")
                    status_opts = ["Confermato","In revisione","Chiuso"]
                    try:
                        s_idx = status_opts.index(cur_status)
                    except ValueError:
                        s_idx = 0
                    new_status = st.radio("Status", status_opts, index=s_idx,
                                          horizontal=True, key=f"crit_radio_{key}_{idx}")
                    new_motiv  = st.text_input("Motivazione", value=cur_motiv,
                                               key=f"crit_motiv_{key}_{idx}")
                    if st.form_submit_button("💾 Salva"):
                        if key not in st.session_state.crit_overrides:
                            st.session_state.crit_overrides[key] = {}
                        st.session_state.crit_overrides[key][idx] = {
                            "status": new_status, "motivation": new_motiv}
                        st.session_state[edit_key] = False
                        st.rerun()

    _render_group(critics,
        '<div style="font-size:0.75rem;font-weight:700;color:#dc2626;margin:8px 0 6px;">🔴 Criticità</div>')
    _render_group(anomalie,
        '<div style="font-size:0.75rem;font-weight:700;color:#d97706;margin:8px 0 6px;">🟡 Attenzione</div>')

    if not critics and not anomalie:
        st.markdown('<div style="color:#aaa;font-size:0.8rem;padding:8px;">Nessuna criticità rilevata.</div>',
                    unsafe_allow_html=True)


# ── Section content ───────────────────────────────────────────────
def _render_section_content(key: str, client):
    sec     = next(s for s in MAIN_SECTIONS if s["key"] == key)
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    mode    = st.session_state.section_modes.get(key, "agent")

    # ── Section title (clean, no badges) ──────────────────────────
    st.markdown(
        f'<div style="border-bottom:1px solid #f0f0f0;padding-bottom:10px;margin-bottom:16px;">'
        f'<span style="font-size:0.6rem;color:#bbb;font-weight:700;letter-spacing:1px;">{sec["number"]}</span>'
        f'<span style="font-size:1.05rem;font-weight:700;color:#1a1a1a;margin-left:8px;">'
        f'{sec["icon"]} {sec["full_label"]}</span>'
        f'</div>',
        unsafe_allow_html=True)

    # ── Manual mode ───────────────────────────────────────────────
    if mode == "manual":
        val = st.session_state.get(f"manual_text_{key}", content or "")
        new_val = st.text_area("Analisi manuale", value=val, height=300,
                               key=f"manual_ta_{key}", label_visibility="collapsed")
        if st.button("💾 Salva", key=f"manual_save_{key}"):
            st.session_state.edited_content[key] = new_val
            st.session_state.kyc_state.add_result(key, new_val)
            st.rerun()
        return

    # ── Agent mode: result ────────────────────────────────────────
    if status == "completed" and content:
        if parsed:
            narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                         or parsed.get("sintesiEsecutiva","") or "")
            if narrativa:
                st.markdown(
                    '<div style="background:#fff;border:1px solid #ebebeb;'
                    'padding:18px 22px;border-radius:6px;font-size:0.87rem;'
                    'line-height:1.85;color:#1a1a1a;">'
                    + narrativa.replace("\n","<br>") + '</div>',
                    unsafe_allow_html=True)

            # Edit toggle
            etk = f"show_edit_{key}"
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            if st.button("✏️ Modifica", key=f"edit_toggle_{key}"):
                st.session_state[etk] = not st.session_state.get(etk, False)
                st.rerun()
            if st.session_state.get(etk, False):
                edited = st.text_area("", value=content, height=300,
                                      key=f"edit_ta_{key}", label_visibility="collapsed")
                if st.button("💾 Salva", key=f"edit_save_{key}"):
                    st.session_state.edited_content[key] = edited
                    st.session_state.kyc_state.add_result(key, edited)
                    st.session_state[etk] = False
                    st.rerun()
        else:
            edited = st.text_area("", value=content, height=300,
                                  key=f"edit_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                st.session_state.kyc_state.add_result(key, edited)

    elif status == "empty":
        st.markdown(
            f'<div style="text-align:center;padding:40px 0;">'
            f'<div style="font-size:3rem;opacity:0.15;">{sec["icon"]}</div>'
            f'<div style="font-size:0.8rem;color:#ccc;margin-top:10px;">In attesa di analisi</div>'
            f'</div>', unsafe_allow_html=True)
        if st.button("▶ Avvia agente", key=f"run_{key}"):
            _run_with_stream(key, client)


# ── STEP 4: ANALYSIS ─────────────────────────────────────────────
def render_analysis():
    render_header()
    client = get_client()

    # Two-phase agent execution:
    # Phase 1 (prepare): render the skeleton so old upload content is cleared, then rerun.
    # Phase 2 (run):     old content is gone — now actually run the agent.
    run_now   = st.session_state.get("agent_run_now", False)
    has_queue = bool(st.session_state.get("run_queue"))

    queued_key = None
    if has_queue:
        if run_now:
            # Phase 2: pop and execute
            queued_key = st.session_state["run_queue"][0]
            st.session_state["run_queue"] = st.session_state["run_queue"][1:]
            st.session_state.active_section = queued_key
            st.session_state.agent_run_now = False
        else:
            # Phase 1: just peek — don't pop yet
            queued_key = st.session_state["run_queue"][0]
            st.session_state.active_section = queued_key

    # ── Global criticality indicator ─────────────────────────────
    # Count active (non-chiuse) CRITICO + ANOMALIA across all done sections
    total_crit = total_anom = 0
    for sec in MAIN_SECTIONS:
        sk = sec["key"]
        sc = get_content(sk)
        sp = parse_json_result(sc) if sc else None
        if not sp:
            continue
        ov = st.session_state.crit_overrides.get(sk, {})
        for i, ev in enumerate(sp.get("principaliEvidenze", [])):
            lvl = (ev.get("livello","") or "").upper()
            if (ov.get(i, {}).get("status","") or "").lower() == "chiuso":
                continue
            if lvl.startswith("CRITICO"):
                total_crit += 1
            elif lvl.startswith("ANOMALIA"):
                total_anom += 1

    # Show indicator row (right-aligned above columns)
    ind_parts = []
    if total_crit:
        ind_parts.append(f'<span style="background:#fef2f2;color:#dc2626;font-size:0.75rem;font-weight:700;'
                         f'padding:4px 12px;border-radius:12px;border:1px solid #fecaca;">🔴 {total_crit} criticità</span>')
    if total_anom:
        ind_parts.append(f'<span style="background:#fffbeb;color:#d97706;font-size:0.75rem;font-weight:700;'
                         f'padding:4px 12px;border-radius:12px;border:1px solid #fde68a;">🟡 {total_anom} attenzioni</span>')
    if ind_parts:
        st.markdown(
            f'<div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:12px;">'
            + "".join(ind_parts) + '</div>',
            unsafe_allow_html=True)

    # ── Layout ────────────────────────────────────────────────────
    crit_panel_open = st.session_state.get("crit_panel_section")

    if crit_panel_open:
        col_sidebar, col_content, col_crit = st.columns([1.6, 3.5, 2.2])
    else:
        col_sidebar, col_content = st.columns([1.6, 5.2])
        col_crit = None

    with col_sidebar:
        _render_analysis_sidebar(queued_key=queued_key)

    with col_content:
        active_key = st.session_state.get("active_section", "registry")

        if queued_key:
            sec = next(s for s in ALL_SECTIONS if s["key"] == queued_key)
            st.markdown(
                f'<div style="font-size:0.88rem;font-weight:600;color:#777;margin-bottom:14px;">'
                f'<span class="aml-spin" style="display:inline-block;margin-right:6px;">⚙</span>'
                f'{sec["icon"]} {sec["full_label"]} — analisi in corso…</div>',
                unsafe_allow_html=True)
            if run_now:
                # Phase 2: old page fully cleared — run the agent
                _run_with_stream(queued_key, client)
                return
            else:
                # Phase 1: skeleton rendered; trigger phase 2 so upload content is gone
                st.session_state.agent_run_now = True
                st.rerun()

        # Criticality badge for active section (opens right panel)
        if parsed_active := parse_json_result(get_content(active_key)):
            ov_a = st.session_state.crit_overrides.get(active_key, {})
            n_c = sum(1 for i,ev in enumerate(parsed_active.get("principaliEvidenze",[]))
                      if (ev.get("livello","") or "").upper().startswith("CRITICO")
                      and (ov_a.get(i,{}).get("status","") or "").lower() != "chiuso")
            n_a = sum(1 for i,ev in enumerate(parsed_active.get("principaliEvidenze",[]))
                      if (ev.get("livello","") or "").upper().startswith("ANOMALIA")
                      and (ov_a.get(i,{}).get("status","") or "").lower() != "chiuso")
            if n_c or n_a:
                bc1, bc2, _ = st.columns([1, 1, 6])
                with bc1:
                    if n_c and st.button(f"🔴 {n_c}", key=f"cb_{active_key}"):
                        st.session_state.crit_panel_section = None if crit_panel_open == active_key else active_key
                        st.rerun()
                with bc2:
                    if n_a and st.button(f"🟡 {n_a}", key=f"ab_{active_key}"):
                        st.session_state.crit_panel_section = None if crit_panel_open == active_key else active_key
                        st.rerun()

        _render_section_content(active_key, client)

        st.markdown('<hr style="margin:20px 0;border-color:#f0f0f0;">', unsafe_allow_html=True)
        done, total = main_progress()
        if done == total:
            if st.button("💾 Salva e Procedi alla Valutazione Finale →",
                         key="go_final", use_container_width=True):
                st.session_state.step = "final"
                st.rerun()

    if col_crit:
        with col_crit:
            st.markdown(
                '<div style="font-size:0.85rem;font-weight:700;color:#1a1a1a;'
                'border-bottom:1px solid #f0f0f0;padding-bottom:8px;margin-bottom:12px;">'
                'Criticità &amp; Attenzioni</div>',
                unsafe_allow_html=True)
            _render_crit_panel(crit_panel_open)
            if st.button("✕ Chiudi", key="close_crit_panel"):
                st.session_state.crit_panel_section = None
                st.rerun()


# ── STEP 5: FINAL VALUATION ───────────────────────────────────────
def render_final_valuation():
    render_header()
    _, col, _ = st.columns([0.3, 5.4, 0.3])
    with col:
        st.markdown("### ⚡ Valutazione Finale")

        # Mode selector
        current_final_mode = st.session_state.final_mode or "manual"
        mode_map = {"✍️ A mano": "manual", "🤖 Super Agent": "agent"}
        mode_labels = list(mode_map.keys())
        mode_idx = 1 if current_final_mode == "agent" else 0
        chosen_label = st.radio(
            "Modalità valutazione",
            mode_labels,
            index=mode_idx,
            horizontal=True,
            key="final_mode_radio",
            label_visibility="collapsed")
        st.session_state.final_mode = mode_map[chosen_label]

        st.markdown("---")

        client = get_client()
        key = "final_valuation"

        if st.session_state.final_mode == "manual":
            # Manual narrative
            existing = get_content(key) or ""
            manual_narrative = st.text_area(
                "Narrativa di valutazione",
                value=existing,
                height=280,
                key="final_manual_text",
                placeholder="Inserisci la valutazione finale della controparte…")
            st.markdown("**Profilo di rischio**")
            risk_opts = ["Confermato", "Innalzamento", "Abbassamento", "Modifica"]
            risk_choice = st.radio("Profilo di rischio", risk_opts,
                                   horizontal=True, key="final_risk_radio",
                                   label_visibility="collapsed")
            if st.button("💾 Salva Valutazione", key="final_manual_save", use_container_width=True):
                narrative_full = f"[{risk_choice}]\n\n{manual_narrative}"
                st.session_state.edited_content[key] = narrative_full
                st.session_state.kyc_state.add_result(key, narrative_full)
                st.success("Valutazione salvata.")

        else:
            # Super Agent mode
            content = get_content(key)
            parsed  = parse_json_result(content) if content else None

            # Collect findings from all sections
            all_findings = []
            overrides    = st.session_state.crit_overrides
            for sec in MAIN_SECTIONS:
                sk = sec["key"]
                sc = get_content(sk)
                sp = parse_json_result(sc) if sc else None
                if not sp:
                    continue
                for idx, ev in enumerate(sp.get("principaliEvidenze",[])):
                    lvl = (ev.get("livello","") or "").upper()
                    if lvl not in ("CRITICO","ANOMALIA"):
                        continue
                    ov_status = (overrides.get(sk,{}).get(idx,{}).get("status","") or "").lower()
                    if ov_status == "chiuso":
                        continue
                    all_findings.append({
                        "sezione": sec["full_label"],
                        "livello": lvl,
                        "evidenza": ev.get("evidenza",""),
                        "normativa": ev.get("normativa",""),
                    })

            st.markdown(
                f'<div style="font-size:0.8rem;color:#888;margin-bottom:12px;">'
                f'{len(all_findings)} evidenze attive raccolte dalle sezioni di analisi.</div>',
                unsafe_allow_html=True)

            if st.button("▶ Avvia Super Agent", key="run_super_agent", use_container_width=True):
                _run_with_stream(key, client)
                return

            if parsed:
                render_prose_result(key, parsed)

                # Editable narrative below
                st.markdown("---")
                st.markdown("**Modifica narrativa**")
                narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                             or parsed.get("sintesiEsecutiva","") or "")
                edited_narrative = st.text_area(
                    "Narrativa",
                    value=narrativa,
                    height=200,
                    key="final_agent_edit",
                    label_visibility="collapsed")

                risk_profile_opts = ["Confermato", "Innalzamento", "Abbassamento", "Modifica"]
                risk_profile = st.radio("Profilo di rischio", risk_profile_opts,
                                        horizontal=True, key="final_agent_risk",
                                        label_visibility="collapsed")
                if st.button("💾 Salva modifiche", key="final_agent_save"):
                    new_content = content.replace(narrativa, edited_narrative) if narrativa else content
                    st.session_state.edited_content[key] = new_content
                    st.session_state.kyc_state.add_result(key, new_content)
                    st.success("Modifiche salvate.")

        st.markdown("---")
        if st.button("← Torna all'analisi", key="back_to_analysis"):
            st.session_state.step = "analysis"
            st.rerun()


# ── ROUTER ───────────────────────────────────────────────────────
step = st.session_state.step
if step == "setup":
    render_setup()
elif step == "upload":
    render_upload()
elif step in ("mode_config", "analysis"):
    render_analysis()
elif step == "final":
    render_final_valuation()
else:
    render_setup()
