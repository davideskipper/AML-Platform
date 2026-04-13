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
    "additional_docs": "",
    "additional_doc_names": [],
    "final_chat_history": [],
    "final_ev_overrides": {},
    "counterparty_info": {},
    "upload_hash": "",
    "running_agent": None,
    "all_docs": "",
    "all_doc_names": [],
    "just_completed": None,
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

def get_parsed(key: str):
    """Cached parse of a section's JSON — re-parses only when content changes."""
    content = get_content(key)
    cache   = st.session_state.setdefault("_parsed_cache", {})
    entry   = cache.get(key)
    if entry and entry[0] == id(content):
        return entry[1]
    parsed = parse_json_result(content) if content else None
    cache[key] = (id(content), parsed)
    return parsed

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


def classify_evidence(ev: dict) -> dict:
    """Classify a single principaliEvidenze entry and return display style."""
    livello = (ev.get("livello", "") or "").upper().strip()
    testo   = (ev.get("evidenza", "") or "").lower()

    # CRITICO o ANOMALIA → Anomalia (rosso)
    if "CRITICO" in livello or "ANOMALIA" in livello:
        return {"bg_color": "#FDECEA", "text_color": "#B71C1C",
                "border_color": "#C62828", "label": "Anomalia"}

    # ATTENZIONE — distingui positivo da neutro/negativo tramite conteggio hit
    if "ATTENZIONE" in livello:
        pattern_positivi = [
            "trasparente",
            "identificabile con certezza",
            "interamente versato",
            "adeguato rispetto",
            "coerenza tra",
            "coerenza con",
            "assenza di procedure",
            "assenza di protesti",
            "assenza di ipoteche",
            "nessuna procedura",
            "nessun protesto",
            "nessuna transazione",
            "nessuna esposizione",
            "nessun collegamento",
            "regolarità commerciale",
            "solidità finanziaria",
            "profilo di rischio aml intrinsecamente basso",
            "flussi finanziari tipicamente tracciabili",
            "indicatore positivo",
            "elemento positivo",
            "certificazioni",
            "conforme",
            "coerente con",
            "senza interposizione",
            "senza discontinuità",
            "senza anomalie",
            "tracciabilità",
            "primario standing",
            "regolarmente",
            "regolari e ricorrenti",
            "puntualmente",
            "privo di criticità",
            "adempimenti fiscali",
            "giurisdizioni eu",
            "giurisdizioni standard",
            "tutti i paesi coinvolti",
            "paesi eu standard",
            "piano di ammortamento",
            "perizia immobiliare",
            "graduale",
            "documentati",
            "documentata",
        ]
        pattern_negativi = [
            "operazioni anomal",
            "flussi anomal",
            "movimentazioni anomal",
            "comportamento anomal",
            "picchi anomal",
            "variazioni anomal",
            "distribuzione anomal",
            "sospett",
            "incongruente",
            "incoerente",
            "sproporzionat",
            "opacità",
            "struttura opaca",
            "impossibilità",
            "non verificabile",
            "non documentat",
            "concentrazione anomala",
            "rischio di abuso",
            "riduce i controlli",
            "pur non costituendo anomalia",
            "tale assetto riduce",
            "oggetto sociale eccessivamente generico",
            "clausola residuale",
            "amplia formalmente il perimetro",
        ]
        hit_positivi = sum(1 for p in pattern_positivi if p in testo)
        hit_negativi = sum(1 for p in pattern_negativi if p in testo)

        if hit_positivi > hit_negativi:
            return {"bg_color": "#F1F8E9", "text_color": "#2E7D32",
                    "border_color": "#558B2F", "label": "Elemento positivo"}
        elif hit_negativi > 0:
            return {"bg_color": "#FFFDE7", "text_color": "#F57F17",
                    "border_color": "#F9A825", "label": "Punto di attenzione"}
        else:
            return {"bg_color": "#F5F5F5", "text_color": "#424242",
                    "border_color": "#BDBDBD", "label": "Info mancanti"}

    # Fallback
    return {"bg_color": "#F5F5F5", "text_color": "#616161",
            "border_color": "#9E9E9E", "label": "Info mancanti"}


# Keyword → suggested recovery action for "Info mancanti" evidences
_INFO_SUGGESTIONS = [
    (["ubo", "titolare effettivo", "beneficiar", "ownership"],
     "Richiedere dichiarazione UBO certificata e documenti identità dei titolari effettivi."),
    (["documento identit", "passaporto", "carta d'identit", "carta di identit"],
     "Acquisire copia del documento identità in corso di validità."),
    (["bilancio", "conto economico", "stato patrimoniale", "fatturato", "ricavi", "ebitda", "margine"],
     "Caricare bilancio degli ultimi 3 esercizi, conto economico e dichiarazioni fiscali."),
    (["estratto conto", "movimenti bancari", "transazion", "bonifici", "flussi finanziari", "movimentazion"],
     "Caricare estratti conto bancari degli ultimi 12 mesi in formato Excel/CSV."),
    (["organigramma", "struttura societaria", "soci", "quote", "partecipazion"],
     "Richiedere organigramma aggiornato e visura camerale storica."),
    (["origine dei fondi", "provenienza fondi", "patrimonio", "source of wealth", "origine patrimonio"],
     "Richiedere documentazione comprovante l'origine dei fondi e del patrimonio dichiarato."),
    (["sentenz", "procediment", "giudiziar", "penale", "casellario"],
     "Acquisire casellario giudiziario e documentazione aggiornata sui procedimenti citati."),
    (["statuto", "atto costitutivo", "oggetto sociale"],
     "Richiedere copia aggiornata dello statuto e dell'atto costitutivo."),
    (["pep", "politicamente espost", "carica politica", "carica pubblica", "incarico pubblico"],
     "Eseguire screening PEP su fonti ufficiali (es. Open Sanctions, World-Check) per le persone identificate."),
    (["dichiarazione dei redditi", "dichiarazione fiscale", "redditi", "irpef", "ires"],
     "Richiedere le ultime 3 dichiarazioni dei redditi e relativi accertamenti."),
    (["visura camerale", "registro imprese", "rea", "camera di commercio"],
     "Acquisire visura camerale aggiornata (storica) dal Registro Imprese."),
    (["notizie", "media", "stampa", "articoli", "adverse media", "web search"],
     "Eseguire ricerca adverse media avanzata (Factiva, World-Check, fonti giornalistiche)."),
    (["contratto", "accordo", "patto parasociale"],
     "Richiedere copia dei contratti o accordi rilevanti citati."),
    (["licenz", "autoriz", "certificazion", "iscrizione albo", "albo"],
     "Verificare iscrizioni ad albi, licenze e autorizzazioni su registri ufficiali."),
    (["sanzioni", "lista sanzioni", "screening sanzioni"],
     "Eseguire screening su liste sanzioni aggiornate (UE, OFAC, ONU, HMT)."),
]

def _info_suggestion(testo: str) -> str:
    """Return the best-matching recovery suggestion for a missing-info evidence, or ''."""
    testo_low = (testo or "").lower()
    for keywords, suggestion in _INFO_SUGGESTIONS:
        if any(kw in testo_low for kw in keywords):
            return suggestion
    return ""


def render_evidenze(evidenze: list) -> None:
    """Render a list of principaliEvidenze dicts with semantic colour coding."""
    if not evidenze:
        return
    for ev in evidenze:
        style     = classify_evidence(ev)
        desc      = ev.get("evidenza", "") or ""
        norm      = ev.get("normativa", "") or ""
        norm_html = (
            f'<p style="color:#9E9E9E;font-size:11px;font-style:italic;margin:0;">{norm}</p>'
            if norm else ""
        )
        suggestion_html = ""
        if style["label"] == "Info mancanti":
            hint = _info_suggestion(desc)
            if hint:
                suggestion_html = (
                    f'<div style="display:flex;align-items:flex-start;gap:5px;'
                    f'margin-top:6px;padding:6px 10px;background:#ECECEC;border-radius:4px;">'
                    f'<span style="font-size:11px;color:#616161;font-weight:700;'
                    f'white-space:nowrap;">Azione suggerita:</span>'
                    f'<span style="font-size:11px;color:#424242;line-height:1.5;">{hint}</span>'
                    f'</div>'
                )
        st.markdown(
            f'<div style="background-color:{style["bg_color"]};'
            f'border-left:4px solid {style["border_color"]};'
            f'border-radius:4px;padding:12px 16px;margin-bottom:10px;">'
            f'<span style="background-color:{style["border_color"]};color:white;'
            f'font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;'
            f'text-transform:uppercase;letter-spacing:0.5px;">{style["label"]}</span>'
            f'<p style="color:{style["text_color"]};font-size:13px;'
            f'margin:8px 0 4px 0;line-height:1.5;">{desc}</p>'
            + norm_html + suggestion_html +
            f'</div>',
            unsafe_allow_html=True)


