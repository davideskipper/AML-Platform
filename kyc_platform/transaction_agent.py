"""
Transaction Agent
=================
Analyzes an Excel/CSV file for AML transaction monitoring patterns
AND geographic risk of counterparties (replaces separate Risk Countries agent).
Returns structured JSON. No web search — analysis based on provided data.
"""

import os
import json as _json
import anthropic
from .utils import run_agent

_NO_DOCS_JSON = _json.dumps({
    "rischioComplessivo": "NON_VALUTABILE",
    "principaliEvidenze": [
        {
            "evidenza": "File transazionale (Excel/CSV movimenti bancari) non fornito. Necessario per l'analisi dei flussi e il monitoraggio AML.",
            "normativa": "Art. 18 D.Lgs. 231/2007 — adeguata verifica della clientela",
            "livello": "INFO_MANCANTE",
        }
    ],
    "anomalieTransazionali": [],
    "narrativa": "Nessun file transazionale fornito. L'analisi non può essere eseguita senza un file Excel o CSV con i movimenti bancari.",
    "note": "Caricare il file Excel/CSV delle transazioni prima di avviare l'agente."
}, ensure_ascii=False)

SYSTEM_PROMPT = """REGOLE FONDAMENTALI — ANTI-ALLUCINAZIONE:
- Analizza ESCLUSIVAMENTE i dati transazionali forniti nel messaggio utente.
- NON inventare transazioni, importi, controparti o pattern non presenti nei dati.
- Se un dato non è presente: usa "NON DISPONIBILE" o ometti il campo.
- Non dedurre comportamenti o pattern da dati insufficienti.
- Segnala esplicitamente quando il campione di dati è troppo limitato per conclusioni affidabili.
REGOLE PER principaliEvidenze — TASSONOMIA DEI LIVELLI:

Usa i livelli esattamente come segue:

CRITICO — red flag grave che richiede azione immediata.
  Esempi: paese FATF Black List, reato presupposto AML,
  documento falso o contraffatto, pass-through sistematico,
  soggetto in lista sanzionatoria, PEP non dichiarato.

ANOMALIA — comportamento sospetto che richiede
  approfondimento documentale o escalation interna.
  Esempi: UBO in paese FATF Grey List, finanziamento soci
  senza documentazione origine fondi, concentrazione ricavi
  anomala su controparti non verificabili, struttura societaria
  opaca con più livelli non giustificati.

ATTENZIONE — elemento di rischio reale ma di bassa intensità
  che richiede monitoraggio periodico.
  Esempi: governance accentrata in capo a un solo soggetto,
  oggetto sociale con clausola residuale ampia, società
  costituita da meno di 2 anni, EBITDA margin sopra benchmark
  di settore, primo cliente con concentrazione >30% del fatturato,
  debiti tributari in crescita.

INFO_MANCANTE — informazione necessaria per la valutazione
  che non è presente nei documenti forniti e che il compliance
  officer deve acquisire prima di completare l'istruttoria.
  Esempi: casellario giudiziale estero non verificabile tramite
  canali italiani, contratti con clienti principali non allegati
  al fascicolo, documentazione origine fondi del finanziamento
  soci non fornita, visura non aggiornata (>6 mesi), documento
  d'identità in scadenza entro 90 giorni.

NON INCLUDERE in principaliEvidenze:
- Conferme di assenza di problemi ("nessuna sanzione",
  "casellario negativo", "nessun protesto")
- Elementi positivi o conformi
- Informazioni già presenti e complete nei documenti
  che non richiedono azione

Se non ci sono elementi negativi né informazioni mancanti,
restituisci principaliEvidenze come lista vuota [].

Sei un AML Transaction Monitoring & Geographic Risk Agent.
Svolgi due analisi integrate sul cliente: (A) analisi comportamentale dei flussi bancari
e (B) valutazione del rischio geografico delle controparti.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A) TRANSACTION MONITORING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ANALISI STRUTTURALE DEI FLUSSI:
- Volume totale, frequenza, importo medio delle transazioni nel periodo
- Distribuzione per tipo controparte (persona fisica / giuridica / istituto)
- Canali: bonifici SEPA, esteri, contante, carte, assegni, crypto
- Coerenza con profilo economico atteso (settore, dimensione, stagionalità)

PATTERN DI RICICLAGGIO (rif. UIF Indicatori anomalia 2023):

STRUTTURAZIONE (Placement):
- Operazioni frazionate sotto soglie chiave: €999, €4.999, €9.999, €14.999
- Versamenti multipli in <7 giorni da/verso stessa controparte
- Utilizzo frequente di contante o banconote di grosso taglio (€200/€500)

LAYERING:
- Transazioni circolari (A→B→C→A entro pochi giorni)
- Pass-through: importi in entrata che escono immediatamente (<48h) verso terzi
- Utilizzo conti di terzi come buffer
- Trasferimenti verso paesi ad alto rischio FATF

INTEGRAZIONE:
- Acquisti asset (immobili, veicoli, preziosi, arte) incoerenti con reddito
- Investimenti sproporzionati rispetto al profilo
- Pagamenti verso soggetti senza relazione commerciale documentabile

Livelli di evidenza: ATTENZIONE = rischio basso, ANOMALIA = rischio medio, CRITICO = rischio alto, INFO_MANCANTE = dato da acquisire.

RED FLAG SPECIFICI:
- Operazioni con controparti in paesi FATF Black List o sanzionati
- Operatività incomprensibile rispetto alla natura del rapporto
- Assenza di normale operatività attesa (stipendi, fornitori, utenze)
- Picchi anomali non correlati a stagionalità ATECO
- Causali generiche, assenti o incoerenti con importo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B) RISCHIO GEOGRAFICO DELLE CONTROPARTI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Per ciascun paese coinvolto nei flussi (residenza/sede controparti, IBAN esteri):

CLASSIFICAZIONE — applica in ordine di priorità:
1. FATF Black List (Call for Action) → CRITICAL, misure rafforzate obbligatorie
2. FATF Grey List (Under Increased Monitoring) → HIGH, EDD obbligatoria
3. Lista UE paesi terzi ad alto rischio → HIGH
4. Sanzioni attive EU/UN/OFAC → CRITICAL, verifica immediata
5. Offshore/centri finanziari OCSE lista grigia → MEDIUM/HIGH
6. CPI Transparency International < 40 → fattore aggiuntivo
7. Paesi senza accordi scambio informazioni fiscali con Italia → MEDIUM

FLAG GEOGRAFICI:
- Qualsiasi flusso verso/da paese FATF Black List o sanzionato
- Esposizione significativa (>10% dei flussi) verso paesi Grey List
- Strutture di pagamento che passano per giurisdizioni opache senza logica commerciale

OUTPUT: Restituisci esclusivamente un oggetto JSON valido:

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido. Nessun testo prima o dopo. Nessun markdown, nessun code block. Il tuo output deve iniziare con { e terminare con }.

{
  "rischioComplessivo": "LOW|MEDIUM|HIGH|CRITICAL",
  "narrativa": "Sintesi discorsiva professionale di 10-14 righe per il compliance officer. Struttura: (1) profilo sintetico della controparte, (2) elementi positivi/conformi, (3) anomalie e criticità con richiamo diretto alla normativa applicabile (D.Lgs.231/2007, FATF Recommendations, provvedimenti UIF, Reg. UE 2015/847). Concludi con il razionale del livello di rischio assegnato. Tono formale, linguaggio tecnico AML.",
  "principaliEvidenze": [
    {
      "evidenza": "Descrizione sintetica dell'anomalia o elemento di attenzione",
      "normativa": "Riferimento normativo specifico (es. UIF Indic. n.42/2023, Art.35 D.Lgs.231/2007, FATF Rec.10)",
      "livello": "ATTENZIONE|ANOMALIA|CRITICO|INFO_MANCANTE"
    }
  ],
  "dashboard": {
    "periodoAnalizzato": "",
    "totaleEntrate": 0,
    "totaleUscite": 0,
    "saldoNetto": 0,
    "numeroTransazioni": 0,
    "importoMedioTransazione": 0,
    "top5Controparti": [{ "nome": "", "volume": 0, "numOperazioni": 0 }]
  },
  "anomalieTransazionali": [
    {
      "pattern": "STRUTTURAZIONE|LAYERING|INTEGRAZIONE|RED_FLAG",
      "descrizione": "",
      "dateImportiCoinvolti": "",
      "indicatoreUIF": "",
      "rischio": "LOW|MEDIUM|HIGH|CRITICAL"
    }
  ],
  "analisiGeografica": {
    "paesiCoinvolti": [
      {
        "paese": "",
        "volumeFlussi": 0,
        "percentualeTotale": "",
        "classificazione": "FATF_BLACK|FATF_GREY|EU_HIGH_RISK|SANZIONI|STANDARD",
        "rischio": "LOW|MEDIUM|HIGH|CRITICAL"
      }
    ],
    "esposizioneAltoRischio": false,
    "paeseCriticoPrincipale": ""
  },
  "transazioneSingolareSegnalabile": false,
  "dettaglioTransazioneSegnalabile": "",
  "valutazioneOperativita": "COERENTE|ANOMALIE_MINORI|ANOMALIE_SIGNIFICATIVE|OPERATIVITA_SOSPETTA",
  "bozzaMotivazioneSOS": "",
  "note": ""
}"""


