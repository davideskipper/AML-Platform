"""
Transaction Agent
=================
Analyzes an Excel/CSV file for AML transaction monitoring patterns
AND geographic risk of counterparties (replaces separate Risk Countries agent).
Returns structured JSON. No web search — analysis based on provided data.
"""

import os
import anthropic
from .utils import run_agent

SYSTEM_PROMPT = """Sei un AML Transaction Monitoring & Geographic Risk Agent.
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
  "principaliEvidenze": [
    {
      "evidenza": "Descrizione sintetica dell'anomalia o elemento di attenzione",
      "normativa": "Riferimento normativo specifico (es. UIF Indic. n.42/2023, Art.35 D.Lgs.231/2007, FATF Rec.10)",
      "livello": "ATTENZIONE (elemento da monitorare, basso rischio → verde) | ANOMALIA (comportamento sospetto, rischio medio → giallo) | CRITICO (red flag grave, rischio alto → rosso)"
    }
  ],
  "rischioComplessivo": "LOW|MEDIUM|HIGH|CRITICAL",
  "narrativa": "Sintesi discorsiva professionale di 10-14 righe per il compliance officer. Struttura: (1) profilo sintetico della controparte, (2) elementi positivi/conformi, (3) anomalie e criticità con richiamo diretto alla normativa applicabile (D.Lgs.231/2007, FATF Recommendations, provvedimenti UIF, Reg. UE 2015/847). Concludi con il razionale del livello di rischio assegnato. Tono formale, linguaggio tecnico AML.",
  "note": ""
}"""


def _read_excel(filepath: str) -> str:
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("pandas not installed. Run: pip install pandas openpyxl")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    ext = os.path.splitext(filepath)[1].lower()
    dfs = {"Sheet1": pd.read_csv(filepath)} if ext == ".csv" else pd.read_excel(filepath, sheet_name=None)
    lines = []
    for sheet_name, df in dfs.items():
        lines.append(f"## Sheet: {sheet_name}")
        lines.append(f"Rows: {len(df)}  |  Columns: {', '.join(str(c) for c in df.columns)}")
        lines.append("")
        lines.append(df.head(500).to_string(index=False))
        if len(df) > 500:
            lines.append(f"\n[... {len(df)-500} more rows omitted ...]")
        lines.append("")
    return "\n".join(lines)


def run(
    client: anthropic.Anthropic,
    excel_path: str,
    company_name: str = "",
    manual_context: str = "",
    show_output: bool = True,
    on_token=None,
    on_thinking=None,
    use_web_search=None,
) -> str:
    excel_text = _read_excel(excel_path)
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
        max_tokens=8000,
        use_web_search=False if use_web_search is None else use_web_search,
        show_output=show_output,
        on_token=on_token,
        on_thinking=on_thinking,
    )