def run_section(key, client, on_token=None, on_thinking=None):
    state   = st.session_state.kyc_state
    company = state.case.company_name
    country = state.case.country
    docs_text  = (st.session_state.section_docs.get(key, "")
                  or st.session_state.get("all_docs", ""))
    notes_text = st.session_state.section_notes.get(key, "")
    kb_text    = st.session_state.knowledge_base
    add_text   = st.session_state.get("additional_docs", "")
    use_web    = st.session_state.section_web.get(key, False) or not bool(docs_text)
    parts = []
    if kb_text:
        parts.append(f"BASE DOCUMENTALE DI RIFERIMENTO (NORMATIVA):\n\n{kb_text}")
    if docs_text:
        parts.append(f"DOCUMENTI DEL CLIENTE:\n\n{docs_text}")
    if add_text:
        parts.append(f"DOCUMENTI AGGIUNTIVI (Nota Parere, pareri legali):\n\n{add_text}")
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
    "upload":   "① Carica Documenti",
    "analysis": "② Analisi Controparte",
    "final":    "③ Valutazione Finale",
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
            f'<span style="{label_style}font-size:0.8rem;">{label}</span>'
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


# ── Agents info dialog ────────────────────────────────────────────
if hasattr(st, "dialog"):
    @st.dialog("Visualizza Agenti", width="large")
    def _agents_info_dialog():
        _AGENTS_INFO = [
            {
                "number": "01",
                "label": "Registry & Struttura Societaria",
                "icon": "🏛",
                "desc": "Analizza la struttura legale e la governance dell'azienda.",
                "documenti": [
                    "Visura camerale ordinaria o storica",
                    "Statuto e atti costitutivi",
                    "Organigramma societario",
                    "Patti parasociali (se disponibili)",
                ],
                "analizza": [
                    "Forma giuridica e oggetto sociale — verifica ampiezza e coerenza con l'attività dichiarata",
                    "Composizione del CDA e poteri di firma — rileva governance accentrata o ruoli anomali",
                    "Assetti proprietari — mappa la catena di controllo e le variazioni recenti",
                    "Durata societaria e modifiche statutarie — identifica società di nuova costituzione o riassetti frequenti",
                    "Sede legale e operativa — verifica coerenza geografica e presenza di indirizzi fittizi",
                ],
                "regole": "D.Lgs. 231/2007 artt. 18-20 (adeguata verifica); FATF Recommendation 10; EBA Guidelines on customer due diligence.",
            },
            {
                "number": "02",
                "label": "UBO & PEP",
                "icon": "👤",
                "desc": "Identifica i titolari effettivi e verifica l'esposizione politica.",
                "documenti": [
                    "Dichiarazione UBO (autocertificazione titolare effettivo)",
                    "Documenti d'identità degli UBO",
                    "Visura camerale (per la catena proprietaria)",
                    "Eventuali atti notarili di trust o fiduciarie",
                ],
                "analizza": [
                    "Catena di controllo — risale fino al titolare effettivo persona fisica (soglia 25% D.Lgs. 231/2007 art.20)",
                    "PEP screening — verifica se gli UBO o soggetti collegati sono persone politicamente esposte (domestici e internazionali)",
                    "Sanzioni internazionali — screening su liste OFAC, EU Consolidated List, ONU, Consob",
                    "Origine dei fondi e del patrimonio — obbligatoria per PEP e soggetti ad alto rischio",
                    "Coerenza tra UBO dichiarato e struttura societaria emersa dai documenti",
                ],
                "regole": "D.Lgs. 231/2007 artt. 20-22 (titolare effettivo); IV e V Direttiva AML UE; FATF Recommendation 12 (PEP); Reg. UE 2015/847.",
            },
            {
                "number": "03",
                "label": "Reputational",
                "icon": "🔍",
                "desc": "Analizza la reputazione online tramite ricerca web strutturata.",
                "documenti": [
                    "Ricerca web (notizie, comunicati stampa, provvedimenti)",
                    "Nota Parere o altri documenti a supporto (se caricati)",
                    "Fonti giudiziarie e registri pubblici accessibili online",
                ],
                "analizza": [
                    "Notizie negative — procedimenti penali, civili, fallimentari o amministrativi",
                    "Presence in liste nere — sanzioni, esclusioni da gare, provvedimenti Banca d'Italia/Consob",
                    "Associazioni con soggetti a rischio AML — co-imputati, soci in procedimenti, network di aziende sanzionate",
                    "Scandali reputazionali — frodi, evasione fiscale, corruzione, riciclaggio",
                    "Congruenza narrativa — verifica che la storia pubblica dell'azienda sia coerente con quanto dichiarato",
                ],
                "regole": "D.Lgs. 231/2007 art. 17 (approccio basato sul rischio); FATF Recommendation 10; Circolare Banca d'Italia n. 285 (Titolo IV).",
            },
            {
                "number": "04",
                "label": "Profilo Economico",
                "icon": "📊",
                "desc": "Analizza la solidità e la coerenza del profilo finanziario.",
                "documenti": [
                    "Bilancio di esercizio (ultimi 3 anni)",
                    "Conto economico",
                    "Dichiarazioni fiscali (Redditi / IVA)",
                ],
                "analizza": [
                    "Coerenza fatturato/settore — confronto con benchmark ATECO e dimensione aziendale",
                    "Struttura patrimoniale — rapporto equity/debito, composizione immobilizzazioni, leva finanziaria",
                    "Marginalità — EBITDA/ricavi vs benchmark di settore; anomalie nei margini",
                    "Flussi di cassa — analisi operativo vs finanziario vs investimento; cash generation anomala",
                    "Attività e passività anomale — voci difficilmente giustificabili, crediti verso soci non documentati",
                    "Concentrazione ricavi — dipendenza da pochi clienti o da un'unica area geografica",
                ],
                "regole": "D.Lgs. 231/2007 art. 18 (profilo economico); FATF Recommendation 10; Indicatori di anomalia UIF (Provvedimento 24/08/2010).",
            },
            {
                "number": "05",
                "label": "Transaction & Geographic Risk",
                "icon": "💳",
                "desc": "Analizza i movimenti bancari e il rischio geografico delle controparti.",
                "documenti": [
                    "File Excel/CSV movimenti bancari (estratto conto strutturato)",
                ],
                "analizza": [
                    "Pattern AML — strutturazione (smurfing), layering, integrazione; pass-through sistematico",
                    "Operazioni verso paesi ad alto rischio — FATF Black List (azione immediata) e Grey List (EDD obbligatoria)",
                    "Concentrazione controparti — dipendenza da pochi soggetti; controparti in paradisi fiscali",
                    "Anomalie negli importi — transazioni appena sotto le soglie di segnalazione (€15.000 / €10.000)",
                    "Frequenza e stagionalità — picchi anomali, operazioni notturne o fuori orario",
                    "Rischio geografico — classificazione FATF Black / Grey / EU High Risk / Sanzioni per ogni paese di flusso",
                ],
                "regole": "D.Lgs. 231/2007 art. 35 (SOS); FATF Recommendations 10 e 16; Indicatori anomalia UIF n. 42/2023; Reg. UE 2015/847 (tracciabilità bonifici).",
            },
            {
                "number": "06",
                "label": "Final Valuation",
                "icon": "⚡",
                "desc": "Sintetizza gli output di tutti gli agenti e produce il Customer Risk Rating finale.",
                "documenti": [
                    "Output strutturati (JSON) degli agenti 01–05",
                    "Nota Parere e documenti aggiuntivi (se caricati)",
                ],
                "analizza": [
                    "Matrice di rischio 5 dimensioni — punteggio 1-5 per identità/struttura, reputazionale, economico, transazionale, geografico",
                    "Consolidamento evidenze — aggrega i principali FLAG AML da tutti gli agenti, elimina duplicati, ordina per criticità",
                    "Customer Risk Rating — BASSO / MEDIO / MEDIO-ALTO / ALTO / CRITICO (con logica di escalation automatica)",
                    "Raccomandazione operativa — accettazione (SI/NO/CONDIZIONATA), livello EDD, frequenza monitoraggio, autorizzazione senior management, valutazione SOS",
                    "Narrativa per il fascicolo — testo formale da 14-18 righe adatto a ispezioni Banca d'Italia",
                ],
                "regole": "D.Lgs. 231/2007; FATF Recommendations; Circolare Banca d'Italia n. 285; EBA Risk Factor Guidelines (JC/2017/37). Extended Thinking attivo: il modello ragiona internamente prima di produrre il rating.",
            },
        ]

        for ag in _AGENTS_INFO:
            with st.expander(f"{ag['icon']} Agente {ag['number']} — {ag['label']}", expanded=False):
                st.markdown(
                    f'<div style="font-size:0.82rem;color:#64748B;margin-bottom:10px;">{ag["desc"]}</div>',
                    unsafe_allow_html=True)

                col_d, col_a = st.columns([1, 1])
                with col_d:
                    st.markdown("**Documenti utilizzati**")
                    for doc in ag["documenti"]:
                        st.markdown(f"- {doc}")
                with col_a:
                    st.markdown("**Cosa analizza**")
                    for item in ag["analizza"]:
                        st.markdown(f"- {item}")

                st.markdown(
                    f'<div style="font-size:0.75rem;color:#64748B;margin-top:6px;'
                    f'padding:6px 10px;background:#F8FAFC;border-radius:4px;">'
                    f'<b>Normativa di riferimento:</b> {ag["regole"]}</div>',
                    unsafe_allow_html=True)


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
            rc   = GREEN if done == total else "#1A1A2E"
            prog_bar = (
                f'<div style="display:inline-flex;align-items:center;gap:6px;'
                f'background:{"#DCFCE7" if done==total else "#EBEBEB"};'
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
        _hb_a, _hb_b = st.columns(2)
        with _hb_a:
            if st.session_state.step in ("analysis", "final"):
                if st.button("Visualizza Agenti", key="btn_agents_info", use_container_width=True):
                    if hasattr(st, "dialog"):
                        _agents_info_dialog()
        with _hb_b:
            if st.session_state.step not in ("setup", ""):
                if st.button("← Home", key="btn_go_home", use_container_width=True):
                    st.session_state.step = "setup"
                    st.rerun()
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

    # ── Evidenze ─────────────────────────────────────────────────
    if evidenze:
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{TEXT_SEC};margin:6px 0 10px;text-transform:uppercase;">Principali Evidenze</div>',
            unsafe_allow_html=True)
        render_evidenze(evidenze)

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

        if st.button("Carica Documenti", use_container_width=True):
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
    """Return section key if filename starts with 0?N[space/_/-/.] for N=1..5, else ''.
    Excel/CSV files are always auto-assigned to 'transaction' since it is the only
    section that consumes structured tabular data."""
    lower = filename.lower()
    # Numeric prefix takes priority
    for i, sec in enumerate(MAIN_SECTIONS, 1):
        if re.match(r'^0?' + str(i) + r'[\s_\-\.]', lower):
            return sec["key"]
    # Excel/CSV → transaction (only section that needs a spreadsheet)
    ext = os.path.splitext(lower)[1]
    if ext in (".xlsx", ".xls", ".csv"):
        return "transaction"
    return ""