def _read_excel(source) -> str:
    """
    Read an Excel/CSV source and return a text representation.
    `source` can be:
      - str  → file path on disk
      - bytes / BytesIO / UploadedFile → in-memory buffer
    Up to 1000 rows are included per sheet to stay within API context limits.
    CSV separator is auto-detected (tries ';' first, then ',').
    """
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("pandas not installed. Run: pip install pandas openpyxl")

    import io as _io

    # Normalise to a seekable buffer or path string
    if isinstance(source, (bytes, bytearray)):
        buf = _io.BytesIO(source)
        ext = ".bin"          # unknown — will try excel first
    elif isinstance(source, str):
        if not os.path.exists(source):
            raise FileNotFoundError(f"File not found: {source}")
        buf = source          # pass path directly to pandas
        ext = os.path.splitext(source)[1].lower()
    else:
        # BytesIO / UploadedFile (has .name attribute)
        name = getattr(source, "name", "")
        ext  = os.path.splitext(name)[1].lower()
        source.seek(0)
        buf = source

    def _read_csv(b):
        """Try multiple separators and encodings to parse CSV robustly.
        Separator: ';' first, fall back to ','.
        Encoding: utf-8-sig → latin-1 → cp1252 (covers Italian bank exports).
        """
        _ENCODINGS = ["utf-8-sig", "latin-1", "cp1252"]

        def _try_csv(data, sep):
            for enc in _ENCODINGS:
                try:
                    buf_c = _io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else _io.BytesIO(data.getvalue())
                    return pd.read_csv(buf_c, sep=sep, encoding=enc)
                except (UnicodeDecodeError, Exception):
                    continue
            raise RuntimeError("Impossibile decodificare il CSV con le codifiche supportate (utf-8, latin-1, cp1252).")

        if isinstance(b, str):
            for enc in _ENCODINGS:
                try:
                    df = pd.read_csv(b, sep=";", encoding=enc)
                    if len(df.columns) == 1:
                        df = pd.read_csv(b, sep=",", encoding=enc)
                    return {"Sheet1": df}
                except (UnicodeDecodeError, Exception):
                    continue
            raise RuntimeError("Impossibile leggere il CSV.")
        else:
            raw = b.read() if hasattr(b, "read") else b
            raw = raw if isinstance(raw, (bytes, bytearray)) else raw.getvalue()
            df = _try_csv(raw, ";")
            if len(df.columns) == 1:
                df = _try_csv(raw, ",")
            return {"Sheet1": df}

    if ext == ".csv":
        dfs = _read_csv(buf)
    elif ext in (".xlsx", ".xls"):
        dfs = pd.read_excel(buf, sheet_name=None)
    else:
        # Unknown extension — try Excel first, then CSV
        try:
            dfs = pd.read_excel(buf, sheet_name=None)
        except Exception:
            if hasattr(buf, "seek"):
                buf.seek(0)
            dfs = _read_csv(buf)

    _MAX_ROWS = 1000  # keep input within API context limits
    lines = []
    for sheet_name, df in dfs.items():
        total_rows = len(df)
        df_disp = df.head(_MAX_ROWS)
        lines.append(f"## Sheet: {sheet_name}")
        lines.append(f"Rows: {total_rows}  |  Columns: {', '.join(str(c) for c in df.columns)}"
                     + (f"  |  [TRONCATO a {_MAX_ROWS} righe]" if total_rows > _MAX_ROWS else ""))
        lines.append("")
        lines.append(df_disp.to_string(index=False))
        lines.append("")
    return "\n".join(lines)


def run(
    client: anthropic.Anthropic,
    excel_source,          # str path OR BytesIO/UploadedFile
    company_name: str = "",
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
    on_thinking=None,
    use_web_search=None,
) -> str:
    if not excel_source:
        return _NO_DOCS_JSON

    excel_text = _read_excel(excel_source)
    subject = f" per {company_name}" if company_name else ""
    user_msg = (
        f"Esegui l'analisi AML transazioni e rischio geografico{subject}.\n\n"
        f"Dati transazionali:\n\n{excel_text}"
    )
    if manual_context:
        user_msg += f"\n\nContesto aggiuntivo:\n{manual_context}"

    return run_agent(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_msg,
        header=f"Transaction & Geographic Risk Agent{subject}",
        max_tokens=16000,
        use_web_search=False if use_web_search is None else use_web_search,
        show_output=show_output,
        on_token=on_token,
        on_thinking=on_thinking,
    )
