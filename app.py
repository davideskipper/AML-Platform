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
from kyc_platform.utils import validate_agent_output

st.set_page_config(
    page_title="AML IntelliGent Platform | Bain & Company",
    page_icon="🔍", layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Design system constants ───────────────────────────────────────
BG       = "#F7F8FA"
SB_BG    = "#1A1F2E"
ACCENT   = "#C41E3A"
BLUE     = "#2E5FA3"
TEXT     = "#1A1A2E"
TEXT_SEC = "#6B7280"
BORDER   = "#E5E7EB"
GREEN    = "#16A34A"
YELLOW   = "#D97706"
DANGER   = "#DC2626"
RED      = ACCENT   # legacy alias

st.markdown(f"""
<style>
  /* ── Base ── */
  .stApp, [data-testid="stAppViewContainer"] {{
    background: {BG} !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif !important;
    color: {TEXT} !important;
  }}
  [data-testid="stHeader"] {{
    background: #fff !important;
    border-bottom: 1px solid {BORDER} !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
  }}
  #MainMenu, footer, [data-testid="stToolbar"] {{ display: none !important; visibility: hidden !important; }}
  section[data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display: none !important; }}
  [data-testid="block-container"] {{ padding-top: 1.2rem !important; padding-bottom: 2rem !important; }}

  /* ── Typography ── */
  h1, h2, h3, h4 {{ color: {TEXT} !important; font-weight: 600 !important; letter-spacing: -0.2px !important; }}
  label {{ color: {TEXT_SEC} !important; }}
  p {{ color: {TEXT} !important; line-height: 1.65 !important; }}

  /* ── Inputs ── */
  .stTextInput input, .stNumberInput input {{
    background: #fff !important; color: {TEXT} !important;
    border: 1px solid {BORDER} !important; border-radius: 6px !important;
    font-size: 0.875rem !important; padding: 8px 12px !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
  }}
  .stTextInput input:focus, .stNumberInput input:focus {{
    border-color: {BLUE} !important;
    box-shadow: 0 0 0 3px rgba(46,95,163,0.12) !important;
    outline: none !important;
  }}
  .stTextArea textarea {{
    background: #fff !important; color: {TEXT} !important;
    border: 1px solid {BORDER} !important; border-radius: 6px !important;
    font-size: 0.84rem !important; line-height: 1.6 !important;
    transition: border-color 0.15s !important;
  }}
  .stTextArea textarea:focus {{
    border-color: {BLUE} !important;
    box-shadow: 0 0 0 3px rgba(46,95,163,0.12) !important;
  }}
  .stSelectbox > div > div {{
    background: #fff !important; color: {TEXT} !important;
    border: 1px solid {BORDER} !important; border-radius: 6px !important;
    font-size: 0.875rem !important;
  }}

  /* ── Buttons ── */
  .stButton > button {{
    background: #E5E7EB !important; color: #111827 !important;
    border: 1px solid #D1D5DB !important; border-radius: 6px !important;
    font-weight: 600 !important; font-size: 0.875rem !important;
    padding: 8px 20px !important; letter-spacing: 0.1px !important;
    transition: background 0.15s, transform 0.1s, box-shadow 0.15s !important;
  }}
  .stButton > button:hover {{
    background: #D1D5DB !important; transform: translateY(-1px) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10) !important;
  }}
  .stButton > button:active {{ transform: translateY(0) !important; }}
  .stButton > button:disabled {{
    background: #F3F4F6 !important; color: #9CA3AF !important;
    cursor: not-allowed !important; transform: none !important; box-shadow: none !important;
  }}

  /* ── Progress ── */
  .stProgress > div > div {{ background: #E5E7EB !important; border-radius: 4px !important; }}
  .stProgress > div > div > div {{ background: #1E2328 !important; border-radius: 4px !important; }}

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {{
    background: #fff !important; border: 2px dashed {BORDER} !important;
    border-radius: 8px !important; transition: border-color 0.2s !important;
  }}
  [data-testid="stFileUploader"]:hover {{ border-color: {BLUE} !important; }}

  /* ── Radio ── */
  .stRadio label {{
    color: {TEXT} !important; text-transform: none !important;
    letter-spacing: 0 !important; font-size: 0.875rem !important;
  }}

  /* ── Expander ── */
  details summary {{ color: {TEXT} !important; font-weight: 500 !important; }}
  details {{ background: #fff !important; border: 1px solid {BORDER} !important; border-radius: 8px !important; }}

  /* ── Bordered containers (st.container(border=True)) styled as cards ── */
  [data-testid="stVerticalBlockBorderWrapper"] {{
    background: #fff !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    padding: 18px 22px !important;
    margin-bottom: 16px !important;
    box-shadow: none !important;
  }}

  /* ── Alerts ── */
  [data-testid="stAlert"] {{ border-radius: 6px !important; }}

  /* ── Scrollbar ── */
  ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
  ::-webkit-scrollbar-track {{ background: #f1f5f9; }}
  ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 3px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

  /* ── HR ── */
  hr {{ border-color: {BORDER} !important; margin: 1rem 0 !important; }}

  /* ── Animations ── */
  @keyframes aml-spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
  .aml-spin {{ display: inline-block !important; animation: aml-spin 1s linear infinite !important; }}
  @keyframes aml-pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.5; }} }}
  .aml-pulse {{ animation: aml-pulse 1.5s ease-in-out infinite !important; }}

  /* ── Tabs ── */
  [data-testid="stTabs"] [data-testid="stTab"] {{
    font-size: 0.82rem !important; font-weight: 500 !important; padding: 8px 16px !important;
  }}
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
    "LOW": GREEN, "MEDIUM": YELLOW, "HIGH": DANGER, "CRITICAL": "#7C3AED",
    "BASSO": GREEN, "MEDIO": YELLOW, "MEDIO-ALTO": "#F97316",
    "ALTO": DANGER, "CRITICO": "#7C3AED", "NON_VALUTABILE": TEXT_SEC,
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
    "excel_raw_bytes": None,
    "excel_name": None,
    "edited_content": {},
    "agent_log": [],
    "active_section": "registry",
    "run_queue": [],
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
    return RISK_COLORS.get((level or "").upper(), TEXT_SEC)


def risk_badge(level: str) -> str:
    """Return HTML badge for a risk/evidence level."""
    _cfg = {
        "LOW":           ("#DCFCE7", "#15803D", "BASSO"),
        "BASSO":         ("#DCFCE7", "#15803D", "BASSO"),
        "MEDIUM":        ("#FEF9C3", "#92400E", "MEDIO"),
        "MEDIO":         ("#FEF9C3", "#92400E", "MEDIO"),
        "MEDIO-ALTO":    ("#FFEDD5", "#C2410C", "MEDIO-ALTO"),
        "HIGH":          ("#FEE2E2", "#B91C1C", "ALTO"),
        "ALTO":          ("#FEE2E2", "#B91C1C", "ALTO"),
        "CRITICAL":      ("#F3E8FF", "#6B21A8", "CRITICO"),
        "CRITICO":       ("#F3E8FF", "#6B21A8", "CRITICO"),
        "NON_VALUTABILE":("#F3F4F6", "#6B7280", "N/V"),
        "ATTENZIONE":    ("#DCFCE7", "#15803D", "ATTENZIONE"),
        "ANOMALIA":      ("#FEF9C3", "#92400E", "ANOMALIA"),
    }
    bg, fg, label = _cfg.get((level or "").upper(), ("#F3F4F6", "#6B7280", level or "—"))
    return (f'<span style="display:inline-block;background:{bg};color:{fg};'
            f'font-size:0.68rem;font-weight:700;letter-spacing:0.4px;'
            f'padding:2px 9px;border-radius:20px;">{label}</span>')

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
            raw = st.session_state.get("excel_raw_bytes") or st.session_state.get("excel_path")
            # If raw bytes have been consumed, try re-creating from section docs text
            if raw is None and docs_text:
                import io as _bio
                raw = _bio.BytesIO(docs_text.encode("utf-8", errors="replace"))
                raw.name = "transazioni.csv"
            result = transaction_agent.run(client, raw, company, manual_ctx,
                                           show_output=False, on_token=on_token,
                                           on_thinking=on_thinking)
        elif key == "final_valuation":
            result = final_valuation_agent.run(client, company, state.results, manual_ctx,
                                               show_output=False, on_token=on_token,
                                               on_thinking=on_thinking)
        else:
            raise ValueError(f"Sezione sconosciuta: {key}")
        is_valid, val_error = validate_agent_output(key, result)
        if not is_valid:
            log_event(sec["label"], f"⚠ Validazione: {val_error}", "error")
            st.warning(f"Output non valido — {val_error}")
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
        num   = str(i + 1)
        if i < current_idx:
            num_style  = f"background:{BLUE};color:#fff;"
            label_style = f"color:{BLUE};font-weight:500;"
            num_label   = "✓"
        elif i == current_idx:
            num_style  = f"background:{ACCENT};color:#fff;"
            label_style = f"color:{TEXT};font-weight:700;"
            num_label   = num
        else:
            num_style  = f"background:{BORDER};color:{TEXT_SEC};"
            label_style = f"color:{TEXT_SEC};font-weight:400;"
            num_label   = num
        parts.append(
            f'<span style="display:inline-flex;align-items:center;gap:6px;">'
            f'<span style="{num_style}width:20px;height:20px;border-radius:50%;'
            f'font-size:0.62rem;font-weight:700;display:inline-flex;'
            f'align-items:center;justify-content:center;">{num_label}</span>'
            f'<span style="{label_style}font-size:0.8rem;">{label}</span>'
            f'</span>'
        )
        if i < len(_STEP_ORDER) - 1:
            parts.append(f'<span style="color:{BORDER};margin:0 10px;font-size:0.8rem;">──</span>')

    st.markdown(
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;'
        f'padding:8px 0 12px;margin-bottom:2px;border-bottom:1px solid {BORDER};">'
        + "".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


# ── Header ────────────────────────────────────────────────────────
def _try_extract_company_name() -> str:
    """Try to extract the company name from registry or other agent results."""
    import re as _re
    for key in ("registry", "ubo_pep", "reputational"):
        content = get_content(key)
        if not content:
            continue
        parsed = parse_json_result(content)
        if parsed:
            narr = (parsed.get("narrativa") or parsed.get("narrativaCompleta") or "")
            # Look for patterns like "Società XYZ S.r.l.", "ABC S.p.A.", "XYZ Ltd"
            m = _re.search(
                r'\b([A-Z][A-Za-zÀ-ÿ &\'\-\.]+(?:\s+(?:S\.r\.l\.|S\.p\.A\.|S\.n\.c\.|'
                r'S\.a\.s\.|S\.r\.l\.S\.|Ltd\.?|Limited|GmbH|S\.A\.|Srl|Spa|SAS|LLC))?)\b',
                narr)
            if m:
                candidate = m.group(1).strip()
                if 4 <= len(candidate) <= 60:
                    return candidate
    return ""


def render_header():
    state = st.session_state.kyc_state

    # Auto-fill company name from agent results if still placeholder
    if state.case.company_name in ("", "Controparte N/D"):
        extracted = _try_extract_company_name()
        if extracted:
            state.case.company_name = extracted

    h_left, h_right = st.columns([7, 1])
    with h_left:
        if st.session_state.step in ("analysis", "final"):
            done, total = main_progress()
            pct  = int(done / total * 100)
            rc   = GREEN if done == total else ACCENT
            prog_bar = (
                f'<div style="display:inline-flex;align-items:center;gap:6px;'
                f'background:{"#DCFCE7" if done==total else "#FEE2E2"};'
                f'padding:2px 10px;border-radius:20px;">'
                f'<span style="font-size:0.62rem;font-weight:700;color:{rc};">{done}/{total}</span>'
                f'</div>'
            )
            st.markdown(
                f'<div style="padding:8px 0 10px;margin-bottom:6px;'
                f'display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
                + _logo_html(30) +
                f'<span style="color:{BORDER};font-size:1.2rem;margin:0 2px;">|</span>'
                f'<span style="font-size:0.72rem;color:{TEXT_SEC};font-weight:500;letter-spacing:0.5px;">AML IntelliGent Platform · KYC/CDD</span>'
                f'<span style="color:{BORDER};font-size:1.2rem;margin:0 2px;">|</span>'
                f'<span style="font-size:0.9rem;font-weight:700;color:{TEXT};">{state.case.company_name}</span>'
                + (f'<span style="font-size:0.72rem;color:{TEXT_SEC};">{state.case.case_id}</span>' if state.case.case_id else '')
                + prog_bar +
                f'</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div style="padding:8px 0 10px;margin-bottom:6px;'
                f'display:flex;align-items:center;gap:10px;">'
                + _logo_html(30) +
                f'<span style="color:{BORDER};font-size:1.2rem;margin:0 2px;">|</span>'
                f'<span style="font-size:0.72rem;color:{TEXT_SEC};font-weight:500;letter-spacing:0.5px;">AML IntelliGent Platform · KYC/CDD</span>'
                f'</div>',
                unsafe_allow_html=True)
    with h_right:
        st.markdown(
            f'<div style="text-align:right;padding-top:10px;font-size:0.62rem;'
            f'color:{TEXT_SEC};font-weight:500;">claude-sonnet-4-6</div>',
            unsafe_allow_html=True)
    if st.session_state.step not in ("setup", ""):
        render_step_nav(st.session_state.step)


# ── render_prose_result ───────────────────────────────────────────
def render_prose_result(key: str, parsed: dict):
    """Displays agent result as professional card — no raw JSON."""
    risk      = parsed.get("rischioComplessivo","") or parsed.get("customerRiskRating","")
    narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                 or parsed.get("sintesiEsecutiva","") or "")
    evidenze  = parsed.get("principaliEvidenze", [])
    flags     = parsed.get("flags", [])

    # ── Risk header bar ──────────────────────────────────────────
    if risk:
        rc   = get_risk_color(risk)
        racc = parsed.get("raccomandazione","")
        racc_str = ""
        if isinstance(racc, dict):
            parts_r = [x for x in [racc.get("accettazione",""),
                                    racc.get("livelloAdeguataVerifica",""),
                                    racc.get("frequenzaMonitoraggio","")] if x]
            if parts_r: racc_str = " · ".join(parts_r)
        elif isinstance(racc, str) and racc:
            racc_str = racc
        st.markdown(
            f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:10px;'
            f'background:#fff;border:1px solid {BORDER};border-left:4px solid {rc};'
            f'border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:18px;">'
            f'<span style="font-size:0.7rem;font-weight:700;letter-spacing:1px;color:{TEXT_SEC};">RISCHIO COMPLESSIVO</span>'
            f'{risk_badge(risk)}'
            + (f'<span style="margin-left:auto;font-size:0.76rem;color:{TEXT_SEC};">{racc_str}</span>' if racc_str else '')
            + f'</div>',
            unsafe_allow_html=True)

    # ── Narrativa ────────────────────────────────────────────────
    if narrativa:
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{TEXT_SEC};margin:14px 0 8px;text-transform:uppercase;">Analisi</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#fff;border:1px solid {BORDER};border-radius:8px;'
            f'padding:18px 22px;font-size:0.875rem;line-height:1.85;color:{TEXT};margin-bottom:18px;">'
            + narrativa.replace("\n", "<br>") + '</div>',
            unsafe_allow_html=True)

    # ── Evidenze table ───────────────────────────────────────────
    if evidenze:
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{TEXT_SEC};margin:6px 0 10px;text-transform:uppercase;">Principali Evidenze</div>',
            unsafe_allow_html=True)
        rows_html = ""
        lv_cfg = {
            "CRITICO":    ("#FEF2F2","#B91C1C"),
            "ANOMALIA":   ("#FFFBEB","#92400E"),
            "ATTENZIONE": ("#F0FDF4","#15803D"),
        }
        for idx, ev in enumerate(evidenze):
            lvl  = (ev.get("livello") or "ATTENZIONE").upper()
            etxt = ev.get("evidenza","")
            ntxt = ev.get("normativa","")
            bg_r, col_r = lv_cfg.get(lvl, lv_cfg["ATTENZIONE"])
            row_bg = "#fff" if idx % 2 == 0 else f"{BG}"
            rows_html += (
                f'<tr style="background:{row_bg};">'
                f'<td style="padding:8px 10px;border-bottom:1px solid {BORDER};white-space:nowrap;">'
                f'{risk_badge(lvl)}</td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid {BORDER};'
                f'font-size:0.82rem;color:{TEXT};line-height:1.5;">{etxt}</td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid {BORDER};'
                f'font-size:0.72rem;color:{TEXT_SEC};font-style:italic;">{ntxt}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<div style="border:1px solid {BORDER};border-radius:8px;overflow:hidden;margin-bottom:18px;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="background:#F8FAFC;">'
            f'<th style="padding:8px 10px;font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
            f'color:{TEXT_SEC};text-align:left;border-bottom:1px solid {BORDER};text-transform:uppercase;">Livello</th>'
            f'<th style="padding:8px 12px;font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
            f'color:{TEXT_SEC};text-align:left;border-bottom:1px solid {BORDER};text-transform:uppercase;">Evidenza</th>'
            f'<th style="padding:8px 10px;font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
            f'color:{TEXT_SEC};text-align:left;border-bottom:1px solid {BORDER};text-transform:uppercase;">Normativa</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table></div>',
            unsafe_allow_html=True)

    # ── Flags ────────────────────────────────────────────────────
    if flags:
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{TEXT_SEC};margin:6px 0 10px;text-transform:uppercase;">Flag AML</div>',
            unsafe_allow_html=True)
        for fl in flags:
            frc  = get_risk_color(fl.get("rischio",""))
            tipo = fl.get("tipo","")
            desc = fl.get("descrizione","")
            norm = fl.get("riferimentoNormativo","") or fl.get("indicatoreUIF","")
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:10px;'
                f'background:#fff;border:1px solid {BORDER};border-left:3px solid {frc};'
                f'border-radius:0 6px 6px 0;padding:8px 12px;margin-bottom:5px;">'
                f'<div style="flex:1;">'
                f'<span style="font-size:0.8rem;font-weight:600;color:{TEXT};">{tipo}</span>'
                + (f'<span style="font-size:0.78rem;color:{TEXT_SEC};"> — {desc}</span>' if desc else '')
                + (f'<div style="font-size:0.68rem;color:{TEXT_SEC};margin-top:2px;">📎 {norm}</div>' if norm else '')
                + f'</div></div>',
                unsafe_allow_html=True)


# ── STEP 1: SETUP ────────────────────────────────────────────────
def _field_label(text: str, required: bool = False) -> None:
    star = f'<span style="color:{ACCENT};">*</span>' if required else ""
    st.markdown(
        f'<div style="font-size:0.7rem;font-weight:600;letter-spacing:0.5px;'
        f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:3px;">{text}{star}</div>',
        unsafe_allow_html=True)

def render_setup():
    render_header()
    _, col, _ = st.columns([1, 2.4, 1])
    with col:
        # Page title card
        st.markdown(
            f'<div style="background:#fff;border:1px solid {BORDER};border-radius:12px;'
            f'padding:28px 32px;margin-bottom:20px;">'
            f'<div style="font-size:1.45rem;font-weight:700;color:{TEXT};margin-bottom:6px;">'
            f'Nuova Analisi Controparte</div>'
            f'<div style="font-size:0.85rem;color:{TEXT_SEC};">'
            f'Inserisci i dati della controparte e carica la knowledge base normativa</div>'
            f'</div>',
            unsafe_allow_html=True)

        if not get_api_key():
            st.error("⚠️  API Key Anthropic non trovata — aggiungi ANTHROPIC_API_KEY nei Secrets.")

        # ── Controparte card (uses st.container so widgets sit inside) ──
        with st.container(border=True):
            st.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                f'color:{BLUE};text-transform:uppercase;margin-bottom:14px;">Dati Controparte</div>',
                unsafe_allow_html=True)

            _field_label("Ragione Sociale")
            company = st.text_input("Ragione Sociale", placeholder="es. Meridian Capital S.r.l.",
                                    label_visibility="collapsed")
            c1, c2 = st.columns(2)
            with c1:
                _field_label("Paese", required=True)
                country = st.text_input("Paese", placeholder="es. Italia",
                                        label_visibility="collapsed")
            with c2:
                _field_label("Settore")
                sector = st.text_input("Settore", placeholder="es. Wealth Management",
                                       label_visibility="collapsed")
            c3, c4 = st.columns(2)
            with c3:
                # Case ID always auto-generated — shown as read-only label
                auto_case_id = f"AML-{datetime.now().strftime('%Y%m%d-%H%M')}"
                st.markdown(
                    f'<div style="font-size:0.7rem;font-weight:600;letter-spacing:0.5px;'
                    f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:3px;">Case ID</div>'
                    f'<div style="font-size:0.82rem;color:{TEXT_SEC};background:#F8F9FA;'
                    f'border:1px solid {BORDER};border-radius:6px;padding:8px 12px;">'
                    f'{auto_case_id}</div>',
                    unsafe_allow_html=True)
                case_id = auto_case_id
            with c4:
                _field_label("Analista", required=True)
                analyst = st.text_input("Analista", placeholder="es. M. Rossi",
                                        label_visibility="collapsed")

        # ── Knowledge Base card ──────────────────────────────────────
        with st.container(border=True):
            st.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                f'color:{BLUE};text-transform:uppercase;margin-bottom:4px;">Knowledge Base Normativa</div>'
                f'<div style="font-size:0.78rem;color:{TEXT_SEC};margin-bottom:12px;">'
                f'FATF guidelines, circolari UIF, D.Lgs.&nbsp;231/2007, liste sanzioni, policy AML interne.</div>',
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
                st.success(f"✓ {len(texts)} documento/i caricati · {len(st.session_state.knowledge_base):,} caratteri")
            elif st.session_state.kb_doc_names:
                st.markdown(
                    f'<div style="font-size:0.78rem;color:{BLUE};padding:6px 0;">'
                    + " · ".join(f"📄 {n}" for n in st.session_state.kb_doc_names)
                    + '</div>', unsafe_allow_html=True)

        if st.button("Continua → Carica Documenti", use_container_width=True):
            if not country.strip():
                st.error("Il campo Paese è obbligatorio.")
            elif not analyst.strip():
                st.error("Il campo Analista è obbligatorio.")
            elif not get_api_key():
                st.error("Configura ANTHROPIC_API_KEY nei Secrets.")
            else:
                s = st.session_state.kyc_state
                s.case.company_name = company.strip()
                s.case.country      = country.strip()
                s.case.case_id      = case_id
                log_event("Sistema", f"Caso aperto: {s.case.company_name} ({country})", "super")
                # Reset per-case analysis state so agents default to "agent" mode
                st.session_state.section_modes = {}
                st.session_state.section_web   = {}
                st.session_state.run_queue     = []
                for sec in ALL_SECTIONS:
                    st.session_state.pop(f"mode_{sec['key']}", None)
                    st.session_state.pop(f"web_{sec['key']}", None)
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
        st.markdown(
            f'<div style="font-size:1.15rem;font-weight:700;color:{TEXT};margin-bottom:4px;">Carica Documenti</div>'
            f'<div style="font-size:0.82rem;color:{TEXT_SEC};margin-bottom:16px;">'
            f'Prefisso automatico: <b>01_</b> Struttura · <b>02_</b> UBO/PEP · '
            f'<b>03_</b> Reputational · <b>04_</b> Economic · <b>05_</b> Transactional</div>',
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
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                f'color:{TEXT_SEC};text-transform:uppercase;margin:18px 0 10px;">Assegnazione Sezioni</div>',
                unsafe_allow_html=True)

            section_options = [("", "— Non assegnato —")] + [
                (s["key"], f'{s["number"]} · {s["full_label"]}') for s in MAIN_SECTIONS
            ]
            option_labels = [lbl for _, lbl in section_options]
            option_keys   = [k for k, _ in section_options]

            for fd in files_data:
                fname = fd["name"]
                disp  = fname if len(fname) <= 44 else fname[:41] + "..."
                ext   = fd.get("ext","").lstrip(".")
                sz_kb = fd.get("size", 0) // 1024
                row_l, row_r = st.columns([2, 3])
                with row_l:
                    st.markdown(
                        f'<div style="background:#fff;border:1px solid {BORDER};border-radius:6px;'
                        f'padding:8px 12px;margin-bottom:4px;display:flex;align-items:center;gap:8px;">'
                        f'<span style="font-size:0.9rem;">📄</span>'
                        f'<div><div style="font-size:0.82rem;font-weight:500;color:{TEXT};">{disp}</div>'
                        f'<div style="font-size:0.68rem;color:{TEXT_SEC};">{ext.upper()} · {sz_kb} KB</div>'
                        f'</div></div>',
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

        if not files_data:
            st.markdown(
                f'<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;'
                f'padding:10px 14px;margin:10px 0;font-size:0.8rem;color:{BLUE};">'
                f'ℹ️ Nessun documento caricato — gli agenti utilizzeranno la ricerca web.</div>',
                unsafe_allow_html=True)

        st.markdown(f'<div style="height:12px;"></div>', unsafe_allow_html=True)
        nav_l, nav_r = st.columns([1, 1])
        with nav_l:
            if st.button("← Indietro", key="upload_back", use_container_width=True):
                st.session_state.step = "setup"
                st.rerun()
        with nav_r:
            if st.button("▶ Avvia Analisi", key="upload_next", use_container_width=True):
                # Build section_docs / excel_raw_bytes (same logic as mode_config used to do)
                _files_data   = st.session_state.uploaded_files_data
                _file_assigns = st.session_state.file_assignments
                _sec_docs, _sec_doc_names = {}, {}
                for _sec in MAIN_SECTIONS:
                    _sk = _sec["key"]
                    _asgn = [fd for fd in _files_data if _file_assigns.get(fd["name"]) == _sk]
                    if not _asgn:
                        continue
                    if _sk == "transaction":
                        _fd  = _asgn[0]
                        _raw = _fd.get("raw_bytes")
                        import io as _io
                        if _raw:
                            _buf = _io.BytesIO(_raw)
                        else:
                            _buf = _io.BytesIO(_fd["content_text"].encode("utf-8", errors="replace"))
                        _buf.name = _fd["name"]
                        st.session_state.excel_raw_bytes = _buf
                        st.session_state.excel_name      = _fd["name"]
                        _sec_doc_names[_sk] = [_fd["name"]]
                    else:
                        _sec_docs[_sk]      = "\n\n".join(
                            f"=== {fd['name']} ===\n{fd['content_text']}" for fd in _asgn)
                        _sec_doc_names[_sk] = [fd["name"] for fd in _asgn]
                st.session_state.section_docs      = _sec_docs
                st.session_state.section_doc_names = _sec_doc_names
                # Default every section to agent mode
                for _sec in MAIN_SECTIONS:
                    st.session_state.section_modes[_sec["key"]] = "agent"
                    st.session_state.section_web[_sec["key"]]   = False
                # Queue all sections
                st.session_state.run_queue      = [s["key"] for s in MAIN_SECTIONS]
                st.session_state.active_section = "registry"
                # Clean up upload state so nothing ghosts
                st.session_state.uploaded_files_data = []
                st.session_state.file_assignments    = {}
                st.session_state.upload_hash         = ""
                for _k in list(st.session_state.keys()):
                    if _k.startswith("assign_"):
                        del st.session_state[_k]
                st.session_state.step = "transit"
                st.rerun()


# ── STEP 3: MODE CONFIG ───────────────────────────────────────────
def render_mode_config():
    render_header()
    _, col, _ = st.columns([0.5, 5, 0.5])
    with col:
        st.markdown(
            f'<div style="font-size:1.15rem;font-weight:700;color:{TEXT};margin-bottom:4px;">Configura Modalità Analisi</div>'
            f'<div style="font-size:0.82rem;color:{TEXT_SEC};margin-bottom:18px;">'
            f'Scegli per ogni sezione se usare l\'agente AI o inserire l\'analisi manualmente.</div>',
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
                f'<div style="background:#fff;border:1px solid {BORDER};border-radius:10px;'
                f'padding:14px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
                f'<span style="font-size:1.05rem;">{sec["icon"]}</span>'
                f'<span style="font-size:0.62rem;color:{TEXT_SEC};font-weight:700;letter-spacing:0.5px;">{sec["number"]}</span>'
                f'<span style="font-size:0.92rem;font-weight:600;color:{TEXT};">{sec["full_label"]}</span>'
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
                        f'<span style="font-size:0.72rem;color:{TEXT_SEC};">Nessun documento assegnato</span>',
                        unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f'<div style="height:12px;"></div>', unsafe_allow_html=True)
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
                        raw = fd.get("raw_bytes")
                        if raw:
                            # Pass raw bytes directly — no tempfile needed
                            import io as _io
                            buf = _io.BytesIO(raw)
                            buf.name = fd["name"]       # give it a name so _read_excel detects ext
                            st.session_state.excel_raw_bytes = buf
                        else:
                            # Fallback: encode text as UTF-8 BytesIO
                            import io as _io
                            buf = _io.BytesIO(fd["content_text"].encode("utf-8", errors="replace"))
                            buf.name = fd["name"]
                            st.session_state.excel_raw_bytes = buf
                        st.session_state.excel_name = fd["name"]
                        section_doc_names[skey] = [fd["name"]]
                    else:
                        texts = [f"=== {fd['name']} ===\n{fd['content_text']}" for fd in assigned]
                        names = [fd["name"] for fd in assigned]
                        section_docs[skey]      = "\n\n".join(texts)
                        section_doc_names[skey] = names

                st.session_state.section_docs     = section_docs
                st.session_state.section_doc_names = section_doc_names

                # Build run_queue — only agent-mode sections that have docs
                run_queue = [s["key"] for s in MAIN_SECTIONS
                             if st.session_state.section_modes.get(s["key"]) == "agent"]
                st.session_state.run_queue = run_queue
                st.session_state.active_section = "registry"
                # Use transit step to force a blank DOM frame before analysis,
                # which clears all stale mode_config widgets from the browser.
                st.session_state.step = "transit"
                # Clear upload data so it cannot ghost in the analysis page
                st.session_state.uploaded_files_data = []
                st.session_state.file_assignments    = {}
                st.session_state.upload_hash         = ""
                # Remove mode_config widget keys to prevent ghost rendering
                for s in MAIN_SECTIONS:
                    st.session_state.pop(f"mode_{s['key']}", None)
                    st.session_state.pop(f"web_{s['key']}", None)
                for k in list(st.session_state.keys()):
                    if k.startswith("assign_"):
                        del st.session_state[k]
                st.session_state.pop("mode_back", None)
                st.session_state.pop("mode_next", None)
                st.rerun()


# ── STREAMING helper ──────────────────────────────────────────────
def _run_with_stream(key: str, client):
    """Run agent with live streaming. Must be called inside the desired column context."""
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
                f'<div style="font-size:0.68rem;color:rgba(148,163,184,0.9);font-style:italic;'
                f'border-left:2px solid rgba(255,255,255,0.1);padding-left:10px;margin-bottom:8px;">'
                + th.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                + '</div>')
        if buf["text"]:
            disp = buf["text"][-4000:] if len(buf["text"]) > 4000 else buf["text"]
            parts.append(
                f'<div style="font-family:\'SFMono-Regular\',Consolas,monospace;'
                f'font-size:0.73rem;white-space:pre-wrap;color:#E2E8F0;line-height:1.6;">'
                + disp.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                + '</div>')
        if parts:
            stream_box.markdown(
                f'<div style="background:#0F172A;border-radius:8px;'
                f'padding:20px 24px;width:100%;">'
                + "".join(parts) + '</div>',
                unsafe_allow_html=True)

    def on_thinking(chunk):
        buf["thinking"] += chunk
        buf["phase"] = "thinking"
        status_box.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;">'
            f'<span class="aml-spin" style="font-size:0.85rem;color:{TEXT_SEC};">⚙</span>'
            f'<span style="font-size:0.78rem;font-weight:600;color:{TEXT_SEC};">Ragionamento in corso…</span>'
            f'</div>', unsafe_allow_html=True)
        _render()

    def on_token(chunk):
        buf["text"] += chunk
        buf["phase"] = "writing"
        status_box.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;">'
            f'<span class="aml-pulse" style="color:{ACCENT};font-size:0.85rem;">✦</span>'
            f'<span style="font-size:0.78rem;font-weight:600;color:{ACCENT};">Redazione output…</span>'
            f'</div>', unsafe_allow_html=True)
        _render()

    try:
        run_section(key, client, on_token=on_token, on_thinking=on_thinking)
        st.rerun()
    except Exception as e:
        status_box.empty()
        stream_box.empty()
        st.error(f"❌ Errore agente **{key}**: {e}")
        st.session_state.pop("running_agent", None)



# ── Criticality panel ─────────────────────────────────────────────
def _render_crit_panel(key: str):
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    if not parsed:
        st.markdown(
            f'<div style="color:{TEXT_SEC};font-size:0.8rem;padding:12px;">'
            f'Nessun risultato disponibile.</div>',
            unsafe_allow_html=True)
        return

    evidenze  = parsed.get("principaliEvidenze", [])
    overrides = st.session_state.crit_overrides.get(key, {})

    critics  = [(i, ev) for i, ev in enumerate(evidenze)
                if (ev.get("livello","") or "").upper().startswith("CRITICO")]
    anomalie = [(i, ev) for i, ev in enumerate(evidenze)
                if (ev.get("livello","") or "").upper().startswith("ANOMALIA")]

    def _render_group(group, grp_label, grp_color):
        if not group:
            return
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
            f'color:{grp_color};margin:12px 0 8px;text-transform:uppercase;">{grp_label}</div>',
            unsafe_allow_html=True)
        for idx, ev in group:
            ov = overrides.get(idx, {})
            is_closed = (ov.get("status","") or "").lower() == "chiuso"
            etxt = ev.get("evidenza","")
            ntxt = ev.get("normativa","")
            lvl  = (ev.get("livello","") or "").upper()
            brd_c = DANGER if lvl.startswith("CRITICO") else YELLOW
            bg_c  = "#FEF2F2" if lvl.startswith("CRITICO") else "#FFFBEB"
            opacity = "opacity:0.45;" if is_closed else ""
            status_pill = ""
            if ov:
                st_color = GREEN if ov.get("status","") == "Chiuso" else TEXT_SEC
                status_pill = (f'<span style="font-size:0.62rem;color:{st_color};'
                               f'font-weight:600;">{ov.get("status","")}</span>')

            st.markdown(
                f'<div style="background:{bg_c};border-left:3px solid {brd_c};'
                f'border-radius:0 6px 6px 0;padding:10px 12px;margin-bottom:6px;{opacity}">'
                f'<div style="font-size:0.8rem;color:{TEXT};font-weight:600;'
                f'margin-bottom:4px;line-height:1.4;">{etxt}</div>'
                + (f'<div style="font-size:0.7rem;color:{TEXT_SEC};">📎 {ntxt}</div>' if ntxt else '')
                + (f'<div style="margin-top:5px;">{status_pill}</div>' if status_pill else '')
                + '</div>',
                unsafe_allow_html=True)

            edit_key = f"crit_edit_{key}_{idx}"
            if st.button("Aggiorna stato ▾", key=f"crit_btn_{key}_{idx}"):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                st.rerun()

            if st.session_state.get(edit_key, False):
                with st.form(key=f"crit_form_{key}_{idx}"):
                    cur_status  = ov.get("status","Confermato")
                    cur_motiv   = ov.get("motivation","")
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

    _render_group(critics,  "🔴 Criticità", DANGER)
    _render_group(anomalie, "🟡 Attenzioni", YELLOW)

    if not critics and not anomalie:
        st.markdown(
            f'<div style="text-align:center;padding:20px 0;color:{TEXT_SEC};font-size:0.8rem;">'
            f'✓ Nessuna criticità aperta</div>',
            unsafe_allow_html=True)


# ── Section content ───────────────────────────────────────────────
def _render_section_content(key: str, client):
    sec     = next(s for s in MAIN_SECTIONS if s["key"] == key)
    status  = sec_status(key)
    content = get_content(key)
    parsed  = parse_json_result(content) if content else None
    mode    = st.session_state.section_modes.get(key, "agent")

    # Section header
    risk_val = (parsed.get("rischioComplessivo","") if parsed else "") or ""
    badge_html = risk_badge(risk_val) if risk_val else ""
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'border-bottom:1px solid {BORDER};padding-bottom:12px;margin-bottom:18px;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-size:0.62rem;color:{TEXT_SEC};font-weight:700;'
        f'letter-spacing:0.8px;">{sec["number"]}</span>'
        f'<span style="font-size:1rem;font-weight:700;color:{TEXT};">'
        f'{sec["icon"]} {sec["full_label"]}</span>'
        f'</div>'
        + badge_html +
        f'</div>',
        unsafe_allow_html=True)

    # ── Manual mode ───────────────────────────────────────────────
    if mode == "manual":
        val = st.session_state.get(f"manual_text_{key}", content or "")
        new_val = st.text_area("Analisi manuale", value=val, height=300,
                               key=f"manual_ta_{key}", label_visibility="collapsed")
        btn_s, btn_r, _ = st.columns([1, 1, 2])
        with btn_s:
            if st.button("💾 Salva", key=f"manual_save_{key}", use_container_width=True):
                st.session_state.edited_content[key] = new_val
                st.session_state.kyc_state.add_result(key, new_val)
                st.rerun()
        with btn_r:
            if st.button("↺ Avvia Agente", key=f"manual_rerun_{key}", use_container_width=True):
                st.session_state.section_modes[key] = "agent"
                st.session_state.run_queue = [key]
                st.rerun()
        return

    # ── Agent mode: completed ─────────────────────────────────────
    if status == "completed" and content:
        if parsed:
            rc = get_risk_color(risk_val) if risk_val else BLUE
            narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                         or parsed.get("sintesiEsecutiva","") or "")
            if narrativa:
                # Split narrativa into sintesi + proposta di azione
                import re as _re
                paras = [p.strip() for p in _re.split(r'\n{2,}', narrativa) if p.strip()]
                if len(paras) == 1:
                    # Single block — split by newline
                    paras = [p.strip() for p in narrativa.split("\n") if p.strip()]
                if len(paras) >= 3:
                    sintesi  = "\n".join(paras[:-2])
                    proposta = "\n".join(paras[-2:])
                elif len(paras) == 2:
                    sintesi, proposta = paras[0], paras[1]
                else:
                    # Single paragraph — split at sentence level near end
                    sentences = _re.split(r'(?<=[.!?])\s+', narrativa.strip())
                    if len(sentences) >= 4:
                        mid = max(1, len(sentences) - 2)
                        sintesi  = " ".join(sentences[:mid])
                        proposta = " ".join(sentences[mid:])
                    else:
                        sintesi, proposta = narrativa, ""

                # Card 1 — Sintesi complessiva
                st.markdown(
                    f'<div style="font-size:0.62rem;font-weight:700;letter-spacing:1px;'
                    f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:5px;">'
                    f'Sintesi complessiva dell\'analisi</div>'
                    f'<div style="background:#fff;border:1px solid {BORDER};'
                    f'border-left:4px solid {rc};border-radius:0 8px 8px 0;'
                    f'padding:16px 20px;font-size:0.875rem;'
                    f'line-height:1.85;color:{TEXT};margin-bottom:12px;">'
                    + sintesi.replace("\n","<br>") + '</div>',
                    unsafe_allow_html=True)

                # Card 2 — Proposta di azione: raccomandazione + conclusione narrativa
                _racc_raw = parsed.get("raccomandazione","")
                _racc_str = ""
                if isinstance(_racc_raw, dict):
                    _rp = [x for x in [_racc_raw.get("accettazione",""),
                                        _racc_raw.get("livelloAdeguataVerifica",""),
                                        _racc_raw.get("frequenzaMonitoraggio","")] if x]
                    _racc_str = " · ".join(_rp) if _rp else ""
                elif isinstance(_racc_raw, str):
                    _racc_str = _racc_raw.strip()

                # Map recommendation codes to descriptive Italian text
                _racc_map = {
                    "PROCEED":                 ("Accettazione",          "#15803D", "#DCFCE7",
                        "Profilo di rischio conforme alle soglie di accettazione. Si raccomanda adeguata verifica ordinaria con aggiornamento periodico del fascicolo."),
                    "ENHANCED_MONITORING":     ("Monitoraggio Rafforzato","#92400E", "#FFFBEB",
                        "Il profilo presenta elementi di attenzione che richiedono sorveglianza continuativa. Si raccomanda revisione semestrale del fascicolo, aggiornamento della documentazione e segnalazione interna al responsabile AML."),
                    "ESCALATE_TO_COMPLIANCE":  ("Escalation Compliance",  "#B91C1C", "#FEE2E2",
                        "Rilevate criticità significative. Il fascicolo deve essere trasmesso al Responsabile AML/Compliance per valutazione approfondita prima di qualsiasi decisione operativa."),
                    "RIFIUTO":                 ("Rifiuto Relazione",      "#6B21A8", "#F3E8FF",
                        "Il profilo di rischio è incompatibile con la policy di accettazione. Si raccomanda il rifiuto dell'instaurazione o la cessazione del rapporto con eventuale valutazione di segnalazione alle autorità competenti."),
                }
                _racc_key = _racc_str.upper().replace(" ","_") if _racc_str else ""
                _racc_info = _racc_map.get(_racc_key)

                # Build proposta content
                _proposta_parts = []
                if _racc_info:
                    _rl, _rc_fg, _rc_bg, _rdesc = _racc_info
                    _proposta_parts.append(
                        f'<div style="display:inline-block;background:{_rc_bg};color:{_rc_fg};'
                        f'font-size:0.72rem;font-weight:700;padding:3px 12px;border-radius:20px;'
                        f'margin-bottom:10px;">{_rl}</div>'
                        f'<div style="font-size:0.875rem;color:{TEXT};line-height:1.8;">{_rdesc}</div>'
                    )
                if proposta:
                    sep = '<div style="height:1px;background:#E5E7EB;margin:10px 0;"></div>' if _proposta_parts else ""
                    _proposta_parts.append(
                        sep + f'<div style="font-size:0.875rem;color:{TEXT};line-height:1.85;">'
                        + proposta.replace("\n","<br>") + '</div>'
                    )

                if _proposta_parts:
                    st.markdown(
                        f'<div style="font-size:0.62rem;font-weight:700;letter-spacing:1px;'
                        f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:5px;">'
                        f'Proposta di azione</div>'
                        f'<div style="background:#F8F9FA;border:1px solid {BORDER};'
                        f'border-left:4px solid #1E2328;border-radius:0 8px 8px 0;'
                        f'padding:16px 20px;margin-bottom:16px;">'
                        + "".join(_proposta_parts) + '</div>',
                        unsafe_allow_html=True)

            # AML flags — sorted: CRITICAL → HIGH → MEDIUM → LOW
            flags = parsed.get("flags", [])
            if flags:
                _flag_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
                flags = sorted(flags, key=lambda f: _flag_order.get(
                    (f.get("rischio","") or "").upper(), 4))
                st.markdown(
                    f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                    f'color:{TEXT_SEC};margin:6px 0 8px;text-transform:uppercase;">Flag AML</div>',
                    unsafe_allow_html=True)
                _flag_cfg = {
                    "CRITICAL": ("#F3E8FF", "#7C3AED", "#7C3AED"),
                    "HIGH":     ("#FEE2E2", "#B91C1C", "#DC2626"),
                    "MEDIUM":   ("#FFFBEB", "#92400E", "#D97706"),
                    "LOW":      ("#F3F4F6", "#6B7280", "#9CA3AF"),
                }
                for fl in flags:
                    rischio = (fl.get("rischio","") or "").upper()
                    bg_f, fg_f, bd_f = _flag_cfg.get(rischio, ("#F3F4F6","#6B7280","#9CA3AF"))
                    tipo = fl.get("tipo","")
                    desc = fl.get("descrizione","")
                    norm = fl.get("riferimentoNormativo","") or fl.get("indicatoreUIF","")
                    st.markdown(
                        f'<div style="display:flex;align-items:flex-start;gap:10px;'
                        f'background:{bg_f};border:1px solid {BORDER};border-left:3px solid {bd_f};'
                        f'border-radius:0 6px 6px 0;padding:8px 12px;margin-bottom:5px;">'
                        f'<div style="flex:1;">'
                        f'<span style="font-size:0.8rem;font-weight:600;color:{fg_f};">{tipo}</span>'
                        + (f'<span style="font-size:0.78rem;color:{TEXT_SEC};"> — {desc}</span>' if desc else '')
                        + (f'<div style="font-size:0.68rem;color:{TEXT_SEC};margin-top:2px;">📎 {norm}</div>' if norm else '')
                        + f'</div></div>',
                        unsafe_allow_html=True)

            # Action row: re-run + edit JSON
            st.markdown(f'<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
            btn_rr, btn_ed, _ = st.columns([1, 1, 2])
            with btn_rr:
                if st.button("↺ Riesegui Agente", key=f"rerun_{key}", use_container_width=True):
                    st.session_state.section_modes[key] = "agent"
                    st.session_state.run_queue = [key]
                    st.rerun()
            with btn_ed:
                etk = f"show_edit_{key}"
                if st.button("✏️ Modifica JSON", key=f"edit_toggle_{key}", use_container_width=True):
                    st.session_state[etk] = not st.session_state.get(etk, False)
                    st.rerun()
            if st.session_state.get(f"show_edit_{key}", False):
                edited = st.text_area("", value=content, height=300,
                                      key=f"edit_ta_{key}", label_visibility="collapsed")
                if st.button("💾 Salva", key=f"edit_save_{key}"):
                    st.session_state.edited_content[key] = edited
                    st.session_state.kyc_state.add_result(key, edited)
                    st.session_state[f"show_edit_{key}"] = False
                    st.rerun()
        else:
            edited = st.text_area("", value=content, height=300,
                                  key=f"edit_{key}", label_visibility="collapsed")
            if edited != content:
                st.session_state.edited_content[key] = edited
                st.session_state.kyc_state.add_result(key, edited)

    # ── Agent mode: empty ─────────────────────────────────────────
    elif status == "empty":
        st.markdown(
            f'<div style="text-align:center;padding:48px 0;background:#fff;'
            f'border:1px solid {BORDER};border-radius:10px;margin-bottom:12px;">'
            f'<div style="font-size:3rem;opacity:0.12;">{sec["icon"]}</div>'
            f'<div style="font-size:0.85rem;color:{TEXT_SEC};margin-top:10px;font-weight:500;">'
            f'In attesa di analisi</div>'
            f'<div style="font-size:0.75rem;color:{TEXT_SEC};opacity:0.7;margin-top:4px;">'
            f'{sec["desc"]}</div>'
            f'</div>', unsafe_allow_html=True)
        if st.button(f"▶ Avvia {sec['label']}", key=f"run_{key}", use_container_width=True):
            st.session_state.section_modes[key] = "agent"
            st.session_state.run_queue = [key]
            st.rerun()


# Flag color coding for right panel
_FLAG_COLORS = {
    "CRITICAL": ("#F3E8FF", "#7C3AED", "#7C3AED"),  # purple bg, purple text, purple border
    "HIGH":     ("#FEE2E2", "#B91C1C", "#DC2626"),   # red
    "MEDIUM":   ("#FFFBEB", "#92400E", "#D97706"),   # yellow
    "LOW":      ("#F3F4F6", "#6B7280", "#9CA3AF"),   # grey
}
_DEFAULT_FLAG_COLOR = ("#F3F4F6", "#6B7280", "#9CA3AF")


# ── Right panel: agent progress + AML flags feed ──────────────────
def _render_right_panel(queued_key=None):
    """Always-visible right column: agent progress + AML flag feed."""
    done, total = main_progress()

    # ── Custom dark progress bar ──────────────────────────────────
    pct = int(done / total * 100) if total else 0
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        f'<span style="font-size:0.65rem;font-weight:700;letter-spacing:1px;color:{TEXT_SEC};'
        f'text-transform:uppercase;">Agenti</span>'
        f'<span style="font-size:0.72rem;font-weight:700;color:#1E2328;">{done}/{total}</span>'
        f'</div>'
        f'<div style="height:6px;background:#E5E7EB;border-radius:3px;margin-bottom:10px;">'
        f'<div style="width:{pct}%;height:100%;background:#1E2328;border-radius:3px;'
        f'transition:width 0.4s;"></div></div>',
        unsafe_allow_html=True)

    # ── Agent status rows ─────────────────────────────────────────
    all_in_queue = st.session_state.get("run_queue", [])
    for sec in MAIN_SECTIONS:
        k       = sec["key"]
        status  = sec_status(k)
        is_run  = (k == queued_key)
        is_q    = (k in all_in_queue)

        content = get_content(k) if status == "completed" else None
        parsed  = parse_json_result(content) if content else None
        risk    = (parsed.get("rischioComplessivo", "") if parsed else "") or ""
        rc      = get_risk_color(risk) if risk else BORDER

        if is_run:
            dot, dcls = "⚙", ' class="aml-spin"'
            bg  = "#F8F8F8"
            brd = "border:1px solid #1E2328;border-left:3px solid #1E2328;"
            dc  = "#1E2328"
        elif status == "completed":
            dot, dcls = "✓", ""
            bg  = "#fff"
            brd = f"border:1px solid {BORDER};border-left:3px solid #1E2328;"
            dc  = "#1E2328"
        elif is_q:
            dot, dcls = "…", ""
            bg, brd, dc = BG, f"border:1px solid {BORDER};", TEXT_SEC
        else:
            dot, dcls = "○", ""
            bg, brd, dc = BG, f"border:1px solid {BORDER};opacity:0.5;", TEXT_SEC

        badge = risk_badge(risk) if (status == "completed" and risk) else ""
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:7px;padding:7px 10px;'
            f'background:{bg};{brd}border-radius:6px;margin-bottom:4px;">'
            f'<span{dcls} style="color:{dc};font-size:0.7rem;width:13px;text-align:center;">{dot}</span>'
            f'<span style="font-size:0.78rem;color:{TEXT};flex:1;">{sec["icon"]} {sec["label"]}</span>'
            + badge +
            f'</div>',
            unsafe_allow_html=True)

    # ── Final valuation shortcut ──────────────────────────────────
    st.markdown(
        f'<div style="height:1px;background:{BORDER};margin:12px 0 10px;"></div>',
        unsafe_allow_html=True)
    if st.button("⚡ Valutazione Finale", key="go_final_panel", use_container_width=True):
        st.session_state.step = "final"
        st.rerun()


# ── STEP 4: ANALYSIS ─────────────────────────────────────────────
def render_analysis():
    render_header()
    client = get_client()

    # Pop next agent from queue (if any)
    queued_key = None
    if st.session_state.get("run_queue"):
        queued_key = st.session_state["run_queue"][0]
        st.session_state["run_queue"] = st.session_state["run_queue"][1:]
        st.session_state.active_section = queued_key

    # ── Top bar: agent status pills + Valutazione Finale button ──────
    done, total = main_progress()
    all_in_queue = st.session_state.get("run_queue", [])

    # Build status pills for each section
    pills = ""
    for s in MAIN_SECTIONS:
        k = s["key"]
        st_s = sec_status(k)
        is_run = (k == queued_key)
        is_q   = (k in all_in_queue)

        content = get_content(k) if st_s == "completed" else None
        parsed  = parse_json_result(content) if content else None
        risk    = (parsed.get("rischioComplessivo","") if parsed else "") or ""
        rc      = get_risk_color(risk) if risk else TEXT_SEC

        if is_run:
            pb, pf = "rgba(30,35,40,0.08)", "#1E2328"
            icon_html = '<span class="aml-spin" style="font-size:0.65rem;">⚙</span> '
        elif st_s == "completed":
            pb, pf = "#F0F0F0", "#1E2328"
            icon_html = f'<span style="color:{rc};">✓</span> '
        elif is_q:
            pb, pf = BG, TEXT_SEC
            icon_html = '<span>…</span> '
        else:
            pb, pf = BG, TEXT_SEC
            icon_html = '<span style="opacity:0.4;">○</span> '

        risk_dot = (f'<span style="display:inline-block;width:6px;height:6px;'
                    f'border-radius:50%;background:{rc};margin-left:5px;vertical-align:middle;"></span>'
                    if (st_s == "completed" and risk) else "")

        pills += (
            f'<span style="background:{pb};color:{pf};font-size:0.72rem;'
            f'font-weight:600;padding:4px 11px;border-radius:20px;'
            f'border:1px solid {BORDER};white-space:nowrap;">'
            + icon_html + s["label"] + risk_dot + '</span>')

    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:5px;align-items:center;'
            f'padding:2px 0 10px;">' + pills + '</div>',
            unsafe_allow_html=True)
    with top_r:
        if st.button("⚡ Valutazione Finale", key="go_final_top", use_container_width=True):
            st.session_state.step = "final"
            st.rerun()

    # ── Main content (single column) ─────────────────────────────────
    if queued_key:
        sec = next(s for s in ALL_SECTIONS if s["key"] == queued_key)

        # Running agent card
        st.markdown(
            f'<div style="background:#fff;border:1px solid {BORDER};'
            f'border-left:4px solid #1E2328;border-radius:0 10px 10px 0;'
            f'padding:14px 20px;margin-bottom:14px;">'
            f'<div style="display:flex;align-items:center;gap:12px;">'
            f'<span class="aml-spin" style="font-size:1.1rem;color:#1E2328;">⚙</span>'
            f'<div>'
            f'<div style="font-size:0.9rem;font-weight:700;color:{TEXT};">'
            f'{sec["icon"]} {sec["full_label"]}</div>'
            f'<div style="font-size:0.75rem;color:{TEXT_SEC};margin-top:2px;">'
            f'Analisi in corso — attendi 1-2 minuti…</div>'
            f'</div></div></div>',
            unsafe_allow_html=True)

        _run_with_stream(queued_key, client)

    else:
        # ── Idle mode: CTA + tabs ─────────────────────────────────
        if done == total and total > 0:
            st.markdown(
                f'<div style="background:#F0FDF4;border:1px solid #86EFAC;'
                f'border-radius:8px;padding:8px 14px;margin-bottom:8px;'
                f'font-size:0.8rem;color:#15803D;font-weight:600;">'
                f'✓ Tutte le sezioni completate — la valutazione finale è disponibile.</div>',
                unsafe_allow_html=True)

        tab_labels = [f"{s['icon']} {s['label']}" for s in MAIN_SECTIONS]
        tabs = st.tabs(tab_labels)
        for tab, sec in zip(tabs, MAIN_SECTIONS):
            with tab:
                _render_section_content(sec["key"], client)



# ── STEP 5: FINAL VALUATION ───────────────────────────────────────
def render_final_valuation():
    render_header()
    _, col, _ = st.columns([0.3, 5.4, 0.3])
    with col:
        st.markdown(
            f'<div style="font-size:1.2rem;font-weight:700;color:{TEXT};margin-bottom:4px;">⚡ Valutazione Finale</div>'
            f'<div style="font-size:0.82rem;color:{TEXT_SEC};margin-bottom:16px;">'
            f'Sintesi del rischio AML e raccomandazione operativa per il fascicolo cliente.</div>',
            unsafe_allow_html=True)

        # Mode selector
        current_final_mode = st.session_state.final_mode or "manual"
        mode_map    = {"✍️ A mano": "manual", "🤖 Super Agent": "agent"}
        mode_labels = list(mode_map.keys())
        mode_idx    = 1 if current_final_mode == "agent" else 0
        chosen_label = st.radio(
            "Modalità valutazione", mode_labels, index=mode_idx,
            horizontal=True, key="final_mode_radio", label_visibility="collapsed")
        st.session_state.final_mode = mode_map[chosen_label]

        st.markdown(f'<div style="height:10px;"></div>', unsafe_allow_html=True)

        client = get_client()
        key    = "final_valuation"

        if st.session_state.final_mode == "manual":
            existing = get_content(key) or ""
            st.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
                f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:6px;">Narrativa di Valutazione</div>',
                unsafe_allow_html=True)
            manual_narrative = st.text_area(
                "Narrativa", value=existing, height=280, key="final_manual_text",
                placeholder="Inserisci la valutazione finale della controparte…",
                label_visibility="collapsed")
            st.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
                f'color:{TEXT_SEC};text-transform:uppercase;margin:12px 0 6px;">Profilo di Rischio</div>',
                unsafe_allow_html=True)
            risk_opts = ["Confermato", "Innalzamento", "Abbassamento", "Modifica"]
            risk_choice = st.radio("Profilo", risk_opts, horizontal=True,
                                   key="final_risk_radio", label_visibility="collapsed")
            if st.button("💾 Salva Valutazione", key="final_manual_save", use_container_width=True):
                narrative_full = f"[{risk_choice}]\n\n{manual_narrative}"
                st.session_state.edited_content[key] = narrative_full
                st.session_state.kyc_state.add_result(key, narrative_full)
                st.success("✓ Valutazione salvata.")

        else:
            # Super Agent mode
            content = get_content(key)
            parsed  = parse_json_result(content) if content else None

            # Collect active findings
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
                        "sezione": sec["full_label"], "livello": lvl,
                        "evidenza": ev.get("evidenza",""), "normativa": ev.get("normativa",""),
                    })

            # Findings summary chips
            n_crit = sum(1 for f in all_findings if f["livello"] == "CRITICO")
            n_anom = sum(1 for f in all_findings if f["livello"] == "ANOMALIA")
            chips  = ""
            if n_crit:
                chips += (f'<span style="background:#FEF2F2;color:{DANGER};font-size:0.72rem;'
                          f'font-weight:700;padding:3px 12px;border-radius:20px;margin-right:6px;">'
                          f'🔴 {n_crit} critiche</span>')
            if n_anom:
                chips += (f'<span style="background:#FFFBEB;color:{YELLOW};font-size:0.72rem;'
                          f'font-weight:700;padding:3px 12px;border-radius:20px;">'
                          f'🟡 {n_anom} anomalie</span>')
            if chips:
                st.markdown(
                    f'<div style="margin-bottom:12px;">{chips}</div>',
                    unsafe_allow_html=True)

            run_col, _ = st.columns([1, 2])
            with run_col:
                if st.button("▶ Avvia Final Valuation Agent", key="run_super_agent",
                             use_container_width=True):
                    _run_with_stream(key, client)
                    return

            if parsed:
                risk     = parsed.get("rischioComplessivo","") or parsed.get("customerRiskRating","")
                rc       = get_risk_color(risk) if risk else BLUE
                narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                             or parsed.get("sintesiEsecutiva","") or "")
                flags    = parsed.get("flags", [])
                racc     = parsed.get("raccomandazione","")

                # Build raccomandazione string
                racc_str = ""
                if isinstance(racc, dict):
                    parts_r = [x for x in [racc.get("accettazione",""),
                                            racc.get("livelloAdeguataVerifica",""),
                                            racc.get("frequenzaMonitoraggio","")] if x]
                    if parts_r: racc_str = " · ".join(parts_r)
                elif isinstance(racc, str) and racc:
                    racc_str = racc

                # ── Risk badge + Confirm/Raise selector (same row) ────
                risk_col, profile_col = st.columns([1.5, 2.5])
                with risk_col:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;'
                        f'background:#fff;border:1px solid {BORDER};border-left:4px solid {rc};'
                        f'border-radius:0 8px 8px 0;padding:12px 14px;height:100%;">'
                        f'<span style="font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
                        f'color:{TEXT_SEC};text-transform:uppercase;">Rischio Complessivo</span>'
                        f'{risk_badge(risk)}'
                        + (f'<div style="width:100%;font-size:0.72rem;color:{TEXT_SEC};margin-top:2px;">'
                           f'{racc_str}</div>' if racc_str else '')
                        + f'</div>',
                        unsafe_allow_html=True)

                with profile_col:
                    st.markdown(
                        f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
                        f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:6px;">'
                        f'Decisione Compliance</div>',
                        unsafe_allow_html=True)
                    risk_profile_opts = ["✓ Confermato", "▲ Innalzamento", "▼ Abbassamento", "~ Modifica"]
                    risk_profile = st.radio("Profilo", risk_profile_opts, horizontal=True,
                                            key="final_agent_risk", label_visibility="collapsed")
                    save_col, _ = st.columns([1, 1])
                    with save_col:
                        if st.button("💾 Conferma decisione", key="final_agent_save",
                                     use_container_width=True):
                            annotated = f"[{risk_profile}]\n\n{content}"
                            st.session_state.edited_content[key] = annotated
                            st.session_state.kyc_state.add_result(key, annotated)
                            st.success("✓ Decisione salvata.")

                st.markdown(f'<div style="height:14px;"></div>', unsafe_allow_html=True)

                # ── Motivazioni (narrativa) ───────────────────────────
                if narrativa:
                    st.markdown(
                        f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                        f'color:{TEXT_SEC};text-transform:uppercase;margin-bottom:6px;">'
                        f'Motivazioni del Profilo di Rischio</div>'
                        f'<div style="background:#fff;border:1px solid {BORDER};'
                        f'border-left:4px solid {rc};border-radius:0 8px 8px 0;'
                        f'padding:18px 22px;font-size:0.875rem;line-height:1.85;'
                        f'color:{TEXT};margin-bottom:18px;">'
                        + narrativa.replace("\n","<br>") + '</div>',
                        unsafe_allow_html=True)

                # ── Flag AML ─────────────────────────────────────────
                if flags:
                    st.markdown(
                        f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                        f'color:{TEXT_SEC};margin:0 0 8px;text-transform:uppercase;">Flag AML</div>',
                        unsafe_allow_html=True)
                    _flag_cfg = {
                        "CRITICAL": ("#F3E8FF","#7C3AED","#7C3AED"),
                        "HIGH":     ("#FEE2E2","#B91C1C","#DC2626"),
                        "MEDIUM":   ("#FFFBEB","#92400E","#D97706"),
                        "LOW":      ("#F3F4F6","#6B7280","#9CA3AF"),
                    }
                    for fl in flags:
                        rischio = (fl.get("rischio","") or "").upper()
                        bg_f, fg_f, bd_f = _flag_cfg.get(rischio, ("#F3F4F6","#6B7280","#9CA3AF"))
                        tipo = fl.get("tipo","")
                        desc = fl.get("descrizione","")
                        norm = fl.get("riferimentoNormativo","") or fl.get("indicatoreUIF","")
                        st.markdown(
                            f'<div style="display:flex;align-items:flex-start;gap:10px;'
                            f'background:{bg_f};border:1px solid {BORDER};border-left:3px solid {bd_f};'
                            f'border-radius:0 6px 6px 0;padding:8px 12px;margin-bottom:5px;">'
                            f'<div style="flex:1;">'
                            f'<span style="font-size:0.8rem;font-weight:600;color:{fg_f};">{tipo}</span>'
                            + (f'<span style="font-size:0.78rem;color:{TEXT_SEC};"> — {desc}</span>' if desc else '')
                            + (f'<div style="font-size:0.68rem;color:{TEXT_SEC};margin-top:2px;">📎 {norm}</div>' if norm else '')
                            + f'</div></div>',
                            unsafe_allow_html=True)

        st.markdown(f'<div style="height:16px;"></div>', unsafe_allow_html=True)
        if st.button("← Torna all'analisi", key="back_to_analysis"):
            st.session_state.step = "analysis"
            st.rerun()


# ── ROUTER ───────────────────────────────────────────────────────
step = st.session_state.step

if step == "transit":
    # Blank frame: sends a near-empty delta to the browser, clearing all
    # stale DOM nodes from the previous page (mode_config widgets etc.).
    # Then immediately reruns to the real analysis page.
    st.markdown('<div style="display:none" id="aml-transit"></div>',
                unsafe_allow_html=True)
    st.session_state.step = "analysis"
    st.rerun()
elif step == "setup":
    render_setup()
elif step == "upload":
    render_upload()
elif step == "analysis":
    render_analysis()
elif step == "final":
    render_final_valuation()
else:
    render_setup()