def render_upload():
    render_header()
    _, col, _ = st.columns([0.5, 5, 0.5])
    with col:
        st.markdown(
            f'<div style="font-size:1.15rem;font-weight:700;color:{TEXT};margin-bottom:8px;">Carica Documenti</div>',
            unsafe_allow_html=True)

        files_data_check = st.session_state.uploaded_files_data
        if not files_data_check:
            st.markdown(
                f'<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;'
                f'padding:10px 14px;margin-bottom:10px;font-size:0.8rem;color:{BLUE};">'
                f'ℹ️ Nessun documento caricato — gli agenti utilizzeranno la ricerca web.</div>',
                unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                f'color:{BLUE};text-transform:uppercase;margin-bottom:4px;">Documenti Controparte</div>'
                f'<div style="font-size:0.78rem;color:{TEXT_SEC};margin-bottom:10px;">'
                f'Visura camerale, statuto, dichiarazione UBO, documenti identità, bilancio, '
                f'estratti conto, movimenti bancari (Excel/CSV), sentenze, atti giudiziari. '
                f'Ogni file viene assegnato automaticamente alla sezione corrispondente.</div>',
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

        # ── Documenti aggiuntivi (Nota Parere, pareri legali, ecc.) ──
        with st.container(border=True):
            st.markdown(
                f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                f'color:{BLUE};text-transform:uppercase;margin-bottom:4px;">Documenti Aggiuntivi</div>'
                f'<div style="font-size:0.78rem;color:{TEXT_SEC};margin-bottom:10px;">'
                f'Nota Parere, altri documenti a supporto della valutazione</div>',
                unsafe_allow_html=True)
            add_files = st.file_uploader(
                "Documenti aggiuntivi", type=["pdf", "docx", "txt", "md"],
                accept_multiple_files=True, key="additional_docs_upload",
                label_visibility="collapsed")
            if add_files:
                _add_texts, _add_names = [], []
                for _f in add_files:
                    _f.seek(0)
                    _add_texts.append(f"=== {_f.name} ===\n{extract_text_from_file(_f)}")
                    _add_names.append(_f.name)
                st.session_state.additional_docs      = "\n\n".join(_add_texts)
                st.session_state.additional_doc_names = _add_names
                st.success(f"✓ {len(_add_texts)} documento/i aggiuntivi caricati")
            elif st.session_state.get("additional_doc_names"):
                st.markdown(
                    f'<div style="font-size:0.78rem;color:{BLUE};padding:6px 0;">'
                    + " · ".join(f"📄 {n}" for n in st.session_state.additional_doc_names)
                    + "</div>", unsafe_allow_html=True)

        st.markdown(f'<div style="height:12px;"></div>', unsafe_allow_html=True)
        nav_l, nav_r = st.columns([1, 1])
        with nav_l:
            if st.button("Indietro", key="upload_back", use_container_width=True):
                st.session_state.step = "setup"
                st.rerun()
        with nav_r:
            if st.button("Avvia Analisi", key="upload_next", use_container_width=True):
                _fd_list  = st.session_state.uploaded_files_data
                _fa       = st.session_state.file_assignments
                _sec_docs, _sec_names = {}, {}
                for _sec in MAIN_SECTIONS:
                    _sk = _sec["key"]
                    _asgn = [fd for fd in _fd_list if _fa.get(fd["name"]) == _sk]
                    if not _asgn:
                        continue
                    if _sk == "transaction":
                        _fd = _asgn[0]; _raw = _fd.get("raw_bytes")
                        import io as _io
                        _buf = _io.BytesIO(_raw) if _raw else _io.BytesIO(
                            _fd["content_text"].encode("utf-8", errors="replace"))
                        _buf.name = _fd["name"]
                        st.session_state.excel_raw_bytes = _buf
                        st.session_state.excel_name      = _fd["name"]
                        _sec_names[_sk] = [_fd["name"]]
                    else:
                        _sec_docs[_sk]  = "\n\n".join(
                            f"=== {fd['name']} ===\n{fd['content_text']}" for fd in _asgn)
                        _sec_names[_sk] = [fd["name"] for fd in _asgn]
                st.session_state.section_docs      = _sec_docs
                st.session_state.section_doc_names = _sec_names
                # All sections start with no mode set — user chooses per tab
                st.session_state.run_queue         = []
                st.session_state.active_section    = "registry"
                # Extract counterparty info from registry docs
                _reg_text = _sec_docs.get("registry", "")
                if _reg_text:
                    with st.spinner("Lettura dati controparte…"):
                        st.session_state.counterparty_info = _extract_counterparty_info(
                            get_client(), _reg_text)
                else:
                    st.session_state.counterparty_info = {}
                st.session_state.uploaded_files_data = []
                st.session_state.file_assignments    = {}
                st.session_state.upload_hash         = ""
                st.session_state.step = "analysis"
                st.rerun()


# ── STEP 3: MODE CONFIG ───────────────────────────────────────────
# CRITICAL: must use st.columns([3.5, 1.5, 1]) — identical to render_analysis().
# Streamlit reconciles the DOM by element-tree path. If mode_config and analysis
# use different column structures, Streamlit cannot properly clear the old columns,
# leaving ghost widgets. Same structure = same paths = clean transition.
def render_mode_config():
    render_header()

    # ── SAME column split as render_analysis() ────────────────────
    main_col, _, ctrl_col = st.columns([3.5, 1.5, 1])

    files_data   = st.session_state.uploaded_files_data
    file_assigns = st.session_state.file_assignments

    with main_col:
        st.markdown(
            f'<div style="font-size:1.05rem;font-weight:700;color:{TEXT};margin-bottom:4px;">'
            f'Configura Modalità Analisi</div>'
            f'<div style="font-size:0.8rem;color:{TEXT_SEC};margin-bottom:14px;">'
            f'Scegli per ogni sezione se usare l\'agente AI o inserire manualmente.</div>',
            unsafe_allow_html=True)

        for sec in MAIN_SECTIONS:
            key = sec["key"]
            assigned_files = [fd["name"] for fd in files_data
                              if file_assigns.get(fd["name"]) == key]
            file_tags = "".join(
                f'<span style="display:inline-block;background:#F0FFF4;border:1px solid #BBF7D0;'
                f'border-radius:10px;padding:1px 8px;font-size:0.68rem;color:#166534;margin:1px 2px;">'
                f'📄 {n[:30]}</span>'
                for n in assigned_files)

            with st.container(border=True):
                st.markdown(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'flex-wrap:wrap;gap:6px;margin-bottom:8px;">'
                    f'<div style="display:flex;align-items:center;gap:6px;">'
                    f'<span style="font-size:1rem;">{sec["icon"]}</span>'
                    f'<span style="font-size:0.62rem;color:{TEXT_SEC};font-weight:700;">{sec["number"]}</span>'
                    f'<span style="font-size:0.9rem;font-weight:600;color:{TEXT};">{sec["full_label"]}</span>'
                    f'</div>'
                    + (f'<div>{file_tags}</div>' if file_tags else
                       f'<span style="font-size:0.7rem;color:{TEXT_SEC};">Nessun documento</span>')
                    + f'</div>',
                    unsafe_allow_html=True)

                current_mode = st.session_state.section_modes.get(key, "agent")
                chosen = st.radio(
                    "Modalità", options=["🤖 Agente", "✍️ Manuale"],
                    index=0 if current_mode == "agent" else 1,
                    key=f"mc_mode_{key}", horizontal=True, label_visibility="collapsed")
                st.session_state.section_modes[key] = "agent" if chosen == "🤖 Agente" else "manual"

                if st.session_state.section_modes.get(key) == "agent":
                    web_val = st.session_state.section_web.get(key, False)
                    st.session_state.section_web[key] = st.checkbox(
                        "🌐 Web search", value=web_val, key=f"mc_web_{key}")

    with ctrl_col:
        st.markdown(f'<div style="height:48px;"></div>', unsafe_allow_html=True)
        if st.button("Indietro", key="mc_back", use_container_width=True):
            st.session_state.step = "upload"
            st.rerun()
        st.markdown(f'<div style="height:6px;"></div>', unsafe_allow_html=True)
        if st.button("Avvia Analisi", key="mc_next", use_container_width=True):
            files_data   = st.session_state.uploaded_files_data
            file_assigns = st.session_state.file_assignments
            section_docs, section_doc_names = {}, {}
            for sec in MAIN_SECTIONS:
                skey     = sec["key"]
                assigned = [fd for fd in files_data if file_assigns.get(fd["name"]) == skey]
                if not assigned:
                    continue
                if skey == "transaction":
                    fd  = assigned[0]
                    raw = fd.get("raw_bytes")
                    import io as _io
                    buf = _io.BytesIO(raw) if raw else _io.BytesIO(
                        fd["content_text"].encode("utf-8", errors="replace"))
                    buf.name = fd["name"]
                    st.session_state.excel_raw_bytes = buf
                    st.session_state.excel_name      = fd["name"]
                    section_doc_names[skey] = [fd["name"]]
                else:
                    section_docs[skey]      = "\n\n".join(
                        f"=== {fd['name']} ===\n{fd['content_text']}" for fd in assigned)
                    section_doc_names[skey] = [fd["name"] for fd in assigned]
            st.session_state.section_docs      = section_docs
            st.session_state.section_doc_names = section_doc_names
            st.session_state.run_queue         = [
                s["key"] for s in MAIN_SECTIONS
                if st.session_state.section_modes.get(s["key"]) == "agent"]
            st.session_state.active_section    = "registry"
            # Clear mc_* widget keys so they don't persist into analysis
            for s in MAIN_SECTIONS:
                st.session_state.pop(f"mc_mode_{s['key']}", None)
                st.session_state.pop(f"mc_web_{s['key']}", None)
            for k in list(st.session_state.keys()):
                if k.startswith("assign_"):
                    del st.session_state[k]
            # Extract counterparty info from registry docs
            _reg_text = section_docs.get("registry", "")
            if _reg_text:
                with st.spinner("Lettura dati controparte…"):
                    st.session_state.counterparty_info = _extract_counterparty_info(
                        get_client(), _reg_text)
            else:
                st.session_state.counterparty_info = {}
            st.session_state.uploaded_files_data = []
            st.session_state.file_assignments    = {}
            st.session_state.upload_hash         = ""
            # Go directly to analysis — no transit needed because column
            # structure is identical, so Streamlit reconciles cleanly.
            st.session_state.step = "analysis"
            st.rerun()


# ── STREAMING helper ──────────────────────────────────────────────
def _run_with_stream(key: str, client):
    """Run agent with live streaming. Must be called inside the desired column context."""
    if not client:
        st.error("API Key non configurata nei Secrets.")
        return

    status_box = st.empty()
    stream_box = st.empty()

    import time as _time
    buf = {"text": "", "thinking": "", "phase": "thinking", "_last_render": 0.0}

    def _render():
        now = _time.monotonic()
        if now - buf["_last_render"] < 0.10:
            return
        buf["_last_render"] = now
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
                f'padding:20px 24px;width:100%;max-height:320px;overflow-y:auto;">'
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
        st.session_state.just_completed = key
        st.rerun()
    except Exception as e:
        status_box.empty()
        stream_box.empty()
        st.error(f"❌ Errore agente **{key}**: {e}")
        st.session_state.pop("running_agent", None)



# ── Criticality panel ─────────────────────────────────────────────
def _render_crit_panel(key: str):
    parsed  = get_parsed(key)
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
            if st.button("Aggiorna stato", key=f"crit_btn_{key}_{idx}"):
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
                    if st.form_submit_button("Salva"):
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
    parsed  = get_parsed(key)
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
        btn_back, btn_s, btn_r = st.columns([1, 1, 1])
        with btn_back:
            if st.button("Indietro", key=f"manual_back_{key}", use_container_width=True):
                st.session_state.section_modes[key] = None
                st.rerun()
        with btn_s:
            if st.button("Salva", key=f"manual_save_{key}", use_container_width=True):
                st.session_state.edited_content[key] = new_val
                st.session_state.kyc_state.add_result(key, new_val)
                st.rerun()
        with btn_r:
            if st.button("Avvia agente", key=f"manual_rerun_{key}", use_container_width=True):
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
                    f'border-radius:8px;'
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
                        f'border-radius:8px;'
                        f'padding:16px 20px;margin-bottom:16px;">'
                        + "".join(_proposta_parts) + '</div>',
                        unsafe_allow_html=True)

            # Principali Evidenze AML — unico schema per tutte le sezioni
            evidenze = parsed.get("principaliEvidenze") or []
            if evidenze:
                _rank_map = {"Anomalia": 0, "Punto di attenzione": 1, "Info mancanti": 2, "Elemento positivo": 3}
                evidenze = sorted(evidenze, key=lambda e: _rank_map.get(classify_evidence(e)["label"], 2))
                st.markdown(
                    f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                    f'color:{TEXT_SEC};margin:6px 0 8px;text-transform:uppercase;">Principali Evidenze AML</div>',
                    unsafe_allow_html=True)
                render_evidenze(evidenze)

            # Action row: re-run + edit JSON
            st.markdown(f'<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
            btn_rr, btn_ed, _ = st.columns([1, 1, 2])
            with btn_rr:
                if st.button("Riesegui Agente", key=f"rerun_{key}", use_container_width=True):
                    st.session_state.section_modes[key] = "agent"
                    st.session_state.run_queue = [key]
                    st.rerun()
            with btn_ed:
                etk = f"show_edit_{key}"
                if st.button("Modifica JSON", key=f"edit_toggle_{key}", use_container_width=True):
                    st.session_state[etk] = not st.session_state.get(etk, False)
                    st.rerun()
            if st.session_state.get(f"show_edit_{key}", False):
                edited = st.text_area("", value=content, height=300,
                                      key=f"edit_ta_{key}", label_visibility="collapsed")
                if st.button("Salva", key=f"edit_save_{key}"):
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

    # ── Agent mode: empty — user picks agent or manual ───────────────
    elif status == "empty":
        st.markdown(
            f'<div style="text-align:center;padding:36px 0 20px;background:#fff;'
            f'border:1px solid {BORDER};border-radius:10px;margin-bottom:16px;">'
            f'<div style="font-size:3rem;opacity:0.10;">{sec["icon"]}</div>'
            f'<div style="font-size:0.85rem;color:{TEXT_SEC};margin-top:10px;font-weight:500;">'
            f'Sezione non ancora analizzata</div>'
            f'<div style="font-size:0.75rem;color:{TEXT_SEC};opacity:0.7;margin-top:4px;">'
            f'{sec["desc"]}</div>'
            f'</div>', unsafe_allow_html=True)
        btn_a, btn_m = st.columns(2)
        with btn_a:
            if st.button("Avvia agente", key=f"run_{key}", use_container_width=True):
                st.session_state.section_modes[key] = "agent"
                st.session_state.run_queue = [key]
                st.rerun()
        with btn_m:
            if st.button("Inserisci valutazione manuale", key=f"manual_start_{key}", use_container_width=True):
                st.session_state.section_modes[key] = "manual"
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

        parsed  = get_parsed(k) if status == "completed" else None
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
    if st.button("Valutazione finale", key="go_final_panel", use_container_width=True):
        st.session_state.step = "final"
        st.rerun()


# ── Run-all agents popup ──────────────────────────────────────────
if hasattr(st, "dialog"):
    @st.dialog("Avvia Agenti", width="large")
    def _run_all_dialog():
        # Persist order and selection across fragment reruns
        if "rall_order" not in st.session_state:
            st.session_state.rall_order = [s["key"] for s in MAIN_SECTIONS]
        if "rall_sel" not in st.session_state:
            st.session_state.rall_sel = {s["key"]: True for s in MAIN_SECTIONS}

        order = list(st.session_state.rall_order)
        sel   = st.session_state.rall_sel

        st.markdown(
            f'<div style="font-size:0.82rem;color:{TEXT_SEC};margin-bottom:14px;">'
            f'Seleziona gli agenti e usa ↑ ↓ per definire l\'ordine di esecuzione.</div>',
            unsafe_allow_html=True)

        for i, k in enumerate(order):
            sec = next(s for s in MAIN_SECTIONS if s["key"] == k)
            col_chk, col_lbl, col_up, col_dn = st.columns([0.4, 5.2, 0.45, 0.45])

            with col_chk:
                st.markdown('<div style="height:7px;"></div>', unsafe_allow_html=True)
                new_val = st.checkbox(
                    "", value=sel.get(k, True), key=f"rall_chk_{k}",
                    label_visibility="collapsed")
                sel[k] = new_val

            with col_lbl:
                done_html = (
                    f'<span style="font-size:0.7rem;color:{GREEN};margin-left:6px;">✓</span>'
                    if sec_status(k) == "completed" else "")
                dim = "opacity:0.4;" if not sel.get(k, True) else ""
                pos_badge = (
                    f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                    f'min-width:20px;height:20px;background:#E5E7EB;border-radius:50%;'
                    f'font-size:0.68rem;font-weight:700;color:#6B7280;">{i + 1}</span>')
                st.markdown(
                    f'<div style="{dim}display:flex;align-items:center;gap:8px;'
                    f'padding:9px 14px;background:#F8F9FA;border-radius:7px;'
                    f'border:1px solid #E5E7EB;margin-bottom:2px;">'
                    f'<span style="color:#CBD5E1;font-size:1rem;user-select:none;">⠿</span>'
                    + pos_badge +
                    f'<span style="font-size:1rem;">{sec["icon"]}</span>'
                    f'<span style="font-size:0.87rem;font-weight:500;color:{TEXT};">'
                    f'{sec["full_label"]}</span>'
                    + done_html + '</div>',
                    unsafe_allow_html=True)

            with col_up:
                st.markdown('<div style="height:3px;"></div>', unsafe_allow_html=True)
                if st.button("↑", key=f"rall_up_{k}", disabled=(i == 0),
                             use_container_width=True):
                    order[i], order[i - 1] = order[i - 1], order[i]
                    st.session_state.rall_order = order

            with col_dn:
                st.markdown('<div style="height:3px;"></div>', unsafe_allow_html=True)
                if st.button("↓", key=f"rall_dn_{k}", disabled=(i == len(order) - 1),
                             use_container_width=True):
                    order[i], order[i + 1] = order[i + 1], order[i]
                    st.session_state.rall_order = order

        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
        col_ann, col_go = st.columns([1, 2])
        with col_ann:
            if st.button("Annulla", key="rall_cancel", use_container_width=True):
                st.session_state.pop("rall_order", None)
                st.session_state.pop("rall_sel", None)
                st.rerun()
        with col_go:
            if st.button("Avvia selezionati", key="rall_go", use_container_width=True):
                queue = [k for k in order if sel.get(k, True)]
                if queue:
                    st.session_state.run_queue      = queue
                    st.session_state.active_section = queue[0]
                st.session_state.pop("rall_order", None)
                st.session_state.pop("rall_sel", None)
                st.rerun()
else:
    def _run_all_dialog():
        pass  # Streamlit < 1.33 — fallback: no popup


# ── Counterparty extraction & card ───────────────────────────────
def _extract_counterparty_info(client, docs_text: str) -> dict:
    """Extract key company fields from registry documents using Claude Haiku."""
    if not client or not docs_text:
        return {}
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=(
                "Sei un estrattore di dati societari italiani. "
                "Estrai le informazioni richieste dal documento e restituisci SOLO un oggetto JSON valido. "
                "Usa null per i campi non disponibili. Nessun testo prima o dopo il JSON."
            ),
            messages=[{
                "role": "user",
                "content": (
                    "Estrai dal seguente documento le informazioni societarie:\n\n"
                    + docs_text[:10000]
                    + "\n\nRestituisci ESCLUSIVAMENTE questo JSON:\n"
                    '{"ragioneSociale":null,"formaGiuridica":null,"sedeLegale":null,'
                    '"codiceFiscale":null,"partitaIva":null,"ateco":null,'
                    '"descrizioneAttivita":null,"capitaleSociale":null,"dataCostituzione":null}'
                ),
            }],
        )
        text = resp.content[0].text.strip()
        s = text.find("{"); e = text.rfind("}") + 1
        if s >= 0 and e > s:
            return {k: v for k, v in json.loads(text[s:e]).items() if v}
    except Exception:
        pass
    return {}


def _render_counterparty_card():
    """Render compact counterparty info card at the top of analysis page."""
    info = st.session_state.get("counterparty_info", {})
    state = st.session_state.kyc_state

    # Always show at minimum company name + country
    nome     = (info.get("ragioneSociale") or
                (state.case.company_name if state and state.case.company_name not in ("", "Controparte N/D") else None))
    country  = state.case.country if state else ""

    if not nome and not info:
        return

    def _field(label, value):
        if not value:
            return ""
        return (
            f'<div style="min-width:140px;flex:1;">'
            f'<div style="font-size:0.6rem;font-weight:700;letter-spacing:0.8px;'
            f'color:#94A3B8;text-transform:uppercase;margin-bottom:2px;">{label}</div>'
            f'<div style="font-size:0.78rem;font-weight:500;color:#1E293B;">{value}</div>'
            f'</div>'
        )

    fields_html = "".join([
        _field("Forma giuridica",  info.get("formaGiuridica")),
        _field("Sede legale",      info.get("sedeLegale")),
        _field("ATECO",            (f'{info["ateco"]} — {info["descrizioneAttivita"]}'
                                    if info.get("ateco") and info.get("descrizioneAttivita")
                                    else info.get("ateco") or info.get("descrizioneAttivita"))),
        _field("CF / P.IVA",       " / ".join(filter(None, [info.get("codiceFiscale"), info.get("partitaIva")])) or None),
        _field("Capitale sociale", info.get("capitaleSociale")),
        _field("Costituzione",     info.get("dataCostituzione")),
        _field("Paese",            country or None),
    ])

    st.markdown(
        f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;'
        f'padding:14px 20px;margin-bottom:16px;">'
        f'<div style="font-size:1.05rem;font-weight:700;color:#1E293B;margin-bottom:10px;">'
        f'{nome}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:16px 24px;">'
        + fields_html +
        f'</div></div>',
        unsafe_allow_html=True)


# ── STEP 4: ANALYSIS ─────────────────────────────────────────────
def render_analysis():
    render_header()
    _render_counterparty_card()
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

    # Build status pills: 3 states only — grey (pending), spinning (running), black ✓ (done)
    pills = ""
    for s in MAIN_SECTIONS:
        k    = s["key"]
        st_s = sec_status(k)
        is_run = (k == queued_key)

        if is_run:
            pb, pf, brd = "#fff", "#1E2328", "border:1px solid #1E2328;"
            icon_html   = '<span class="aml-spin" style="font-size:0.65rem;color:#1E2328;">⚙</span> '
        elif st_s == "completed":
            pb, pf, brd = "#EBEBEB", "#1E2328", "border:1px solid #C8C8C8;"
            icon_html   = '<span style="color:#1E2328;font-weight:800;">✓</span> '
        else:
            pb, pf, brd = BG, TEXT_SEC, f"border:1px solid {BORDER};"
            icon_html   = '<span style="opacity:0.45;">○</span> '

        pills += (
            f'<span style="background:{pb};color:{pf};font-size:0.72rem;'
            f'font-weight:600;padding:4px 11px;border-radius:20px;'
            f'{brd}white-space:nowrap;">'
            + icon_html + s["label"] + '</span>')

    # ── Count AML flags — use classify_evidence() for perfect consistency
    # with the FLAG AML cards rendered in each section and in final valuation.
    _fl_counts = {"Anomalia": 0, "Punto di attenzione": 0,
                  "Info mancanti": 0, "Elemento positivo": 0}
    for _s in MAIN_SECTIONS:
        _p = get_parsed(_s["key"])
        if not _p:
            continue
        for _ev in _p.get("principaliEvidenze", []):
            _lbl = classify_evidence(_ev)["label"]
            if _lbl in _fl_counts:
                _fl_counts[_lbl] += 1

    # Same colours as classify_evidence() / render_evidenze()
    _badge_cfg = [
        ("Anomalia",           "#B71C1C", "#FDECEA", "Anomalie"),
        ("Punto di attenzione","#F57F17", "#FFFDE7", "Attenzioni"),
        ("Info mancanti",      "#616161", "#F5F5F5", "Info mancanti"),
        ("Elemento positivo",  "#2E7D32", "#F1F8E9", "Positivi"),
    ]
    _badges_html = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;'
        f'background:{_bg};color:{_fg};font-size:0.68rem;font-weight:700;'
        f'padding:3px 9px;border-radius:20px;white-space:nowrap;">'
        f'<span style="font-size:0.6rem;">●</span>{_fl_counts[_k]} {_lbl}</span>'
        for _k, _fg, _bg, _lbl in _badge_cfg if _fl_counts[_k] > 0
    )

    top_l, top_m, top_r = st.columns([3, 1.5, 2])
    with top_l:
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:5px;align-items:center;'
            f'padding:2px 0 10px;">' + pills + '</div>',
            unsafe_allow_html=True)
    with top_m:
        if _badges_html:
            st.markdown(
                f'<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;'
                f'padding:4px 0 10px;justify-content:flex-end;">' + _badges_html + '</div>',
                unsafe_allow_html=True)
    with top_r:
        _tr_a, _tr_b = st.columns(2)
        with _tr_a:
            if st.button("Lancia agenti", key="run_all_top", use_container_width=True):
                _run_all_dialog()
        with _tr_b:
            if st.button("Valutazione finale", key="go_final_top", use_container_width=True):
                st.session_state.step = "final"
                st.rerun()

    # ── Main content (single column) ─────────────────────────────────
    just_completed = st.session_state.get("just_completed")

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

    elif just_completed:
        # ── Just-completed: show result inline, not hidden in a tab ──
        st.session_state.just_completed = None
        sec = next((s for s in MAIN_SECTIONS if s["key"] == just_completed), None)
        if sec:
            st.markdown(
                f'<div style="background:#F0FDF4;border:1px solid #86EFAC;'
                f'border-radius:8px;padding:8px 14px;margin-bottom:14px;'
                f'font-size:0.8rem;color:#15803D;font-weight:600;">'
                f'✓ {sec["icon"]} {sec["full_label"]} — analisi completata.</div>',
                unsafe_allow_html=True)
            _render_section_content(just_completed, client)
            st.markdown(f'<div style="height:8px;"></div>', unsafe_allow_html=True)
            if st.button("Torna a tutte le sezioni", key="back_to_tabs_after_run"):
                st.rerun()

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



# ── Final valuation chatbot ───────────────────────────────────────
def _render_final_chatbot(client, valuation_key: str):
    """Right-side chatbot panel on the final valuation screen."""
    st.markdown(
        f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
        f'color:{BLUE};text-transform:uppercase;margin-bottom:6px;">Assistente AML</div>'
        f'<div style="font-size:0.75rem;color:{TEXT_SEC};margin-bottom:10px;">'
        f'Fai domande sulla valutazione, richiedi approfondimenti su evidenze specifiche '
        f'o chiedi modifiche alla narrativa.</div>',
        unsafe_allow_html=True)

    history = st.session_state.setdefault("final_chat_history", [])

    # Message area
    with st.container(height=420, border=True):
        if not history:
            st.markdown(
                f'<div style="padding:30px 10px;text-align:center;'
                f'color:{TEXT_SEC};font-size:0.8rem;">'
                f'💬 Inizia una conversazione con l\'assistente AML.</div>',
                unsafe_allow_html=True)
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("Fai una domanda o richiedi modifiche…", key="final_chat_input")

    if user_input:
        history.append({"role": "user", "content": user_input})
        if not client:
            history.append({"role": "assistant",
                            "content": "⚠️ API Key non configurata — aggiungi ANTHROPIC_API_KEY."})
            st.rerun()
            return

        # Build context from all available results
        state = st.session_state.kyc_state
        ctx_parts = [
            f"Azienda analizzata: {state.case.company_name} | Paese: {state.case.country}",
        ]
        val_content = get_content(valuation_key)
        if val_content:
            ctx_parts.append(f"VALUTAZIONE FINALE:\n{val_content[:3000]}")
        for sec in MAIN_SECTIONS:
            c = get_content(sec["key"])
            if c:
                ctx_parts.append(f"ANALISI {sec['full_label'].upper()}:\n{c[:1500]}")

        system_msg = (
            "Sei un esperto AML Compliance Officer e assistente di analisi del rischio.\n"
            "Il tuo ruolo è supportare l'analista nella valutazione finale della controparte.\n"
            "Rispondi sempre in italiano, con tono professionale e linguaggio tecnico AML.\n"
            "Puoi: rispondere a domande sulle evidenze, approfondire aspetti normativi "
            "(D.Lgs.231/2007, FATF Recommendations, provvedimenti UIF), proporre modifiche "
            "alla narrativa, suggerire azioni di mitigazione o valutazioni alternative.\n\n"
            "CONTESTO ANALISI COMPLETA:\n\n" + "\n\n---\n\n".join(ctx_parts)
        )

        try:
            api_msgs = [{"role": m["role"], "content": m["content"]} for m in history[-12:]]
            resp  = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_msg,
                messages=api_msgs,
            )
            reply = resp.content[0].text
        except Exception as e:
            reply = f"⚠️ Errore nella risposta: {e}"

        history.append({"role": "assistant", "content": reply})
        st.rerun()

    if history:
        if st.button("🗑 Cancella chat", key="clear_final_chat", use_container_width=True):
            st.session_state.final_chat_history = []
            st.rerun()


# ── Final valuation edit popup ────────────────────────────────────
if hasattr(st, "dialog"):
    @st.dialog("Modifica Valutazione Finale", width="large")
    def _edit_final_dialog():
        key    = "final_valuation"
        parsed = get_parsed(key)
        if not parsed:
            st.warning("Esegui prima l'agente di valutazione finale.")
            if st.button("Chiudi", key="efd_close"):
                st.rerun()
            return

        ev_overrides = st.session_state.get("final_ev_overrides", {})

        # ── Sezione 1: Rischio + Narrativa ────────────────────────
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{BLUE};text-transform:uppercase;margin-bottom:8px;">Profilo di Rischio</div>',
            unsafe_allow_html=True)

        _risk_opts = ["LOW", "MEDIUM", "MEDIO-ALTO", "HIGH", "CRITICAL"]
        _cur_risk  = (st.session_state.get("final_ev_overrides", {}).get("__risk__")
                      or parsed.get("rischioComplessivo", "MEDIUM") or "MEDIUM")
        try:
            _r_idx = _risk_opts.index(_cur_risk.upper())
        except (ValueError, AttributeError):
            _r_idx = 1
        st.selectbox("Rischio complessivo", _risk_opts, index=_r_idx, key="efd_risk")

        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{BLUE};text-transform:uppercase;margin:12px 0 6px;">Narrativa</div>',
            unsafe_allow_html=True)
        _cur_narr = (ev_overrides.get("__narrativa__")
                     or parsed.get("narrativa") or parsed.get("narrativaCompleta") or "")
        st.text_area("", value=_cur_narr, height=200, key="efd_narrativa",
                     label_visibility="collapsed")

        st.markdown(f'<hr style="border-color:{BORDER};margin:16px 0;">', unsafe_allow_html=True)

        # ── Sezione 2: FLAG AML per sezione ──────────────────────
        st.markdown(
            f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
            f'color:{BLUE};text-transform:uppercase;margin-bottom:10px;">'
            f'FLAG AML — modifica evidenze</div>',
            unsafe_allow_html=True)
        st.caption("Modifica il testo, cambia livello o escludi un'evidenza. Le modifiche sovrascrivono l'output dell'agente.")

        for sec in MAIN_SECTIONS:
            sk  = sec["key"]
            sp  = get_parsed(sk)
            if not sp:
                continue
            evs = sp.get("principaliEvidenze", [])
            if not evs:
                continue

            with st.expander(f"{sec['icon']} {sec['full_label']} — {len(evs)} evidenze",
                             expanded=False):
                for i, ev in enumerate(evs):
                    ov       = ev_overrides.get(f"{sk}__{i}", {})
                    cur_txt  = ov.get("evidenza",  ev.get("evidenza", ""))
                    cur_lvl  = ov.get("livello",   ev.get("livello", "ATTENZIONE"))
                    cur_vis  = ov.get("visible", True)

                    st.markdown(
                        f'<div style="font-size:0.75rem;font-weight:600;color:{TEXT_SEC};'
                        f'margin:10px 0 4px;">Evidenza {i + 1}</div>',
                        unsafe_allow_html=True)

                    c_chk, c_lvl = st.columns([1, 2])
                    with c_chk:
                        st.checkbox("Includi", value=cur_vis, key=f"efd_vis_{sk}_{i}")
                    with c_lvl:
                        _lvl_opts = ["ATTENZIONE", "ANOMALIA", "CRITICO"]
                        try:
                            _li = _lvl_opts.index((cur_lvl or "").upper())
                        except ValueError:
                            _li = 0
                        st.selectbox("Livello", _lvl_opts, index=_li,
                                     key=f"efd_lvl_{sk}_{i}")

                    st.text_area("Testo evidenza", value=cur_txt, height=70,
                                 key=f"efd_txt_{sk}_{i}", label_visibility="visible")

        st.markdown(f'<div style="height:6px;"></div>', unsafe_allow_html=True)
        c_ann, c_save = st.columns([1, 2])
        with c_ann:
            if st.button("Annulla", key="efd_cancel", use_container_width=True):
                st.rerun()
        with c_save:
            if st.button("Salva modifiche", key="efd_save", use_container_width=True):
                # ── Persist risk + narrativa into the JSON ────────
                new_risk  = st.session_state.get("efd_risk", "")
                new_narr  = st.session_state.get("efd_narrativa", "")
                _p = dict(get_parsed(key) or {})
                if new_risk:
                    _p["rischioComplessivo"] = new_risk
                if new_narr is not None:
                    _p["narrativa"] = new_narr
                _new_json = json.dumps(_p, ensure_ascii=False, indent=2)
                st.session_state.edited_content[key] = _new_json
                st.session_state.kyc_state.add_result(key, _new_json)
                st.session_state.setdefault("_parsed_cache", {}).pop(key, None)

                # ── Persist evidence overrides ────────────────────
                new_ov = {}
                for sec in MAIN_SECTIONS:
                    sk = sec["key"]
                    sp = get_parsed(sk)
                    if not sp:
                        continue
                    for i, ev in enumerate(sp.get("principaliEvidenze", [])):
                        nv = st.session_state.get(f"efd_vis_{sk}_{i}", True)
                        nl = st.session_state.get(f"efd_lvl_{sk}_{i}",
                                                  ev.get("livello", "ATTENZIONE"))
                        nt = st.session_state.get(f"efd_txt_{sk}_{i}",
                                                  ev.get("evidenza", ""))
                        orig_txt = ev.get("evidenza", "")
                        orig_lvl = ev.get("livello", "")
                        if nt != orig_txt or nl != orig_lvl or not nv:
                            new_ov[f"{sk}__{i}"] = {
                                "evidenza": nt, "livello": nl, "visible": nv}
                st.session_state.final_ev_overrides = new_ov
                st.rerun()
else:
    def _edit_final_dialog():
        pass


# ── STEP 5: FINAL VALUATION ───────────────────────────────────────
def render_final_valuation():
    render_header()
    client = get_client()
    key    = "final_valuation"

    # ── 2-column layout: valuation results (left) + chatbot (right) ──
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown(
            f'<div style="font-size:1.2rem;font-weight:700;color:{TEXT};margin-bottom:4px;">Valutazione finale</div>'
            f'<div style="font-size:0.82rem;color:{TEXT_SEC};margin-bottom:16px;">'
            f'Sintesi del rischio AML e raccomandazione operativa per il fascicolo cliente.</div>',
            unsafe_allow_html=True)

        content = get_content(key)
        parsed  = get_parsed(key)

        _btn_run, _btn_edit = st.columns([2, 1])
        with _btn_run:
            if st.button('Avvia "Final Valuation" Agent', key="run_super_agent",
                         use_container_width=True):
                _run_with_stream(key, client)
                return
        with _btn_edit:
            if parsed and st.button("Modifica", key="edit_final_btn",
                                    use_container_width=True):
                _edit_final_dialog()

        if parsed:
            _ev_ov = st.session_state.get("final_ev_overrides", {})

            # Chips — use classify_evidence() + overrides for 1-to-1 match with FLAG AML
            _chip_counts = {"Anomalia": 0, "Punto di attenzione": 0,
                            "Info mancanti": 0, "Elemento positivo": 0}
            for sec in MAIN_SECTIONS:
                sp = get_parsed(sec["key"])
                if not sp:
                    continue
                for _i, ev in enumerate(sp.get("principaliEvidenze", [])):
                    _ov = _ev_ov.get(f"{sec['key']}__{_i}", {})
                    if not _ov.get("visible", True):
                        continue
                    _ev_eff = dict(ev)
                    if "evidenza" in _ov: _ev_eff["evidenza"] = _ov["evidenza"]
                    if "livello"  in _ov: _ev_eff["livello"]  = _ov["livello"]
                    _lbl = classify_evidence(_ev_eff)["label"]
                    if _lbl in _chip_counts:
                        _chip_counts[_lbl] += 1

            _chip_cfg = [
                ("Anomalia",            "#B71C1C", "#FDECEA"),
                ("Punto di attenzione", "#F57F17", "#FFFDE7"),
                ("Info mancanti",       "#616161", "#F5F5F5"),
                ("Elemento positivo",   "#2E7D32", "#F1F8E9"),
            ]
            chips = "".join(
                f'<span style="background:{_bg};color:{_fg};font-size:0.72rem;'
                f'font-weight:700;padding:3px 12px;border-radius:20px;margin-right:6px;">'
                f'● {_chip_counts[_k]} {_k}</span>'
                for _k, _fg, _bg in _chip_cfg if _chip_counts[_k] > 0
            )
            if chips:
                st.markdown(f'<div style="margin-bottom:12px;">{chips}</div>',
                            unsafe_allow_html=True)

            risk      = parsed.get("rischioComplessivo", "") or parsed.get("customerRiskRating", "")
            rc        = get_risk_color(risk) if risk else BLUE
            narrativa = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                         or parsed.get("sintesiEsecutiva", "") or "")
            racc      = parsed.get("raccomandazione", "")

            racc_str = ""
            if isinstance(racc, dict):
                parts_r = [x for x in [racc.get("accettazione", ""),
                                        racc.get("livelloAdeguataVerifica", ""),
                                        racc.get("frequenzaMonitoraggio", "")] if x]
                if parts_r:
                    racc_str = " · ".join(parts_r)
            elif isinstance(racc, str) and racc:
                racc_str = racc

            # ── Risk badge ────────────────────────────────────────
            # Detect which main sections were NOT run
            _missing_secs = [s for s in MAIN_SECTIONS if sec_status(s["key"]) != "completed"]
            _partial       = len(_missing_secs) > 0

            _partial_html = ""
            if _partial:
                _missing_names = ", ".join(s["full_label"] for s in _missing_secs)
                _partial_html = (
                    f'<div style="width:100%;margin-top:12px;padding:10px 14px;'
                    f'background:#FFFBEB;border:1px solid #FDE68A;border-radius:6px;">'
                    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">'
                    f'<span style="font-size:0.75rem;">⚠️</span>'
                    f'<span style="font-size:0.68rem;font-weight:800;letter-spacing:0.8px;'
                    f'color:#92400E;text-transform:uppercase;">Valutazione parziale — Rating provvisorio</span>'
                    f'</div>'
                    f'<div style="font-size:0.75rem;color:#78350F;line-height:1.6;">'
                    f'<b>Agenti non eseguiti:</b> {_missing_names}.<br>'
                    f'Il Customer Risk Rating è <b>provvisorio</b> e non definitivo ai fini '
                    f'dell\'onboarding o dell\'aggiornamento del fascicolo cliente. '
                    f'Eseguire gli agenti mancanti per ottenere una valutazione completa.'
                    f'</div>'
                    f'</div>'
                )

            st.markdown(
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;'
                f'background:#fff;border:1px solid {BORDER};border-left:4px solid {rc};'
                f'border-radius:0 8px 8px 0;padding:12px 14px;margin-bottom:16px;">'
                f'<span style="font-size:0.65rem;font-weight:700;letter-spacing:0.8px;'
                f'color:{TEXT_SEC};text-transform:uppercase;">Rischio Complessivo</span>'
                f'{risk_badge(risk)}'
                + (f'<span style="margin-left:4px;font-size:0.68rem;font-weight:700;'
                   f'color:#92400E;background:#FFFBEB;padding:2px 8px;border-radius:20px;'
                   f'border:1px solid #FDE68A;">PROVVISORIO</span>' if _partial else '')
                + (f'<div style="width:100%;font-size:0.72rem;color:{TEXT_SEC};margin-top:2px;">'
                   f'{racc_str}</div>' if racc_str else '')
                + _partial_html
                + f'</div>',
                unsafe_allow_html=True)

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
                    + narrativa.replace("\n", "<br>") + '</div>',
                    unsafe_allow_html=True)

            # ── Flag AML — riepilogo completo da tutte le sezioni ──
            _rank_map = {"Anomalia": 0, "Punto di attenzione": 1,
                         "Info mancanti": 2, "Elemento positivo": 3}
            _all_evidenze = []
            for _sec in MAIN_SECTIONS:
                _sp = get_parsed(_sec["key"])
                if not _sp:
                    continue
                for _i, _ev in enumerate(_sp.get("principaliEvidenze", [])):
                    _ov = _ev_ov.get(f"{_sec['key']}__{_i}", {})
                    if not _ov.get("visible", True):
                        continue
                    _ev = dict(_ev)
                    if "evidenza" in _ov: _ev["evidenza"] = _ov["evidenza"]
                    if "livello"  in _ov: _ev["livello"]  = _ov["livello"]
                    _entry = {
                        "sezione":   _sec["full_label"],
                        "sec_icon":  _sec["icon"],
                        "livello":   (_ev.get("livello", "") or "").upper(),
                        "evidenza":  _ev.get("evidenza", ""),
                        "normativa": _ev.get("normativa", ""),
                    }
                    _entry["_ord"] = _rank_map.get(classify_evidence(_entry)["label"], 2)
                    _all_evidenze.append(_entry)
            _all_evidenze.sort(key=lambda x: x["_ord"])

            if _all_evidenze:
                st.markdown(
                    f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:1.2px;'
                    f'color:{TEXT_SEC};margin:0 0 8px;text-transform:uppercase;">Flag AML</div>',
                    unsafe_allow_html=True)
                for _ev in _all_evidenze:
                    _style = classify_evidence(_ev)
                    _norm_html = (
                        f'<p style="color:#9E9E9E;font-size:11px;font-style:italic;margin:4px 0 0;">'
                        f'📎 {_ev["normativa"]}</p>' if _ev["normativa"] else "")
                    _sugg_html = ""
                    if _style["label"] == "Info mancanti":
                        _hint = _info_suggestion(_ev["evidenza"])
                        if _hint:
                            _sugg_html = (
                                f'<div style="display:flex;align-items:flex-start;gap:5px;'
                                f'margin-top:6px;padding:6px 10px;background:#ECECEC;border-radius:4px;">'
                                f'<span style="font-size:11px;color:#616161;font-weight:700;'
                                f'white-space:nowrap;">Azione suggerita:</span>'
                                f'<span style="font-size:11px;color:#424242;line-height:1.5;">{_hint}</span>'
                                f'</div>'
                            )
                    st.markdown(
                        f'<div style="background-color:{_style["bg_color"]};'
                        f'border-left:4px solid {_style["border_color"]};'
                        f'border-radius:4px;padding:12px 16px;margin-bottom:8px;">'
                        f'<span style="background-color:{_style["border_color"]};color:white;'
                        f'font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;'
                        f'text-transform:uppercase;letter-spacing:0.5px;">{_style["label"]}</span>'
                        f'<p style="color:{_style["text_color"]};font-size:13px;'
                        f'margin:8px 0 3px 0;line-height:1.5;">{_ev["evidenza"]}</p>'
                        f'<p style="font-size:11px;color:{TEXT_SEC};margin:0;">'
                        f'{_ev["sec_icon"]} {_ev["sezione"]}</p>'
                        + _norm_html + _sugg_html + f'</div>',
                        unsafe_allow_html=True)

        st.markdown(f'<div style="height:16px;"></div>', unsafe_allow_html=True)
        if st.button("Torna all'analisi", key="back_to_analysis"):
            st.session_state.step = "analysis"
            st.rerun()

    with right_col:
        _render_final_chatbot(client, key)


# ── ROUTER ───────────────────────────────────────────────────────
step = st.session_state.step

if step == "transit":
    # Fallback: if something sets step="transit", go straight to analysis.
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
